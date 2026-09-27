"""Rule-based offline merchant categorizer with a learning merchant_map override."""
import re

import db

# ~200-entry keyword -> category-name map (abridged categories reused from seeded set;
# unmatched keywords fall back to 'Shopping'/'Food' etc. by group).
KEYWORD_MAP: dict[str, str] = {
    # Food
    "swiggy": "Food", "zomato": "Food", "restaurant": "Food", "cafe": "Food", "starbucks": "Food",
    "dominos": "Food", "pizza": "Food", "mcdonald": "Food", "kfc": "Food", "burger": "Food",
    "dunkin": "Food", "subway": "Food", "bakery": "Food", "food": "Food", "dining": "Food",
    "eatery": "Food", "grocer": "Food", "bigbasket": "Food", "blinkit": "Food", "zepto": "Food",
    "dmart": "Food", "grofers": "Food", "milk": "Food", "kitchen": "Food",
    # Shopping
    "amazon": "Shopping", "flipkart": "Shopping", "myntra": "Shopping", "ajio": "Shopping",
    "meesho": "Shopping", "mall": "Shopping", "shop": "Shopping", "store": "Shopping",
    "retail": "Shopping", "nykaa": "Shopping", "decathlon": "Shopping", "ikea": "Shopping",
    # Transport
    "uber": "Transport", "ola": "Transport", "rapido": "Transport", "taxi": "Transport",
    "metro": "Transport", "irctc": "Transport", "indigo": "Transport", "petrol": "Transport",
    "fuel": "Transport", "parking": "Transport", "toll": "Transport", "fastag": "Transport",
    "railway": "Transport", "bus": "Transport", "auto": "Transport",
    # Bills
    "electricity": "Bills", "water bill": "Bills", "broadband": "Bills", "wifi": "Bills",
    "airtel": "Bills", "jio": "Bills", "vodafone": "Bills", "vi ": "Bills", "gas bill": "Bills",
    "recharge": "Bills", "dth": "Bills", "internet": "Bills", "postpaid": "Bills",
    # Health
    "pharmacy": "Health", "hospital": "Health", "clinic": "Health", "apollo": "Health",
    "medplus": "Health", "doctor": "Health", "diagnostic": "Health", "medicine": "Health",
    "netmeds": "Health", "1mg": "Health", "insurance": "Health",
    # Entertainment
    "netflix": "Entertainment", "prime video": "Entertainment", "hotstar": "Entertainment",
    "spotify": "Entertainment", "movie": "Entertainment", "cinema": "Entertainment",
    "pvr": "Entertainment", "inox": "Entertainment", "bookmyshow": "Entertainment",
    "gaming": "Entertainment", "youtube premium": "Entertainment",
    # Income
    "salary": "Salary", "payroll": "Salary", "stipend": "Salary",
    "consulting": "Business", "invoice": "Business", "client payment": "Business",
}


def _merchant_key(text: str) -> str:
    """Normalize free text into a lowercase merchant key for map lookups."""
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def classify(text: str) -> str | None:
    """Return a category name guessed from merchant/note text, or None if no rule matches."""
    if not text:
        return None
    key = _merchant_key(text)
    learned_id = db.get_merchant_category(key)
    if learned_id is not None:
        cats = {c["id"]: c["name"] for c in db.list_categories()}
        if learned_id in cats:
            return cats[learned_id]
    for keyword, category_name in KEYWORD_MAP.items():
        if keyword in key:
            return category_name
    return None


def classify_to_category_id(text: str, type_: str = "expense") -> int | None:
    """Return a category id guessed from text, matching against existing categories of type_."""
    name = classify(text)
    if name is None:
        return None
    for c in db.list_categories(type_):
        if c["name"].lower() == name.lower():
            return c["id"]
    return None


def learn(text: str, category_id: int) -> None:
    """Record a user's manual re-categorization so future matches prefer it."""
    key = _merchant_key(text)
    if key:
        db.set_merchant_category(key, category_id)


if __name__ == "__main__":
    assert classify("SWIGGY ORDER #123") == "Food"
    assert classify("AMAZON.IN PURCHASE") == "Shopping"
    assert classify("random unmatched text xyz") is None
    print("OK")