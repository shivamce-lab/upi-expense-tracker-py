"""Recurring transaction engine: rolls due recurring rules (salary/rent/SIP) into real transactions."""
import datetime as dt

import db


def _advance(date: dt.date, cycle: str) -> dt.date:
    """Advance a date forward by one cycle increment."""
    if cycle == "weekly":
        return date + dt.timedelta(days=7)
    if cycle == "yearly":
        try:
            return date.replace(year=date.year + 1)
        except ValueError:
            return date.replace(year=date.year + 1, day=28)
    # monthly (also used as fallback/default)
    month = date.month + 1
    year = date.year + (1 if month > 12 else 0)
    month = month if month <= 12 else 1
    import calendar as _cal

    last_day = _cal.monthrange(year, month)[1]
    day = min(date.day, last_day)
    return dt.date(year, month, day)


def run_due(kind: str = "recurring", today: dt.date | None = None) -> int:
    """Insert transactions for any active recurring rule of `kind` whose next_date <= today.

    Rolls next_date forward (possibly multiple cycles if the app was closed a while) and
    stamps last_run. Returns the number of transactions inserted.
    """
    today = today or dt.date.today()
    inserted = 0
    for rule in db.list_recurring(kind=kind):
        next_date = dt.date.fromisoformat(rule["next_date"])
        cycle = rule.get("cycle") or "monthly"
        safety = 0
        while next_date <= today and safety < 500:
            db.add_transaction(
                amount=rule["amount"],
                type_=rule["type"],
                category_id=rule["category_id"],
                account_id=rule["account_id"],
                date=next_date.isoformat(),
                note=f"Recurring: {rule['name']}",
            )
            inserted += 1
            db.update_recurring(rule["id"], last_run=next_date.isoformat())
            if cycle == "none":
                db.delete_recurring(rule["id"])
                break
            next_date = _advance(next_date, cycle)
            safety += 1
        if safety >= 1 or next_date != dt.date.fromisoformat(rule["next_date"]):
            db.update_recurring(rule["id"], next_date=next_date.isoformat())
    return inserted


def run_due_all() -> dict:
    """Run due recurring transactions and subscriptions in one pass, return counts by kind."""
    return {
        "recurring": run_due(kind="recurring"),
        "subscription": run_due(kind="subscription"),
    }


if __name__ == "__main__":
    result = run_due_all()
    assert set(result.keys()) == {"recurring", "subscription"}
    print("OK")