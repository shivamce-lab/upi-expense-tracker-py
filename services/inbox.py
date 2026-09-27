"""Share-sheet-style inbox: reads inbox.txt for bank SMS/UPI text and regex-parses transactions."""
import re
from pathlib import Path

import db

AMOUNT_RE = re.compile(r"(?:rs\.?|inr|₹)\s*([0-9][0-9,]*\.?[0-9]{0,2})", re.IGNORECASE)
DATE_RE = re.compile(r"(\d{1,2}[-/][A-Za-z]{3}[-/]\d{2,4}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})")
MERCHANT_RE = re.compile(r"(?:at|to|towards)\s+([A-Za-z0-9 &._-]{2,30})", re.IGNORECASE)

INBOX_FILENAME = "inbox.txt"


def inbox_path() -> Path:
    """Return the path to inbox.txt under the app's data directory."""
    return Path(db.DB_PATH).parent / INBOX_FILENAME


def ingest_inbox_file() -> int:
    """Read any new lines from inbox.txt into the DB as unparsed inbox messages, return count added."""
    path = inbox_path()
    if not path.exists():
        return 0
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines() if ln.strip()]
    added = 0
    for line in lines:
        db.add_inbox_message(line)
        added += 1
    try:
        path.unlink()
    except OSError:
        pass
    return added


def parse_message(text: str) -> dict | None:
    """Regex-parse a bank SMS/UPI message into {amount, date, merchant}, or None if unparseable."""
    amount_m = AMOUNT_RE.search(text)
    if not amount_m:
        return None
    amount = amount_m.group(1).replace(",", "")
    date_m = DATE_RE.search(text)
    merchant_m = MERCHANT_RE.search(text)
    return {
        "amount": amount,
        "date": date_m.group(1) if date_m else None,
        "merchant": merchant_m.group(1).strip() if merchant_m else "Unknown",
    }


def review_summary() -> tuple[int, int]:
    """Return (unparsed_count, total_count) of stored inbox messages, parsing what it can."""
    ingest_inbox_file()
    unparsed = [m for m in db.list_inbox_messages(parsed=False)]
    still_unparsed = 0
    for msg in unparsed:
        parsed = parse_message(msg["raw_text"])
        if parsed is None:
            still_unparsed += 1
    total = len(db.list_inbox_messages())
    return still_unparsed, total


if __name__ == "__main__":
    parsed = parse_message("Rs.499.00 debited at SWIGGY on 12-Jan-24")
    assert parsed is not None and parsed["amount"] == "499.00"
    print("OK")