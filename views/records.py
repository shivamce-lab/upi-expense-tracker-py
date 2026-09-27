"""Records screen: monthly transaction list, add/edit/delete dialogs, header totals."""
import calendar
import datetime as dt
from decimal import Decimal, InvalidOperation

import flet as ft

import components
import db
import state
import theme

class RecordsView:
    """Builds and manages the Records screen and its Add/Edit transaction dialog."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.palette = theme.get_palette()
        self.container = ft.Container(
        expand=True,
        bgcolor=self.palette["bg"],
        )

    def build(self) -> ft.Container:
        """Build (or rebuild) the Records screen content."""
        self.container.content = self._build_body()
        return self.container

    def _refresh(self) -> None:
        self.container.content = self._build_body()
        self.page.update()

    def _build_body(self) -> ft.Control:
        self.palette = theme.get_palette()
        year, month = state.get_month()
        totals = db.month_totals(year, month)
        month_label = dt.date(year, month, 1).strftime("%B, %Y")

        def prev_month(e: ft.ControlEvent) -> None:
            y, m = year, month - 1
            if m == 0:
                m, y = 12, y - 1
            state.set_month(y, m)
            self._refresh()

        def next_month(e: ft.ControlEvent) -> None:
            y, m = year, month + 1
            if m == 13:
                m, y = 1, y + 1
            state.set_month(y, m)
            self._refresh()

        nav = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=prev_month),
                ft.Text(month_label, size=15, weight=ft.FontWeight.W_600),
                ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=next_month),
            ],
        )

        last_day = calendar.monthrange(year, month)[1]
        start = f"{year:04d}-{month:02d}-01"
        end = f"{year:04d}-{month:02d}-{last_day:02d}"
        txns = db.list_transactions(start, end)

        list_content: ft.Control
        if not txns:
            list_content = components.empty_state("No transactions yet this month.\nTap + to add one.")
        else:
            groups: dict[str, list[dict]] = {}
            for t in txns:
                groups.setdefault(t["date"], []).append(t)

            group_controls = []
            for date_str in sorted(groups.keys(), reverse=True):
                d = dt.date.fromisoformat(date_str)
                header_text = f"{d.strftime('%b')} {d.day}, {d.strftime('%A')}"
                rows = []
                for t in groups[date_str]:
                    category = {
                        "name": t.get("category_name"),
                        "icon": t.get("category_icon"),
                        "color": t.get("category_color"),
                    }
                    is_recurring = (t.get("note") or "").startswith("Recurring:")
                    account_label = t.get("account_name") or ""
                    if t["type"] == "transfer":
                        category = {"name": "Transfer", "icon": "🔁", "color": "#5C6BC0"}
                    if is_recurring:
                        account_label = f"{account_label}  🔄"
                    rows.append(
                        components.category_row(
                            category,
                            account_label,
                            t["amount"],
                            t["type"] if t["type"] != "transfer" else "expense",
                            on_click=lambda e, tid=t["id"]: self.open_edit_dialog(tid),
                            on_long_press=lambda tid=t["id"]: self.open_delete_dialog(tid),
                        )
                    )
                group_controls.append(
                    ft.Column(
                        spacing=4,
                        controls=[
                            ft.Text(header_text, size=12, weight=ft.FontWeight.BOLD, color=self.palette["muted"]),
                            *rows,
                        ],
                    )
                )
            list_content = ft.Column(spacing=16, controls=group_controls)

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=14,
            controls=[
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=16),
                    content=components.stat_header(totals["expense"], totals["income"]),
                ),
                nav,
                ft.Container(padding=ft.Padding.symmetric(horizontal=16), content=list_content),
            ],
        )

    # ---------------------------------------------------------------- dialog

    def open_add_dialog(self) -> None:
        """Open the Add Transaction dialog (blank)."""
        self._open_txn_dialog(None, prefill=None)

    def open_add_dialog_prefill(self, prefill: dict) -> None:
        """Open the Add Transaction dialog pre-filled from OCR/voice/inbox capture.

        prefill may include: amount (str), date (str), note (str), category_id (int|None).
        This is additive — the plain open_add_dialog() contract is unchanged.
        """
        self._open_txn_dialog(None, prefill=prefill)

    def open_edit_dialog(self, txn_id: int) -> None:
        """Open the Edit Transaction dialog pre-filled for an existing transaction."""
        txns = {t["id"]: t for t in db.list_transactions()}
        txn = txns.get(txn_id)
        if txn:
            self._open_txn_dialog(txn, prefill=None)

    def _open_txn_dialog(self, txn: dict | None, prefill: dict | None) -> None:
        is_edit = txn is not None
        type_value = txn["type"] if is_edit else "expense"

        default_amount = str(txn["amount"]) if is_edit else (str(prefill.get("amount")) if prefill and prefill.get("amount") else "")
        default_note = txn.get("note", "") if is_edit else (prefill.get("note", "") if prefill else "")

        amount_field = ft.TextField(label="Amount", value=default_amount, keyboard_type=ft.KeyboardType.NUMBER)
        note_field = ft.TextField(label="Note", value=default_note)

        category_dropdown = ft.Dropdown(label="Category", options=[])
        account_dropdown = ft.Dropdown(
            label="Account",
            options=[ft.DropdownOption(str(a["id"]), a["name"]) for a in db.list_accounts()],
            value=str(txn["account_id"]) if is_edit else None,
        )

        default_date = txn["date"] if is_edit else ((prefill.get("date") if prefill else None) or dt.date.today().isoformat())
        picked_date = {"value": default_date}
        date_button = ft.TextButton(content=picked_date["value"])

        prefill_category_id = prefill.get("category_id") if prefill else None

        def refresh_categories(type_: str) -> None:
            cats = db.list_categories(type_)
            category_dropdown.options = [ft.DropdownOption(str(c["id"]), f"{c['icon']} {c['name']}") for c in cats]
            if is_edit and type_ == txn["type"]:
                category_dropdown.value = str(txn["category_id"])
            elif prefill_category_id and any(c["id"] == prefill_category_id for c in cats):
                category_dropdown.value = str(prefill_category_id)
            elif cats:
                category_dropdown.value = str(cats[0]["id"])
            else:
                category_dropdown.value = None
            self.page.update()

        type_toggle = ft.Tabs(
            selected_index=0 if type_value == "expense" else 1,
            tabs=[ft.Tab(label="Expense"), ft.Tab(label="Income")],
        )

        def type_changed(e: ft.ControlEvent) -> None:
            new_type = "expense" if type_toggle.selected_index == 0 else "income"
            refresh_categories(new_type)

        type_toggle.on_change = type_changed

        def date_picked(e: ft.ControlEvent) -> None:
            if date_picker.value:
                picked_date["value"] = date_picker.value.date().isoformat() if hasattr(date_picker.value, "date") else str(date_picker.value)[:10]
                date_button.content = picked_date["value"]
                self.page.update()

        date_picker = ft.DatePicker(on_change=date_picked)

        def open_date_picker(e: ft.ControlEvent) -> None:
            self.page.show_dialog(date_picker)

        date_button.on_click = open_date_picker

        def close_dialog(e: ft.ControlEvent | None = None) -> None:
            dialog.open = False
            self.page.update()

        def save(e: ft.ControlEvent) -> None:
            try:
                amount = Decimal(amount_field.value.strip())
                if amount <= 0:
                    raise InvalidOperation
            except (InvalidOperation, AttributeError, ValueError):
                components.show_error(self.page, "Enter a valid positive amount.")
                return
            if not category_dropdown.value or not account_dropdown.value:
                components.show_error(self.page, "Select a category and account.")
                return

            type_ = "expense" if type_toggle.selected_index == 0 else "income"
            try:
                if is_edit:
                    db.update_transaction(
                        txn["id"], amount=amount, type=type_,
                        category_id=int(category_dropdown.value), account_id=int(account_dropdown.value),
                        date=picked_date["value"], note=note_field.value or "",
                    )
                else:
                    db.add_transaction(
                        amount, type_, int(category_dropdown.value), int(account_dropdown.value),
                        picked_date["value"], note_field.value or "",
                    )
                    if note_field.value:
                        from services import classify
                        classify.learn(note_field.value, int(category_dropdown.value))
            except Exception as ex:
                components.show_error(self.page, f"Could not save transaction: {ex}")
                return

            close_dialog()
            self._refresh()

        refresh_categories(type_value)

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit Transaction" if is_edit else "Add Transaction"),
            content=ft.Column(
                tight=True, width=320,
                controls=[type_toggle, amount_field, category_dropdown, account_dropdown, date_button, note_field],
            ),
            actions=[ft.TextButton("Cancel", on_click=close_dialog), ft.FilledButton("Save", on_click=save)],
        )
        self.page.show_dialog(dialog)

    def open_delete_dialog(self, txn_id: int) -> None:
        """Open a confirmation dialog before deleting a transaction."""

        def close_dialog(e: ft.ControlEvent | None = None) -> None:
            dialog.open = False
            self.page.update()

        def confirm_delete(e: ft.ControlEvent) -> None:
            try:
                db.delete_transaction(txn_id)
            except Exception as ex:
                components.show_error(self.page, f"Could not delete: {ex}")
            close_dialog()
            self._refresh()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete transaction?"),
            content=ft.Text("This action cannot be undone."),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.TextButton("Delete", on_click=confirm_delete, style=ft.ButtonStyle(color=ft.Colors.RED_400)),
            ],
        )
        self.page.show_dialog(dialog)