"""Bill-splitting with named participants and per-person settlement tracking."""
from decimal import Decimal

import db


def split_transaction(txn_id: int, shares: dict[str, Decimal]) -> list[int]:
    """Record per-person shares for a transaction's bill-split, return the new split row ids."""
    ids = []
    for person, share in shares.items():
        ids.append(db.add_person_split(txn_id, person, share))
    return ids


def person_totals() -> list[dict]:
    """Return running totals per person across all splits: {person, owed, paid_count, unpaid_count}."""
    splits = db.list_person_splits()
    totals: dict[str, dict] = {}
    for s in splits:
        p = totals.setdefault(s["person"], {"person": s["person"], "owed": Decimal("0.00"), "settled": 0, "unsettled": 0})
        if not s["settled"]:
            p["owed"] += s["share"]
            p["unsettled"] += 1
        else:
            p["settled"] += 1
    return list(totals.values())


def settle(split_id: int) -> None:
    """Mark a person-split as settled."""
    db.set_split_settled(split_id, True)


def unsettle(split_id: int) -> None:
    """Mark a person-split as unsettled."""
    db.set_split_settled(split_id, False)


if __name__ == "__main__":
    totals = person_totals()
    assert isinstance(totals, list)
    print("OK")