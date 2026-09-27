"""Pure-Python (no LLM) statistical insight generation for the Analysis screen."""
import calendar
import datetime as dt
from decimal import Decimal

import db
from services import enhancements


def _prev_month(year: int, month: int) -> tuple[int, int]:
    """Return the (year, month) preceding the given one."""
    m = month - 1
    y = year
    if m == 0:
        m, y = 12, year - 1
    return y, m


def _month_range(year: int, month: int) -> tuple[str, str]:
    """Return (start, end) ISO date strings for a calendar month."""
    last_day = calendar.monthrange(year, month)[1]
    return f"{year:04d}-{month:02d}-01", f"{year:04d}-{month:02d}-{last_day:02d}"


def generate_insights(year: int | None = None, month: int | None = None) -> list[str]:
    """Generate a handful of plain-English insight lines from local transaction stats."""
    today = dt.date.today()
    year = year or today.year
    month = month or today.month
    lines: list[str] = []

    start, end = _month_range(year, month)
    cats = db.category_totals(start, end)
    py, pm = _prev_month(year, month)
    pstart, pend = _month_range(py, pm)
    prev_cats = {c["category_id"]: c["total"] for c in db.category_totals(pstart, pend)}

    for c in cats[:3]:
        prev = prev_cats.get(c["category_id"], Decimal("0.00"))
        if prev > 0:
            pct = float((c["total"] - prev) / prev) * 100
            direction = "more" if pct >= 0 else "less"
            lines.append(
                f"You spent {enhancements.inr(c['total'])} on {c['name']} this month — "
                f"{abs(pct):.0f}% {direction} than last month."
            )
        else:
            lines.append(f"You spent {enhancements.inr(c['total'])} on {c['name']} this month.")

    merchants = db.merchant_totals(start, end)
    if merchants:
        top = merchants[0]
        lines.append(
            f"Your top merchant was {top['note']} ({enhancements.inr(top['total'])} across {top['count']} orders)."
        )

    totals = db.month_totals(year, month)
    last_day = calendar.monthrange(year, month)[1]
    days_elapsed = today.day if (year, month) == (today.year, today.month) else last_day
    days_elapsed = max(days_elapsed, 1)
    daily_burn = totals["expense"] / days_elapsed
    projected_expense = daily_burn * last_day
    projected_savings = totals["income"] - projected_expense
    if projected_savings >= 0:
        lines.append(f"You are on track to save {enhancements.inr(projected_savings)} this month.")
    else:
        lines.append(f"You are on track to overspend by {enhancements.inr(-projected_savings)} this month.")

    if not cats and not merchants:
        lines = ["Not enough data yet this month — add a few transactions to see insights."]

    return lines


def has_ai_key() -> bool:
    """Return True if the user has configured an optional external AI key in settings."""
    return bool(db.get_setting("openai_api_key") or db.get_setting("gemini_api_key"))


if __name__ == "__main__":
    result = generate_insights(2024, 1)
    assert isinstance(result, list) and len(result) >= 1
    print("OK")