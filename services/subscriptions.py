"""Subscription helpers built on top of db.recurring (kind='subscription')."""
import datetime as dt
from decimal import Decimal

import db

CYCLE_DAYS = {"weekly": 7, "monthly": 30, "yearly": 365}


def add_subscription(
    name: str, amount: Decimal, category_id: int | None, account_id: int,
    cycle: str, next_date: str | None = None,
) -> int:
    """Add a new subscription (a recurring rule with kind='subscription')."""
    next_date = next_date or dt.date.today().isoformat()
    return db.add_recurring(name, amount, "expense", category_id, account_id, cycle, next_date, kind="subscription")


def list_subscriptions() -> list[dict]:
    """Return all active subscriptions with computed monthly_cost, yearly_cost, and progress."""
    subs = db.list_recurring(kind="subscription")
    today = dt.date.today()
    out = []
    for s in subs:
        cycle_days = CYCLE_DAYS.get(s["cycle"], 30)
        next_date = dt.date.fromisoformat(s["next_date"])
        days_left = (next_date - today).days
        progress = 1 - (days_left / cycle_days) if cycle_days else 0.0
        progress = max(0.0, min(1.0, progress))

        if s["cycle"] == "yearly":
            monthly_cost = (s["amount"] / Decimal("12")).quantize(Decimal("0.01"))
            yearly_cost = s["amount"]
        elif s["cycle"] == "weekly":
            monthly_cost = (s["amount"] * Decimal("4.33")).quantize(Decimal("0.01"))
            yearly_cost = (s["amount"] * Decimal("52")).quantize(Decimal("0.01"))
        else:  # monthly
            monthly_cost = s["amount"]
            yearly_cost = (s["amount"] * Decimal("12")).quantize(Decimal("0.01"))

        item = dict(s)
        item["days_left"] = days_left
        item["progress"] = progress
        item["monthly_cost"] = monthly_cost
        item["yearly_cost"] = yearly_cost
        out.append(item)
    return out


def total_monthly_spend() -> Decimal:
    """Return the sum of all subscriptions' monthly-equivalent cost."""
    total = Decimal("0.00")
    for s in list_subscriptions():
        total += s["monthly_cost"]
    return total


def cancel_subscription(id_: int) -> None:
    """Soft-delete (deactivate) a subscription."""
    db.delete_recurring(id_)


def update_subscription(id_: int, **fields) -> None:
    """Update fields of an existing subscription."""
    db.update_recurring(id_, **fields)


if __name__ == "__main__":
    subs = list_subscriptions()
    assert isinstance(subs, list)
    assert total_monthly_spend() >= Decimal("0.00")
    print("OK")