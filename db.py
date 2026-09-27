"""SQLite data access layer for MyMoney. All DB access must go through this module."""
import calendar
import datetime as dt
import os
import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

DB_PATH = Path(os.getenv("FLET_APP_STORAGE_DATA", Path.home() / ".mymoney")) / "mymoney.db"


def to_decimal(value: Any) -> Decimal:
    """Convert a DB REAL/str/None value to a Decimal quantized to 2 places."""
    if value is None:
        value = 0
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def from_decimal(value: Decimal) -> float:
    """Convert a Decimal to the float SQLite will store, via str() to avoid binary artifacts."""
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return float(str(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)))


def get_conn() -> sqlite3.Connection:
    """Open (and lazily create) the SQLite connection for the MyMoney database."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """Create all tables (P0-P3) if they do not already exist."""
    conn = get_conn()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY, name TEXT, type TEXT, balance REAL DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY, name TEXT, type TEXT, icon TEXT, color TEXT
            );
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY, amount REAL, type TEXT, category_id INTEGER,
                account_id INTEGER, date TEXT, note TEXT, created_at TEXT,
                from_account_id INTEGER, to_account_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY, category_id INTEGER, period TEXT,
                limit_amount REAL, start_date TEXT, end_date TEXT
            );
            CREATE TABLE IF NOT EXISTS bills (
                id INTEGER PRIMARY KEY, name TEXT, amount REAL, category_id INTEGER,
                account_id INTEGER, due_date TEXT, cycle TEXT DEFAULT 'monthly',
                last_paid TEXT, active INTEGER DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);

            -- P3 tables
            CREATE TABLE IF NOT EXISTS recurring (
                id INTEGER PRIMARY KEY, name TEXT, amount REAL, type TEXT,
                category_id INTEGER, account_id INTEGER, cycle TEXT,
                next_date TEXT, last_run TEXT, active INTEGER DEFAULT 1,
                kind TEXT DEFAULT 'recurring'
            );
            CREATE TABLE IF NOT EXISTS transaction_splits (
                id INTEGER PRIMARY KEY, txn_id INTEGER, category_id INTEGER, amount REAL
            );
            CREATE TABLE IF NOT EXISTS merchant_map (
                merchant_key TEXT PRIMARY KEY, category_id INTEGER
            );
            CREATE TABLE IF NOT EXISTS splits (
                id INTEGER PRIMARY KEY, txn_id INTEGER, person TEXT,
                share REAL, settled INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS inbox_messages (
                id INTEGER PRIMARY KEY, raw_text TEXT, parsed INTEGER DEFAULT 0,
                created_at TEXT
            );
            """
        )
        conn.commit()
        _migrate_columns(conn)
    finally:
        conn.close()


def _migrate_columns(conn: sqlite3.Connection) -> None:
    """Add columns to pre-existing tables created by earlier app versions."""
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(transactions)").fetchall()}
    if "from_account_id" not in cols:
        conn.execute("ALTER TABLE transactions ADD COLUMN from_account_id INTEGER")
    if "to_account_id" not in cols:
        conn.execute("ALTER TABLE transactions ADD COLUMN to_account_id INTEGER")
    conn.commit()


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convert a sqlite3.Row into a plain dict."""
    return {k: row[k] for k in row.keys()}


def _apply_account_delta(conn: sqlite3.Connection, account_id: int, delta: Decimal) -> None:
    """Adjust an account's balance by delta (positive or negative)."""
    row = conn.execute("SELECT balance FROM accounts WHERE id = ?", (account_id,)).fetchone()
    if row is None:
        return
    new_balance = to_decimal(row["balance"]) + delta
    conn.execute("UPDATE accounts SET balance = ? WHERE id = ?", (from_decimal(new_balance), account_id))


# ---------------------------------------------------------------- transactions

def add_transaction(
    amount: Decimal, type_: str, category_id: int | None, account_id: int | None, date: str,
    note: str = "", from_account_id: int | None = None, to_account_id: int | None = None,
) -> int:
    """Insert a transaction (expense/income/transfer), update balances, return new row id."""
    amount = to_decimal(amount)
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO transactions (amount, type, category_id, account_id, date, note, created_at, "
            "from_account_id, to_account_id) VALUES (?,?,?,?,?,?,?,?,?)",
            (from_decimal(amount), type_, category_id, account_id, date, note,
             dt.datetime.now().isoformat(timespec="seconds"), from_account_id, to_account_id),
        )
        if type_ == "transfer":
            _apply_account_delta(conn, from_account_id, -amount)
            _apply_account_delta(conn, to_account_id, amount)
        else:
            delta = amount if type_ == "income" else -amount
            _apply_account_delta(conn, account_id, delta)
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def add_split_transaction(
    total_amount: Decimal, account_id: int, date: str, note: str,
    splits: list[tuple[int, Decimal]],
) -> int:
    """Insert an expense transaction whose amount is split across several categories."""
    total_amount = to_decimal(total_amount)
    primary_cat = splits[0][0] if splits else None
    txn_id = add_transaction(total_amount, "expense", primary_cat, account_id, date, note)
    conn = get_conn()
    try:
        for cat_id, amt in splits:
            conn.execute(
                "INSERT INTO transaction_splits (txn_id, category_id, amount) VALUES (?,?,?)",
                (txn_id, cat_id, from_decimal(to_decimal(amt))),
            )
        conn.commit()
    finally:
        conn.close()
    return txn_id


def list_transaction_splits(txn_id: int) -> list[dict]:
    """Return the category splits for a transaction."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT ts.*, c.name AS category_name FROM transaction_splits ts "
            "LEFT JOIN categories c ON c.id = ts.category_id WHERE ts.txn_id = ?", (txn_id,),
        ).fetchall()
        out = []
        for r in rows:
            d = _row_to_dict(r)
            d["amount"] = to_decimal(d["amount"])
            out.append(d)
        return out
    finally:
        conn.close()


def list_transactions(start: str | None = None, end: str | None = None) -> list[dict]:
    """Return transactions (optionally filtered to [start, end] inclusive dates), newest first."""
    conn = get_conn()
    try:
        query = (
            "SELECT t.*, c.name AS category_name, c.icon AS category_icon, c.color AS category_color, "
            "a.name AS account_name FROM transactions t "
            "LEFT JOIN categories c ON c.id = t.category_id "
            "LEFT JOIN accounts a ON a.id = t.account_id"
        )
        params: list[Any] = []
        clauses = []
        if start is not None:
            clauses.append("t.date >= ?")
            params.append(start)
        if end is not None:
            clauses.append("t.date <= ?")
            params.append(end)
        if clauses:
            query += " WHERE " + " AND ".join(clauses)
        query += " ORDER BY t.date DESC, t.id DESC"
        rows = conn.execute(query, params).fetchall()
        result = []
        for row in rows:
            d = _row_to_dict(row)
            d["amount"] = to_decimal(d["amount"])
            result.append(d)
        return result
    finally:
        conn.close()


def update_transaction(id_: int, **fields: Any) -> None:
    """Update arbitrary columns of a transaction by id, keeping account balances consistent."""
    conn = get_conn()
    try:
        old_row = conn.execute("SELECT * FROM transactions WHERE id = ?", (id_,)).fetchone()
        if old_row is None:
            return
        old = _row_to_dict(old_row)
        old_amount = to_decimal(old["amount"])
        if old["type"] == "transfer":
            _apply_account_delta(conn, old["from_account_id"], old_amount)
            _apply_account_delta(conn, old["to_account_id"], -old_amount)
        else:
            old_delta = old_amount if old["type"] == "income" else -old_amount
            _apply_account_delta(conn, old["account_id"], -old_delta)

        new = dict(old)
        for k, v in fields.items():
            new[k] = v
        new_amount = to_decimal(new["amount"])

        conn.execute(
            "UPDATE transactions SET amount=?, type=?, category_id=?, account_id=?, date=?, note=?, "
            "from_account_id=?, to_account_id=? WHERE id=?",
            (from_decimal(new_amount), new["type"], new["category_id"], new["account_id"], new["date"],
             new.get("note", ""), new.get("from_account_id"), new.get("to_account_id"), id_),
        )
        if new["type"] == "transfer":
            _apply_account_delta(conn, new["from_account_id"], -new_amount)
            _apply_account_delta(conn, new["to_account_id"], new_amount)
        else:
            new_delta = new_amount if new["type"] == "income" else -new_amount
            _apply_account_delta(conn, new["account_id"], new_delta)
        conn.commit()
    finally:
        conn.close()


def delete_transaction(id_: int) -> None:
    """Delete a transaction by id and reverse its effect on account balance(s)."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM transactions WHERE id = ?", (id_,)).fetchone()
        if row is None:
            return
        d = _row_to_dict(row)
        amount = to_decimal(d["amount"])
        if d["type"] == "transfer":
            _apply_account_delta(conn, d["from_account_id"], amount)
            _apply_account_delta(conn, d["to_account_id"], -amount)
        else:
            delta = amount if d["type"] == "income" else -amount
            _apply_account_delta(conn, d["account_id"], -delta)
        conn.execute("DELETE FROM transactions WHERE id = ?", (id_,))
        conn.execute("DELETE FROM transaction_splits WHERE txn_id = ?", (id_,))
        conn.execute("DELETE FROM splits WHERE txn_id = ?", (id_,))
        conn.commit()
    finally:
        conn.close()


# -------------------------------------------------------------------- totals

def month_totals(year: int, month: int) -> dict:
    """Return {expense, income, total} Decimal totals for the given calendar month (excludes transfers)."""
    last_day = calendar.monthrange(year, month)[1]
    start = f"{year:04d}-{month:02d}-01"
    end = f"{year:04d}-{month:02d}-{last_day:02d}"
    return _range_totals(start, end)


def week_totals(start_date: str) -> dict:
    """Return {expense, income, total} Decimal totals for the 7-day window starting at start_date."""
    start = dt.date.fromisoformat(start_date)
    end = start + dt.timedelta(days=6)
    return _range_totals(start.isoformat(), end.isoformat())


def _range_totals(start: str, end: str) -> dict:
    """Internal: sum expense/income (excluding transfers) within an inclusive date range."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT type, SUM(amount) AS total FROM transactions WHERE date >= ? AND date <= ? "
            "AND type IN ('expense','income') GROUP BY type",
            (start, end),
        ).fetchall()
        expense = Decimal("0.00")
        income = Decimal("0.00")
        for row in rows:
            if row["type"] == "expense":
                expense = to_decimal(row["total"])
            elif row["type"] == "income":
                income = to_decimal(row["total"])
        return {"expense": expense, "income": income, "total": income - expense}
    finally:
        conn.close()


def daily_totals(start: str, end: str) -> list[dict]:
    """Return one dict per calendar day in [start, end]: {date, expense, income}."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT date, type, SUM(amount) AS total FROM transactions "
            "WHERE date >= ? AND date <= ? AND type IN ('expense','income') GROUP BY date, type",
            (start, end),
        ).fetchall()
        by_date: dict[str, dict] = {}
        d0 = dt.date.fromisoformat(start)
        d1 = dt.date.fromisoformat(end)
        cur = d0
        while cur <= d1:
            by_date[cur.isoformat()] = {"date": cur.isoformat(), "expense": Decimal("0.00"), "income": Decimal("0.00")}
            cur += dt.timedelta(days=1)
        for row in rows:
            if row["date"] in by_date:
                by_date[row["date"]][row["type"]] = to_decimal(row["total"])
        return [by_date[k] for k in sorted(by_date.keys())]
    finally:
        conn.close()


def category_totals(start: str, end: str) -> list[dict]:
    """Return per-category expense totals within [start, end]: {category_id, name, icon, color, total}."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT c.id AS category_id, c.name, c.icon, c.color, SUM(t.amount) AS total "
            "FROM transactions t JOIN categories c ON c.id = t.category_id "
            "WHERE t.date >= ? AND t.date <= ? AND t.type = 'expense' "
            "GROUP BY c.id ORDER BY total DESC",
            (start, end),
        ).fetchall()
        result = []
        for row in rows:
            d = _row_to_dict(row)
            d["total"] = to_decimal(d["total"])
            result.append(d)
        return result
    finally:
        conn.close()


def merchant_totals(start: str, end: str) -> list[dict]:
    """Return per-merchant (note text) totals within [start, end] for expenses, {note, total, count}."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT note, SUM(amount) AS total, COUNT(*) AS cnt FROM transactions "
            "WHERE date >= ? AND date <= ? AND type = 'expense' AND note != '' "
            "GROUP BY note ORDER BY total DESC",
            (start, end),
        ).fetchall()
        out = []
        for r in rows:
            out.append({"note": r["note"], "total": to_decimal(r["total"]), "count": r["cnt"]})
        return out
    finally:
        conn.close()


# ------------------------------------------------------------------- budgets

def _compute_end_date(start_date: str, period: str) -> str:
    """Internal: compute end_date from start_date + period."""
    start = dt.date.fromisoformat(start_date)
    if period == "weekly":
        end = start + dt.timedelta(days=6)
    elif period == "yearly":
        try:
            end = start.replace(year=start.year + 1) - dt.timedelta(days=1)
        except ValueError:
            end = start.replace(year=start.year + 1, day=28) - dt.timedelta(days=1)
    else:
        last_day = calendar.monthrange(start.year, start.month)[1]
        end = start.replace(day=last_day)
    return end.isoformat()


def add_budget(category_id: int, period: str, limit_amount: Decimal, start_date: str) -> int:
    """Insert a budget with an auto-computed end_date, return the new row id."""
    end_date = _compute_end_date(start_date, period)
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO budgets (category_id, period, limit_amount, start_date, end_date) VALUES (?,?,?,?,?)",
            (category_id, period, from_decimal(to_decimal(limit_amount)), start_date, end_date),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_budgets(period: str) -> list[dict]:
    """Return all budgets for the given period, joined with category info."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT b.*, c.name AS category_name, c.icon AS category_icon, c.color AS category_color "
            "FROM budgets b JOIN categories c ON c.id = b.category_id "
            "WHERE b.period = ? ORDER BY b.start_date DESC",
            (period,),
        ).fetchall()
        result = []
        for row in rows:
            d = _row_to_dict(row)
            d["limit_amount"] = to_decimal(d["limit_amount"])
            result.append(d)
        return result
    finally:
        conn.close()


def budget_status(budget_id: int) -> dict:
    """Return {limit, spent, remaining, pct} for a single budget."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT * FROM budgets WHERE id = ?", (budget_id,)).fetchone()
        if row is None:
            return {"limit": Decimal("0.00"), "spent": Decimal("0.00"), "remaining": Decimal("0.00"), "pct": 0.0}
        b = _row_to_dict(row)
        limit_amount = to_decimal(b["limit_amount"])
        spent_row = conn.execute(
            "SELECT SUM(amount) AS total FROM transactions WHERE category_id = ? AND type = 'expense' "
            "AND date >= ? AND date <= ?",
            (b["category_id"], b["start_date"], b["end_date"]),
        ).fetchone()
        spent = to_decimal(spent_row["total"]) if spent_row and spent_row["total"] is not None else Decimal("0.00")
        remaining = limit_amount - spent
        pct = float(spent / limit_amount) if limit_amount > 0 else 0.0
        return {"limit": limit_amount, "spent": spent, "remaining": remaining, "pct": pct}
    finally:
        conn.close()


# --------------------------------------------------------------------- bills

def add_bill(
    name: str, amount: Decimal, category_id: int, account_id: int, due_date: str, cycle: str = "monthly"
) -> int:
    """Insert a new active bill, return the new row id."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO bills (name, amount, category_id, account_id, due_date, cycle, last_paid, active) "
            "VALUES (?,?,?,?,?,?,NULL,1)",
            (name, from_decimal(to_decimal(amount)), category_id, account_id, due_date, cycle),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_bills() -> list[dict]:
    """Return all active bills, joined with category and account names."""
    conn = get_conn()
    try:
        rows = conn.execute(
            "SELECT b.*, c.name AS category_name, c.icon AS category_icon, c.color AS category_color, "
            "a.name AS account_name FROM bills b "
            "LEFT JOIN categories c ON c.id = b.category_id "
            "LEFT JOIN accounts a ON a.id = b.account_id "
            "WHERE b.active = 1 ORDER BY b.due_date ASC"
        ).fetchall()
        result = []
        for row in rows:
            d = _row_to_dict(row)
            d["amount"] = to_decimal(d["amount"])
            result.append(d)
        return result
    finally:
        conn.close()


def upcoming_bills(days_ahead: int = 14) -> list[dict]:
    """Return active bills whose next due date falls within days_ahead, sorted by days_left."""
    from services import reminders as _reminders
    return _reminders.upcoming_bills(days_ahead)


def mark_paid(bill_id: int) -> int:
    """Record a bill as paid: insert its transaction, update last_paid, return the new transaction id."""
    from services import reminders as _reminders
    return _reminders.mark_paid(bill_id)


def update_bill(id_: int, **fields: Any) -> None:
    """Update arbitrary columns of a bill by id."""
    if not fields:
        return
    conn = get_conn()
    try:
        cols = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values())
        if "amount" in fields:
            idx = list(fields.keys()).index("amount")
            values[idx] = from_decimal(to_decimal(fields["amount"]))
        values.append(id_)
        conn.execute(f"UPDATE bills SET {cols} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def delete_bill(id_: int) -> None:
    """Soft-delete a bill by marking it inactive."""
    conn = get_conn()
    try:
        conn.execute("UPDATE bills SET active = 0 WHERE id = ?", (id_,))
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------ accounts

def add_account(name: str, type_: str, opening_balance: Decimal = Decimal("0")) -> int:
    """Insert a new account with an opening balance, return the new row id."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO accounts (name, type, balance) VALUES (?,?,?)",
            (name, type_, from_decimal(to_decimal(opening_balance))),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_accounts() -> list[dict]:
    """Return all accounts with balances as Decimal."""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT * FROM accounts ORDER BY id ASC").fetchall()
        result = []
        for row in rows:
            d = _row_to_dict(row)
            d["balance"] = to_decimal(d["balance"])
            result.append(d)
        return result
    finally:
        conn.close()


def last_transaction_date(account_id: int) -> str | None:
    """Return the most recent transaction date for an account, or None."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT date FROM transactions WHERE account_id = ? OR from_account_id = ? OR to_account_id = ? "
            "ORDER BY date DESC LIMIT 1",
            (account_id, account_id, account_id),
        ).fetchone()
        return row["date"] if row else None
    finally:
        conn.close()


# ---------------------------------------------------------------- categories

def add_category(name: str, type_: str, icon: str, color: str) -> int:
    """Insert a new category, return the new row id."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO categories (name, type, icon, color) VALUES (?,?,?,?)", (name, type_, icon, color),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_categories(type_: str | None = None) -> list[dict]:
    """Return categories, optionally filtered by type ('income' | 'expense')."""
    conn = get_conn()
    try:
        if type_ is None:
            rows = conn.execute("SELECT * FROM categories ORDER BY id ASC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM categories WHERE type = ? ORDER BY id ASC", (type_,)).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def update_category(id_: int, **fields: Any) -> None:
    """Update arbitrary columns of a category by id."""
    if not fields:
        return
    conn = get_conn()
    try:
        cols = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [id_]
        conn.execute(f"UPDATE categories SET {cols} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def delete_category(id_: int) -> None:
    """Delete a category by id."""
    conn = get_conn()
    try:
        conn.execute("DELETE FROM categories WHERE id = ?", (id_,))
        conn.commit()
    finally:
        conn.close()


# ----------------------------------------------------------------- settings

def set_setting(key: str, value: str) -> None:
    """Upsert a settings key/value pair."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
        conn.commit()
    finally:
        conn.close()


def get_setting(key: str, default: str | None = None) -> str | None:
    """Return the value for a settings key, or default if unset."""
    conn = get_conn()
    try:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default
    finally:
        conn.close()


def all_settings() -> dict:
    """Return all settings key/value pairs as a plain dict."""
    conn = get_conn()
    try:
        rows = conn.execute("SELECT key, value FROM settings").fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        conn.close()


# ----------------------------------------------------------------- recurring

def add_recurring(
    name: str, amount: Decimal, type_: str, category_id: int | None, account_id: int,
    cycle: str, next_date: str, kind: str = "recurring",
) -> int:
    """Insert a recurring rule (salary/rent/SIP/subscription), return new row id."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO recurring (name, amount, type, category_id, account_id, cycle, next_date, "
            "last_run, active, kind) VALUES (?,?,?,?,?,?,?,NULL,1,?)",
            (name, from_decimal(to_decimal(amount)), type_, category_id, account_id, cycle, next_date, kind),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_recurring(kind: str | None = None) -> list[dict]:
    """Return active recurring rules, optionally filtered by kind ('recurring'|'subscription')."""
    conn = get_conn()
    try:
        if kind is None:
            rows = conn.execute(
                "SELECT r.*, c.name AS category_name, a.name AS account_name FROM recurring r "
                "LEFT JOIN categories c ON c.id = r.category_id "
                "LEFT JOIN accounts a ON a.id = r.account_id WHERE r.active = 1 ORDER BY r.next_date ASC"
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT r.*, c.name AS category_name, a.name AS account_name FROM recurring r "
                "LEFT JOIN categories c ON c.id = r.category_id "
                "LEFT JOIN accounts a ON a.id = r.account_id WHERE r.active = 1 AND r.kind = ? "
                "ORDER BY r.next_date ASC",
                (kind,),
            ).fetchall()
        out = []
        for row in rows:
            d = _row_to_dict(row)
            d["amount"] = to_decimal(d["amount"])
            out.append(d)
        return out
    finally:
        conn.close()


def update_recurring(id_: int, **fields: Any) -> None:
    """Update arbitrary columns of a recurring rule by id."""
    if not fields:
        return
    conn = get_conn()
    try:
        cols = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values())
        if "amount" in fields:
            idx = list(fields.keys()).index("amount")
            values[idx] = from_decimal(to_decimal(fields["amount"]))
        values.append(id_)
        conn.execute(f"UPDATE recurring SET {cols} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()


def delete_recurring(id_: int) -> None:
    """Soft-delete a recurring rule by marking it inactive."""
    conn = get_conn()
    try:
        conn.execute("UPDATE recurring SET active = 0 WHERE id = ?", (id_,))
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------- merchant map

def set_merchant_category(merchant_key: str, category_id: int) -> None:
    """Learn/update the preferred category for a merchant key (used by services.classify)."""
    conn = get_conn()
    try:
        conn.execute(
            "INSERT INTO merchant_map (merchant_key, category_id) VALUES (?,?) "
            "ON CONFLICT(merchant_key) DO UPDATE SET category_id = excluded.category_id",
            (merchant_key, category_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_merchant_category(merchant_key: str) -> int | None:
    """Return the learned category id for a merchant key, or None."""
    conn = get_conn()
    try:
        row = conn.execute(
            "SELECT category_id FROM merchant_map WHERE merchant_key = ?", (merchant_key,)
        ).fetchone()
        return row["category_id"] if row else None
    finally:
        conn.close()


# -------------------------------------------------------------- bill splits

def add_person_split(txn_id: int, person: str, share: Decimal) -> int:
    """Add a per-person share to a transaction's bill-split, return new row id."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO splits (txn_id, person, share, settled) VALUES (?,?,?,0)",
            (txn_id, person, from_decimal(to_decimal(share))),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_person_splits(txn_id: int | None = None) -> list[dict]:
    """Return person-splits, optionally filtered to one transaction."""
    conn = get_conn()
    try:
        if txn_id is None:
            rows = conn.execute("SELECT * FROM splits ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute("SELECT * FROM splits WHERE txn_id = ?", (txn_id,)).fetchall()
        out = []
        for r in rows:
            d = _row_to_dict(r)
            d["share"] = to_decimal(d["share"])
            out.append(d)
        return out
    finally:
        conn.close()


def set_split_settled(split_id: int, settled: bool) -> None:
    """Mark a person-split as settled or unsettled."""
    conn = get_conn()
    try:
        conn.execute("UPDATE splits SET settled = ? WHERE id = ?", (1 if settled else 0, split_id))
        conn.commit()
    finally:
        conn.close()


# ------------------------------------------------------------------- inbox

def add_inbox_message(raw_text: str) -> int:
    """Store a raw inbound text message for later parsing, return new row id."""
    conn = get_conn()
    try:
        cur = conn.execute(
            "INSERT INTO inbox_messages (raw_text, parsed, created_at) VALUES (?,0,?)",
            (raw_text, dt.datetime.now().isoformat(timespec="seconds")),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_inbox_messages(parsed: bool | None = None) -> list[dict]:
    """Return inbox messages, optionally filtered by parsed status."""
    conn = get_conn()
    try:
        if parsed is None:
            rows = conn.execute("SELECT * FROM inbox_messages ORDER BY id DESC").fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM inbox_messages WHERE parsed = ? ORDER BY id DESC", (1 if parsed else 0,)
            ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def mark_inbox_parsed(id_: int) -> None:
    """Mark an inbox message as parsed."""
    conn = get_conn()
    try:
        conn.execute("UPDATE inbox_messages SET parsed = 1 WHERE id = ?", (id_,))
        conn.commit()
    finally:
        conn.close()