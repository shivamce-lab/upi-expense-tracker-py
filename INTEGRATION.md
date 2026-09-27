# MyMoney P3 Integration Guide

Apply these in order. `db.py` was already delivered in full earlier in this
session with every P3 table (`recurring`, `transaction_splits`, `merchant_map`,
`splits`, `inbox_messages`) plus their `add_*`/`list_*`/`update_*`/`delete_*`
helpers, `all_settings()`, `add_split_transaction`, `merchant_totals`,
`add_person_split`/`list_person_splits`/`set_split_settled`, and
`add_inbox_message`/`list_inbox_messages`/`mark_inbox_parsed`. No further edits
to `db.py` are needed beyond that version.

## 1. Drop in new files
Copy every file from this conversation into place:
theme.py
services/subscriptions.py
services/recurring.py
services/networth.py
services/classify.py
services/ocr.py
services/voice.py
services/inbox.py
services/split.py
services/report.py
services/backup.py
services/insights.py
views/subscriptions.py
views/networth.py
views/calendar_view.py
views/capture.py
views/split_screen.py
views/settings.py
views/lock.py
views/onboarding.py

Replace the existing `main.py`, `views/records.py`, `views/analysis.py`,
`views/accounts.py`, and `views/categories.py` with the versions above.

## 2. `enhancements.py` assumption
`views/categories.py` now calls `enhancements.open_add_category_dialog(page, on_saved, prefill=None)`.
Since `enhancements.py`'s public contract must not change and its current
source wasn't provided in this session, confirm it exposes a function with
that name/signature (per the original brief, `enhancements.py` already
supports "unlimited categories"). If its actual signature differs, adjust the
one call site in `views/categories.py._open_add_dialog`/`open_edit_dialog` —
nothing else depends on it.

## 3. Install optional extras (all free/permissive; app degrades gracefully without them)

pip install pytesseract Pillow # receipt OCR (services/ocr.py)
pip install vosk # voice capture (services/voice.py) + download a small model
pip install pdfplumber pdf2image # only if you extend io_utils/statement import to parse PDFs

Every service checks `is_available()` and shows a SnackBar with the install
hint instead of crashing when a package is missing.

## 4. Runtime wiring already done in `main.py`
- `db.init_db()` + `seed_defaults()` run first, as before.
- `services.inbox.ingest_inbox_file()` runs once on start to pull in any
  `inbox.txt` dropped into `FLET_APP_STORAGE_DATA` by a share-sheet-style flow.
- `services.recurring.run_due_all()` runs once on start, inserting any due
  `recurring` and `subscription` transactions and rolling `next_date` forward.
- `theme.apply_theme(page)` applies the persisted light/dark palette before
  anything is drawn.
- `views.lock.is_locked()` gates the whole app behind `views/lock.py` if
  `settings['passcode_hash']` is set; on unlock it proceeds to onboarding/shell.
- `views.onboarding.is_onboarded()` gates first-run behind the 3-step
  `views/onboarding.py` flow; on completion it calls back into the normal shell.
- The header's hamburger icon opens a `ft.NavigationDrawer` with Subscriptions,
  Net Worth, Calendar, Capture, Split Bills, and Settings — these five screens
  are intentionally *not* on the 5-slot `NavigationBar` per the original P0
  contract, so they live in the drawer instead.
- `views/capture.py`'s OCR/voice/inbox flows call back into
  `RecordsView.open_add_dialog_prefill(prefill)`, a new, additive method on
  `RecordsView` (the original `open_add_dialog()` is untouched) that pre-fills
  amount/date/note/category before the user confirms and saves.

## 5. Manual verification (no build meter / dev screen in this build)
Each new module has a `if __name__ == "__main__":` self-test. Run them individually, e.g.:

python -m services.classify
python -m services.recurring
python -m services.networth
python -m services.insights
python -m services.backup
python -m services.split
python -m services.report
python -m views.lock

Each should print `OK`. Then launch the app normally:

cd mymoney
pip install flet plyer
flet run main.py

and walk through: onboarding (first run) → Records add/edit/transfer →
Analysis insights → Budgets → Accounts (Net Worth card + CSV import) →
Categories → drawer → Subscriptions/Net Worth/Calendar/Capture/Split
Bills/Settings (theme toggle, passcode, encrypted backup/restore).