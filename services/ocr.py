"""Offline receipt OCR using pytesseract + Pillow. Degrades gracefully if unavailable."""
import datetime as dt
import re
from pathlib import Path

try:
    import pytesseract
    from PIL import Image

    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False

AMOUNT_RE = re.compile(r"(?:rs\.?|inr|₹)\s*([0-9][0-9,]*\.?[0-9]{0,2})", re.IGNORECASE)
DATE_RE = re.compile(r"(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})")


def is_available() -> bool:
    """Return True if pytesseract + Pillow are importable in this environment."""
    return OCR_AVAILABLE


def extract_receipt(image_path: str | Path) -> dict:
    """Extract {amount, date, vendor, raw_text} from a receipt image, or raise RuntimeError."""
    if not OCR_AVAILABLE:
        raise RuntimeError(
            "OCR is unavailable. Install with: pip install pytesseract Pillow "
            "(and the Tesseract binary via your OS package manager)."
        )
    image = Image.open(image_path)
    text = pytesseract.image_to_string(image)

    amount = None
    m = AMOUNT_RE.search(text)
    if m:
        amount = m.group(1).replace(",", "")

    date_str = None
    d = DATE_RE.search(text)
    if d:
        date_str = d.group(1)

    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    vendor = lines[0] if lines else "Unknown"

    return {
        "amount": amount,
        "date": date_str or dt.date.today().isoformat(),
        "vendor": vendor,
        "raw_text": text,
    }


if __name__ == "__main__":
    assert is_available() in (True, False)
    print("OK")