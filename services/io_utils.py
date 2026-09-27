"""CSV import/export and DB backup/restore helpers."""
import csv
import shutil
from decimal import Decimal, InvalidOperation
from pathlib import Path


import db


CSV_FIELDS = ["date", "type", "category", "account", "amount", "note"]




def export_csv(path: str | Path) -> None:
    """Write all transactions to a CSV file with human-readable columns."""
    path = Path(path)
    txns = db.list_transactions()
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for t in txns:
            writer.writerow(
                {
                    "date": t.get("date", ""),
                    "type": t.get("type", ""),
                    "category": t.get("category_name", ""),
                    "account": t.get("account_name", ""),
                    "amount": str(t.get("amount", Decimal("0.00"))),
                    "note": t.get("note", ""),
                }
            )




def _get_or_create_category(name: str, type_: str, cache: dict) -> int:
    """Look up a category by (name, type), creating it if missing, using a cache dict."""
    key = (name.strip().lower(), type_)
    if key in cache:
        return cache[key]
    for c in db.list_categories(type_):
        if c["name"].strip().lower() == name.strip().lower():
            cache[key] = c["id"]
            return c["id"]
    import components


    palette = components.CATEGORY_COLOR_PALETTE
    idx = len(cache) % len(palette)
    new_id = db.add_category(name.strip(), type_, "❓", palette[idx])
    cache[key] = new_id
    return new_id




def _get_or_create_account(name: str, cache: dict) -> int:
    """Look up an account by name, creating it if missing, using a cache dict."""
    key = name.strip().lower()
    if key in cache:
        return cache[key]
    for a in db.list_accounts():
        if a["name"].strip().lower() == key:
            cache[key] = a["id"]
            return a["id"]
    new_id = db.add_account(name.strip(), "Wallet", Decimal("0"))
    cache[key] = new_id
    return new_id




def import_csv(path: str | Path) -> tuple[int, int]:
    """Import transactions from a CSV file with CSV_FIELDS columns; returns (inserted, skipped)."""
    path = Path(path)
    inserted = 0
    skipped = 0
    cat_cache: dict = {}
    acct_cache: dict = {}


    try:
        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames is None or not set(CSV_FIELDS).issubset(set(reader.fieldnames)):
                return (0, 0)
            for row in reader:
                try:
                    date = (row.get("date") or "").strip()
                    type_ = (row.get("type") or "").strip().lower()
                    category = (row.get("category") or "Uncategorized").strip()
                    account = (row.get("account") or "Wallet").strip()
                    amount_raw = (row.get("amount") or "").strip()
                    note = (row.get("note") or "").strip()


                    if not date or type_ not in ("income", "expense") or not amount_raw:
                        skipped += 1
                        continue
                    try:
                        amount = Decimal(amount_raw)
                    except InvalidOperation:
                        skipped += 1
                        continue


                    category_id = _get_or_create_category(category or "Uncategorized", type_, cat_cache)
                    account_id = _get_or_create_account(account or "Wallet", acct_cache)


                    db.add_transaction(amount, type_, category_id, account_id, date, note)
                    inserted += 1
                except Exception:
                    skipped += 1
    except OSError:
        return (0, 0)


    return (inserted, skipped)




def backup_db(dest: str | Path) -> None:
    """Copy the live SQLite file to dest."""
    shutil.copy2(str(db.DB_PATH), str(dest))




def restore_db(src: str | Path) -> None:
    """Replace the live SQLite file with src. Caller must confirm with the user first."""
    shutil.copy2(str(src), str(db.DB_PATH))
