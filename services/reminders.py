"""Bill-due computation, payment recording, and notification helpers."""
import datetime as dt
from decimal import Decimal


import flet as ft


import db




def _roll_forward(due: dt.date, cycle: str, past: dt.date) -> dt.date:
    """Roll a due date forward by cycle increments until it is on/after `past`."""
    if cycle == "none":
        return due
    while due < past:
        if cycle == "weekly":
            due += dt.timedelta(days=7)
        elif cycle == "yearly":
            try:
                due = due.replace(year=due.year + 1)
            except ValueError:
                due = due.replace(year=due.year + 1, day=28)
        else:  # monthly
            month = due.month + 1
            year = due.year + (1 if month > 12 else 0)
            month = month if month <= 12 else 1
            day = min(due.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                                 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
            due = dt.date(year, month, day)
    return due




def upcoming_bills(days_ahead: int = 14) -> list[dict]:
    """Return active bills with their next due date and days_left, sorted ascending."""
    today = dt.date.today()
    results = []
    for bill in db.list_bills():
        cycle = bill.get("cycle") or "monthly"
        due_date_str = bill.get("due_date")
        if not due_date_str:
            continue
        due = dt.date.fromisoformat(due_date_str)
        last_paid = bill.get("last_paid")


        if cycle == "none":
            if last_paid:
                continue  # already paid, no recurrence
            next_due = due
        else:
            anchor = due
            if last_paid:
                paid_date = dt.date.fromisoformat(last_paid)
                anchor = max(due, paid_date)
                anchor = _roll_forward(anchor, cycle, paid_date + dt.timedelta(days=1))
            next_due = _roll_forward(anchor, cycle, today)


        days_left = (next_due - today).days
        if days_left <= days_ahead:
            results.append(
                {
                    "bill": bill,
                    "due": next_due,
                    "days_left": days_left,
                    "overdue": days_left < 0,
                }
            )
    results.sort(key=lambda r: r["days_left"])
    return results




def mark_paid(bill_id: int) -> int:
    """Insert an expense transaction for the bill's amount today, set last_paid, return txn id."""
    conn = db.get_conn()
    try:
        row = conn.execute("SELECT * FROM bills WHERE id = ?", (bill_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise ValueError(f"Bill {bill_id} not found")
    bill = {k: row[k] for k in row.keys()}
    today = dt.date.today().isoformat()


    txn_id = db.add_transaction(
        amount=db.to_decimal(bill["amount"]),
        type_="expense",
        category_id=bill["category_id"],
        account_id=bill["account_id"],
        date=today,
        note=f"Bill payment: {bill['name']}",
    )
    db.update_bill(bill_id, last_paid=today)
    return txn_id




def notify_due(page: ft.Page, days_ahead: int = 3) -> None:
    """Show an in-app SnackBar for overdue/soon-due bills and attempt OS notifications via plyer."""
    import components


    due = upcoming_bills(max(days_ahead, 1))
    overdue = [d for d in due if d["overdue"]]
    soon = [d for d in due if not d["overdue"] and d["days_left"] <= days_ahead]


    if overdue:
        components.show_error(page, f"⚠ {len(overdue)} bill(s) overdue!")
    elif soon:
        first = soon[0]
        components.show_info(page, f"🔔 {first['bill']['name']} due in {first['days_left']} day(s)")


    try:
        from plyer import notification


        for item in due[:3]:
            try:
                days_left = item["days_left"]
                due_text = "today" if days_left == 0 else f"in {days_left} day(s)"
                notification.notify(
                    title="MyMoney bill reminder",
                    message=f"{item['bill']['name']} due {due_text}",
                    timeout=5,
                )
            except Exception:
                pass
    except Exception:
        pass
