"""Bills screen: upcoming bills with mark-paid, full bill list with edit/delete, add-bill dialog."""
import datetime as dt
from decimal import Decimal, InvalidOperation

import flet as ft

import components
import db
from services import reminders


class BillsView:
    """Builds and manages the Bills screen and its Add Bill dialog."""

    def __init__(self, page: ft.Page, go_back) -> None:
        self.page = page
        self.go_back = go_back
        self.container = ft.Container(expand=True, bgcolor=ft.Colors.WHITE)

    def build(self) -> ft.Container:
        """Build (or rebuild) the Bills screen content."""
        self.container.content = self._build_body()
        return self.container

    def _refresh(self) -> None:
        self.container.content = self._build_body()
        self.page.update()

    def _chip_for(self, days_left: int, overdue: bool) -> ft.Control:
        if overdue:
            return components.pill("Overdue", "#B71C1C")
        if days_left > 7:
            return components.pill(f"{days_left}d", "#43A047")
        if days_left >= 3:
            return components.pill(f"{days_left}d", "#FFA726")
        return components.pill(f"{days_left}d", "#EF5350")

    def _build_body(self) -> ft.Control:
        header = ft.Row(
            controls=[
                ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: self.go_back()),
                ft.Text("Bills", size=20, weight=ft.FontWeight.BOLD),
            ]
        )

        upcoming = reminders.upcoming_bills(14)
        upcoming_rows: list[ft.Control] = []
        if not upcoming:
            upcoming_rows.append(components.empty_state("No bills due soon."))
        else:
            for item in upcoming:
                bill = item["bill"]
                upcoming_rows.append(
                    ft.Container(
                        padding=12,
                        border=ft.Border.all(1, ft.Colors.GREY_200),
                        border_radius=12,
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(bill["name"], size=14, weight=ft.FontWeight.W_600),
                                        self._chip_for(item["days_left"], item["overdue"]),
                                    ],
                                ),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(f"${bill['amount']:,.2f}  ·  due {item['due'].isoformat()}", size=12, color=ft.Colors.GREY_600),
                                        ft.TextButton("Mark paid", on_click=lambda e, bid=bill["id"]: self._mark_paid(bid)),
                                    ],
                                ),
                            ],
                        ),
                    )
                )

        all_bills = db.list_bills()
        all_rows: list[ft.Control] = []
        if not all_bills:
            all_rows.append(components.empty_state("No bills added yet."))
        else:
            for b in all_bills:
                all_rows.append(
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Column(
                                spacing=0,
                                controls=[
                                    ft.Text(b["name"], size=14, weight=ft.FontWeight.W_600),
                                    ft.Text(f"${b['amount']:,.2f}  ·  {b['cycle']}", size=11, color=ft.Colors.GREY_600),
                                ],
                            ),
                            ft.PopupMenuButton(
                                icon=ft.Icons.MORE_VERT,
                                items=[
                                    ft.PopupMenuItem(content="Edit", on_click=lambda e, bid=b["id"]: self.open_edit_dialog(bid)),
                                    ft.PopupMenuItem(content="Delete", on_click=lambda e, bid=b["id"]: self._delete_bill(bid)),
                                ],
                            ),
                        ],
                    )
                )

        body = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=18,
            controls=[
                header,
                components.section_title("Upcoming"),
                ft.Column(spacing=10, controls=upcoming_rows),
                components.section_title("All bills"),
                ft.Column(spacing=10, controls=all_rows),
            ],
        )
        return ft.Container(padding=ft.Padding.symmetric(horizontal=16, vertical=10), content=body)

    def _mark_paid(self, bill_id: int) -> None:
        try:
            reminders.mark_paid(bill_id)
            components.show_info(self.page, "Bill marked as paid.")
        except Exception as ex:
            components.show_error(self.page, f"Could not mark bill paid: {ex}")
        self._refresh()

    def _delete_bill(self, bill_id: int) -> None:
        try:
            db.delete_bill(bill_id)
        except Exception as ex:
            components.show_error(self.page, f"Could not delete bill: {ex}")
        self._refresh()

    # ---------------------------------------------------------------- dialog

    def open_add_dialog(self) -> None:
        """Open the Add Bill dialog."""
        self._open_dialog(None)

    def open_edit_dialog(self, bill_id: int) -> None:
        """Open the edit dialog for an existing bill."""
        bills = {b["id"]: b for b in db.list_bills()}
        bill = bills.get(bill_id)
        if bill:
            self._open_dialog(bill)

    def _open_dialog(self, bill: dict | None) -> None:
        is_edit = bill is not None
        name_field = ft.TextField(label="Name", value=bill["name"] if is_edit else "")
        amount_field = ft.TextField(label="Amount", value=str(bill["amount"]) if is_edit else "", keyboard_type=ft.KeyboardType.NUMBER)

        expense_cats = db.list_categories("expense")
        category_dropdown = ft.Dropdown(
            label="Category",
            options=[ft.DropdownOption(str(c["id"]), f"{c['icon']} {c['name']}") for c in expense_cats],
            value=str(bill["category_id"]) if is_edit else (str(expense_cats[0]["id"]) if expense_cats else None),
        )
        accounts = db.list_accounts()
        account_dropdown = ft.Dropdown(
            label="Account",
            options=[ft.DropdownOption(str(a["id"]), a["name"]) for a in accounts],
            value=str(bill["account_id"]) if is_edit else (str(accounts[0]["id"]) if accounts else None),
        )
        cycle_dropdown = ft.Dropdown(
            label="Cycle",
            options=[
                ft.DropdownOption("none", "One-time"),
                ft.DropdownOption("weekly", "Weekly"),
                ft.DropdownOption("monthly", "Monthly"),
                ft.DropdownOption("yearly", "Yearly"),
            ],
            value=bill["cycle"] if is_edit else "monthly",
        )

        picked_date = {"value": bill["due_date"] if is_edit else dt.date.today().isoformat()}
        date_button = ft.TextButton(content=picked_date["value"])

        def date_picked(e: ft.ControlEvent) -> None:
            if date_picker.value:
                picked_date["value"] = date_picker.value.date().isoformat() if hasattr(date_picker.value, "date") else str(date_picker.value)[:10]
                date_button.content = picked_date["value"]
                self.page.update()

        date_picker = ft.DatePicker(on_change=date_picked)
        date_button.on_click = lambda e: self.page.show_dialog(date_picker)

        def close_dialog(e: ft.ControlEvent | None = None) -> None:
            self.page.pop_dialog()

        def save(e: ft.ControlEvent) -> None:
            if not name_field.value or not name_field.value.strip():
                components.show_error(self.page, "Enter a bill name.")
                return
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
            try:
                if is_edit:
                    db.update_bill(
                        bill["id"],
                        name=name_field.value.strip(),
                        amount=amount,
                        category_id=int(category_dropdown.value),
                        account_id=int(account_dropdown.value),
                        due_date=picked_date["value"],
                        cycle=cycle_dropdown.value,
                    )
                else:
                    db.add_bill(
                        name_field.value.strip(),
                        amount,
                        int(category_dropdown.value),
                        int(account_dropdown.value),
                        picked_date["value"],
                        cycle_dropdown.value,
                    )
            except Exception as ex:
                components.show_error(self.page, f"Could not save bill: {ex}")
                return
            close_dialog()
            self._refresh()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Edit bill" if is_edit else "Add Bill"),
            content=ft.Column(
                tight=True,
                width=320,
                controls=[name_field, amount_field, category_dropdown, account_dropdown, date_button, cycle_dropdown],
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.FilledButton("Save", on_click=save),
            ],
        )
        self.page.show_dialog(dialog)
