"""Net worth computation: assets vs liabilities, percentages, and a plain-English debt line."""
from decimal import Decimal

import db

LIABILITY_TYPES = {"Card", "Loan", "Credit Card"}


def compute_networth() -> dict:
    """Return {assets, liabilities, net_worth, own_pct, owe_pct, debt_per_100} as Decimals/floats.

    An account counts as a liability if its balance is negative, regardless of its
    declared type (a credit card in credit still counts as an asset).
    """
    accounts = db.list_accounts()
    assets = sum((a["balance"] for a in accounts if a["balance"] > 0), Decimal("0.00"))
    liabilities = sum((-a["balance"] for a in accounts if a["balance"] < 0), Decimal("0.00"))
    net_worth = assets - liabilities

    total_base = assets + liabilities
    if total_base > 0:
        own_pct = float(assets / total_base) * 100
        owe_pct = 100.0 - own_pct
    else:
        own_pct, owe_pct = 100.0, 0.0

    if assets > 0:
        debt_per_100 = (liabilities / assets) * 100
    else:
        debt_per_100 = Decimal("100.00") if liabilities > 0 else Decimal("0.00")

    return {
        "assets": assets,
        "liabilities": liabilities,
        "net_worth": net_worth,
        "own_pct": own_pct,
        "owe_pct": owe_pct,
        "debt_per_100": debt_per_100.quantize(Decimal("0.01")),
    }


def debt_check_line(currency: str = "₹") -> str:
    """Return a plain-English 'for every X you own, you owe Y' style line."""
    nw = compute_networth()
    if nw["assets"] == 0 and nw["liabilities"] == 0:
        return "Add accounts to track your debt ratio."
    if nw["assets"] == 0:
        return f"You have no assets recorded but {currency}{nw['liabilities']:,.2f} in liabilities."
    return f"For every {currency}100 you own, you owe {currency}{nw['debt_per_100']:,.0f}"


if __name__ == "__main__":
    nw = compute_networth()
    assert set(nw.keys()) == {"assets", "liabilities", "net_worth", "own_pct", "owe_pct", "debt_per_100"}
    line = debt_check_line()
    assert isinstance(line, str) and len(line) > 0
    print("OK")