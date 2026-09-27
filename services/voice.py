"""Offline voice-command parsing using Vosk (tiny model). Degrades gracefully if unavailable."""
import re

try:
    import vosk  # noqa: F401

    VOSK_AVAILABLE = True
except ImportError:
    VOSK_AVAILABLE = False

NUMBER_WORDS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
    "eight": 8, "nine": 9, "ten": 10, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50,
    "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100, "thousand": 1000,
}


def is_available() -> bool:
    """Return True if the vosk package is importable in this environment."""
    return VOSK_AVAILABLE


def _words_to_number(text: str) -> float | None:
    """Convert a simple English number phrase ('two hundred') to a float."""
    tokens = text.lower().split()
    total, current = 0, 0
    found = False
    for tok in tokens:
        if tok in NUMBER_WORDS:
            found = True
            val = NUMBER_WORDS[tok]
            if val == 100:
                current = (current or 1) * 100
            elif val == 1000:
                current = (current or 1) * 1000
                total += current
                current = 0
            else:
                current += val
        elif tok.isdigit():
            found = True
            current += int(tok)
    total += current
    return float(total) if found else None


def parse_command(text: str) -> dict:
    """Parse a spoken command like 'spent two hundred on food from wallet' into structured fields."""
    text_lower = text.lower()
    amount = None
    m = re.search(r"(\d+(?:\.\d+)?)", text_lower)
    if m:
        amount = float(m.group(1))
    else:
        amount_phrase = re.sub(r"^(spent|paid|spend)\s+", "", text_lower)
        amount_phrase = re.split(r"\s+on\s+|\s+from\s+", amount_phrase)[0]
        amount = _words_to_number(amount_phrase)

    category = None
    cat_match = re.search(r"\bon\s+([a-z ]+?)(?:\s+from\b|$)", text_lower)
    if cat_match:
        category = cat_match.group(1).strip()

    account = None
    acc_match = re.search(r"\bfrom\s+([a-z ]+)$", text_lower)
    if acc_match:
        account = acc_match.group(1).strip()

    return {"amount": amount, "category": category, "account": account, "raw": text}


def listen_and_parse(model_path: str | None = None) -> dict:
    """Capture a short audio command via Vosk and return parsed fields, or raise RuntimeError."""
    if not VOSK_AVAILABLE:
        raise RuntimeError(
            "Voice input is unavailable. Install with: pip install vosk, and download a "
            "small model from https://alphacephei.com/vosk/models (e.g. vosk-model-small-en-us)."
        )
    raise RuntimeError("Microphone capture not wired up in this offline demo build.")


if __name__ == "__main__":
    result = parse_command("spent two hundred on food from wallet")
    assert result["amount"] == 200.0
    assert result["category"] == "food"
    assert result["account"] == "wallet"
    print("OK")