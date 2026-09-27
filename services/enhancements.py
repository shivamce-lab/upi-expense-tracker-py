# services/enhancements.py
"""
Single-file enhancement layer for MyMoney.

Solves three problems in one module:
  1. Rupee (INR) formatting with Indian lakh/crore grouping — replaces "₹X.XX" everywhere.
  2. Unlimited category creation — a helper that never runs out, auto-picks icon + color.
  3. Offline PDF bank-statement import — pdfplumber text layer first, pytesseract OCR fallback.
Plus: UI polish helpers (card, chip, empty_state) used by new screens.

Free forever. No server. No API keys.
"""

from __future__ import annotations

import datetime as dt
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Iterable

import flet as ft

import db  # project-local


# ============================================================
# 1.  RUPEES — Indian grouping, drop-in for "₹X.XX"
# ============================================================

INR = "₹"

def inr(value, with_symbol: bool = True) -> str:
    """Format Decimal/float/str as Indian Rupees with lakh/crore grouping.

    inr(1234.5)      -> '₹1,234.50'
    inr(1234567.89)  -> '₹12,34,567.89'
    inr(-4520)       -> '-₹4,520.00'
    """
    try:
        d = Decimal(str(value)).quantize(Decimal("0.01"))
    except (InvalidOperation, ValueError, TypeError):
        d = Decimal("0.00")

    neg = d < 0
    d = abs(d)
    whole = int(d)
    frac = int((d - whole) * 100)
    whole_s = str(whole)

    # Indian grouping: rightmost 3 digits, then groups of 2
    if len(whole_s) > 3:
        head, tail = whole_s[:-3], whole_s[-3:]
        head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
        whole_s = f"{head},{tail}"

    sign = "-" if neg else ""
    return f"{sign}{INR if with_symbol else ''}{whole_s}.{frac:02d}"


def patch_components_money() -> None:
    """Monkeypatch components._money so every existing view shows ₹ without edits.

    Call once at the top of main() AFTER importing components.
    """
    import components
    components._money = lambda value: inr(value)
    # Also patch a few direct users if present
    for mod_name in ("views.records", "views.accounts", "views.budgets",
                     "views.analysis", "views.bills"):
        try:
            mod = __import__(mod_name, fromlist=["*"])
        except ImportError:
            continue
        if hasattr(mod, "_money"):
            mod._money = lambda value: inr(value)


# ============================================================
# 2.  UNLIMITED CATEGORIES — auto icon + color, no cap
# ============================================================

CATEGORY_ICON_POOL = [
    "🍔", "🛒", "🚕", "💡", "📱", "🏠", "💊", "🎬", "✈️", "🎁",
    "📚", "👕", "⛽", "☕", "🍕", "🎵", "🐾", "💼", "💰", "🏦",
    "🧾", "🎓", "🏋️", "🚿", "🧴", "🍺", "🎮", "🧸", "🔧", "💳",
]

CATEGORY_COLOR_POOL = [
    "#EF5350", "#EC407A", "#AB47BC", "#5C6BC0", "#29B6F6",
    "#26A69A", "#66BB6A", "#FFA726", "#FF7043", "#8D6E63",
    "#78909C", "#7E57C2", "#42A5F5", "#26C6DA", "#9CCC65",
]


def _next_icon() -> str:
    n = len(db.list_categories())
    return CATEGORY_ICON_POOL[n % len(CATEGORY_ICON_POOL)]


def _next_color() -> str:
    n = len(db.list_categories())
    return CATEGORY_COLOR_POOL[n % len(CATEGORY_COLOR_POOL)]


def add_category_unlimited(name: str, type_: str = "expense",
                           icon: str | None = None,
                           color: str | None = None) -> int:
    """Insert a category with no limit on how many exist.

    Auto-picks icon + color from the pools if not given.
    Returns the new category id. Raises ValueError on empty/duplicate name.
    """
    name = (name or "").strip()
    if not name:
        raise ValueError("Category name cannot be empty.")
    if type_ not in ("expense", "income"):
        raise ValueError("Type must be 'expense' or 'income'.")

    # Allow duplicates? No — surface a friendly error.
    for c in db.list_categories(type_):
        if c["name"].strip().lower() == name.lower():
            raise ValueError(f"Category '{name}' already exists.")

    return db.add_category(name, type_, icon or _next_icon(), color or _next_color())


def bulk_add_categories(spec: Iterable[str], type_: str = "expense") -> list[int]:
    """Add many categories in one call. Skips duplicates silently."""
    ids = []
    for name in spec:
        try:
            ids.append(add_category_unlimited(name, type_))
        except ValueError:
            continue
    return ids

def open_add_category_dialog(page: ft.Page, on_saved=None, prefill: dict | None = None) -> None:
    """Ready-made dialog that lets the user add or edit a category with no cap."""
    name_field = ft.TextField(
        label="Category name",
        autofocus=True,
        value=prefill["name"] if prefill else "",
    )
    type_toggle = ft.CupertinoSegmentedButton(
        selected_index=1 if (prefill and prefill.get("type") == "income") else 0,
        controls=[ft.Text("Expense"), ft.Text("Income")],
    )

    def close(e=None):
        page.pop_dialog()

    def save(e):
        type_ = "expense" if type_toggle.selected_index == 0 else "income"
        try:
            add_category_unlimited(name_field.value, type_)
        except ValueError as ex:
            page.show_dialog(ft.SnackBar(ft.Text(str(ex)), bgcolor=ft.Colors.RED_400))
            return
        close()
        if on_saved:
            on_saved()

    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=ft.Text("Edit Category" if prefill else "Create Category"),
        content=ft.Column(tight=True, width=300, controls=[type_toggle, name_field]),
        actions=[
            ft.TextButton("Cancel", on_click=close),
            ft.FilledButton("Save", on_click=save),
        ],
    ))


# ============================================================
# 3.  OFFLINE PDF / CSV STATEMENT IMPORT
# ============================================================

_DATE_RE = re.compile(
    r"\b(\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}|\d{4}[-/.]\d{1,2}[-/.]\d{1,2})\b"
)
_AMOUNT_RE = re.compile(r"[-+]?\d[\d,]*\.?\d{0,2}")
_SKIP_WORDS = re.compile(
    r"\b(opening|closing|balance|total|statement|page|account|ifsc|branch|"
    r"narration|particulars|withdrawal|deposit|debit|credit|date)\b",
    re.IGNORECASE,
)


def _norm_date(raw: str) -> str:
    """Best-effort: return ISO yyyy-mm-dd from common formats."""
    for sep in ("/", "-", "."):
        if sep in raw:
            parts = raw.split(sep)
            break
    else:
        return dt.date.today().isoformat()

    try:
        a, b, c = (int(p) for p in parts)
    except ValueError:
        return dt.date.today().isoformat()

    if a > 31:                 # yyyy-mm-dd
        y, m, d = a, b, c
    elif c > 31:               # dd-mm-yyyy
        d, m, y = a, b, c
    else:                      # dd-mm-yy
        d, m, y = a, b, 2000 + c
    try:
        return dt.date(y, m, d).isoformat()
    except ValueError:
        return dt.date.today().isoformat()


def _extract_rows_from_text(text: str) -> list[dict]:
    """Regex-scan a blob of text for (date, description, amount) rows."""
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line or len(line) < 8:
            continue
        dm = _DATE_RE.search(line)
        if not dm:
            continue
        # Skip header lines
        if _SKIP_WORDS.search(line) and len(line) < 60:
            continue
        amounts = _AMOUNT_RE.findall(line)
        if not amounts:
            continue
        # Last number on line is usually the transaction amount
        amt_raw = amounts[-1].replace(",", "")
        try:
            amt = Decimal(amt_raw)
        except InvalidOperation:
            continue
        if amt == 0:
            continue
        desc = _DATE_RE.sub("", line)
        desc = desc.replace(amounts[-1], "").strip(" -|.")
        rows.append({
            "date": _norm_date(dm.group(1)),
            "description": desc[:100] or "Imported",
            "amount": abs(amt),
            "type": "income" if amt > 0 and "cr" in line.lower() else "expense",
        })
    return rows


def parse_statement_pdf(path: str | Path, ocr_fallback: bool = True) -> list[dict]:
    """Extract transactions from a bank-statement PDF, fully offline.

    Strategy:
      1. pdfplumber text layer (fast, exact for digital statements)
      2. pytesseract OCR (optional, only if step 1 yields nothing and ocr_fallback=True)
    Returns a list of {date, description, amount, type}.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    text = ""
    try:
        import pdfplumber
        with pdfplumber.open(path) as pdf:
            text = "\n".join((p.extract_text() or "") for p in pdf.pages)
    except ImportError:
        raise RuntimeError("Install pdfplumber:  pip install pdfplumber")
    except Exception:
        text = ""

    rows = _extract_rows_from_text(text) if text else []

    if not rows and ocr_fallback:
        rows = _ocr_pdf(path)

    return rows


def _ocr_pdf(path: Path) -> list[dict]:
    """OCR fallback for scanned PDFs. Free but slower; requires pytesseract + Poppler."""
    try:
        import pytesseract
        from pdf2image import convert_from_path
    except ImportError:
        return []
    try:
        pages = convert_from_path(str(path), dpi=200)
    except Exception:
        return []
    text = "\n".join(pytesseract.image_to_string(p) for p in pages)
    return _extract_rows_from_text(text)


def import_statement(path: str | Path, account_id: int,
                     default_category_name: str = "Imported") -> dict:
    """Parse a PDF/CSV and insert rows into the DB. Returns a summary dict.

    Categories named 'Imported' are auto-created once and reused.
    """
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        rows = parse_statement_pdf(path)
    elif path.suffix.lower() == ".csv":
        rows = _read_csv_rows(path)
    else:
        raise ValueError("Only PDF and CSV are supported offline.")

    # Ensure the fallback category exists
    cat_id = None
    for c in db.list_categories():
        if c["name"].lower() == default_category_name.lower():
            cat_id = c["id"]
            break
    if cat_id is None:
        cat_id = add_category_unlimited(default_category_name, "expense")

    inserted, skipped = 0, 0
    for r in rows:
        try:
            db.add_transaction(
                amount=r["amount"],
                type_=r["type"],
                category_id=cat_id,
                account_id=account_id,
                date=r["date"],
                note=r["description"][:120],
            )
            inserted += 1
        except Exception:
            skipped += 1

    return {"inserted": inserted, "skipped": skipped,
            "parsed": len(rows), "file": path.name}


def _read_csv_rows(path: Path) -> list[dict]:
    import csv
    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date_raw = (row.get("date") or row.get("Date") or "").strip()
            amt_raw = (row.get("amount") or row.get("Amount") or "0").replace(",", "")
            desc = (row.get("note") or row.get("description") or "").strip()
            if not date_raw or not amt_raw:
                continue
            try:
                amt = Decimal(amt_raw)
            except InvalidOperation:
                continue
            rows.append({
                "date": _norm_date(date_raw),
                "description": desc or "Imported",
                "amount": abs(amt),
                "type": "income" if amt > 0 and "income" in row.get("type", "").lower() else "expense",
            })
    return rows


def open_import_dialog(page: ft.Page, on_done=None) -> None:
    """Ready-made dialog: pick account + drop a PDF/CSV path, import offline."""
    accounts = db.list_accounts()
    if not accounts:
        page.show_dialog(ft.SnackBar(ft.Text("Add an account first."),
                                     bgcolor=ft.Colors.RED_400))
        return

    account_dd = ft.Dropdown(
        label="Into account",
        options=[ft.DropdownOption(str(a["id"]), a["name"]) for a in accounts],
        value=str(accounts[0]["id"]),
    )
    path_field = ft.TextField(label="PDF or CSV path",
                              hint_text=r"C:\Users\you\statement.pdf")
    status = ft.Text("", size=12, color=ft.Colors.GREY_600)

    def close(e=None):
        page.pop_dialog()

    def run(e):
        status.value = "Parsing offline…"
        page.update()
        try:
            summary = import_statement(path_field.value.strip(),
                                       int(account_dd.value))
            status.value = (f"Parsed {summary['parsed']} rows · "
                            f"inserted {summary['inserted']} · "
                            f"skipped {summary['skipped']}")
            status.color = ft.Colors.GREEN_700
            if on_done:
                on_done()
        except Exception as ex:
            status.value = f"Error: {ex}"
            status.color = ft.Colors.RED_400
        page.update()

    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=ft.Text("Import Statement (offline)"),
        content=ft.Column(tight=True, width=380,
                          controls=[account_dd, path_field, status]),
        actions=[
            ft.TextButton("Cancel", on_click=close),
            ft.FilledButton("Import", on_click=run),
        ],
    ))


# ============================================================
# 4.  UI POLISH — shared widgets for the enhanced screens
# ============================================================

def card(content: ft.Control, padding: int = 14) -> ft.Container:
    return ft.Container(
        padding=padding,
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, ft.Colors.GREY_200),
        border_radius=14,
        content=content,
    )


def chip(text: str, color: str) -> ft.Container:
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=20,
        bgcolor=color,
        content=ft.Text(text, size=11, color=ft.Colors.WHITE,
                        weight=ft.FontWeight.W_600),
    )


def empty_state(message: str) -> ft.Control:
    return ft.Container(
        padding=30,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.INBOX_OUTLINED, size=40, color=ft.Colors.GREY_400),
                ft.Text(message, size=13, color=ft.Colors.GREY_500,
                        italic=True, text_align=ft.TextAlign.CENTER),
            ],
        ),
    )


def rupee_stat(expense: Decimal, income: Decimal) -> ft.Control:
    """Replacement for components.stat_header that shows ₹."""
    total = income - expense
    total_color = ft.Colors.GREEN_600 if total >= 0 else ft.Colors.RED_400

    def col(label: str, value: Decimal, color: str):
        return ft.Column(expand=True,
                         horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                         controls=[
                             ft.Text(label, size=11, color=ft.Colors.GREY_600,
                                     weight=ft.FontWeight.W_600),
                             ft.Text(inr(value), size=16,
                                     weight=ft.FontWeight.BOLD, color=color),
                         ])

    return card(ft.Row(controls=[
        col("EXPENSE", expense, ft.Colors.RED_400),
        col("INCOME", income, ft.Colors.GREEN_600),
        col("TOTAL", total, total_color),
    ]))