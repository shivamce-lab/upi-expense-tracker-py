"""Subscriptions screen: per-subscription cards with next renewal and cycle progress."""
import datetime as dt
from decimal import Decimal, InvalidOperation

import flet as ft

import components
import db

CYCLE_DAYS = {"weekly": 7, "monthly": 30, "yearly": 365}


class SubscriptionsView:
    """Builds and manages the Subscriptions screen (backed by the recurring table)."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.container = ft.Container(expand=True, bgcolor=ft.Colors.WHITE)

    def build(self) -> ft.Container:
        """Build (or rebuild) the Subscriptions screen content."""
        self.container.content = self._build_body()
        return self.container

    def _refresh(self) -> None:
        self.container.content = self._build_body()
        self.page.update()

    def _build_body(self) -> ft.Control:
        subs = db.list_recurring(kind="subscription")
        cards: list[ft.Control] = []
        if not subs:
            cards.append(components.empty_state("No subscriptions tracked yet. Tap + to add one."))
        else:
            today = dt.date.today()
            for s in subs:
                next_date = dt.date.fromisoformat(s["next_date"])
                days_in_cycle = CYCLE_DAYS.get(s["cycle"], 30)
                days_left = (next_date - today).days
                progress = max(0.0, min(1.0, 1 - (days_left / days_in_cycle))) if days_in_cycle else 0.0
                monthly_cost = s["amount"] if s["cycle"] == "monthly" else (
                    s["amount"] * 12 / 1 if s["cycle"] == "yearly" else s["amount"] * 4
                )
                yearly_cost = s["amount"] * (365 / days_in_cycle) if days_in_cycle else s["amount"]
                cards.append(
                    ft.Container(
                        padding=14, border=ft.Border.all(1, ft.Colors.GREY_200), border_radius=12,
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                                    ft.Text(s["name"], size=14, weight=ft.FontWeight.W_600),
                                    ft.Text(f"${s['amount']:,.2f}/{s['cycle']}", size=12, color=ft.Colors.GREY_600),
                                ]),
                                ft.Text(f"Next renewal: {s['next_date']}", size=12, color=ft.Colors.GREY_600),
                                ft.ProgressBar(value=progress, color=ft.Colors.BLUE_400, bgcolor=ft.Colors.GREY_100, height=6),
                                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                                    ft.Text(f"Monthly: ${monthly_cost:,.2f}", size=11, color=ft.Colors.GREY_600),
                                    ft.Text(f"Yearly: ${yearly_cost:,.2f}", size=11, color=ft.Colors.GREY_600),
                                ]),
                            ],
                        ),
                    )
                )

        body = ft.Column(
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=16,
            controls=[
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                    ft.Text("Subscriptions", size=22, weight=ft.FontWeight.BOLD),
                    ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE, on_click=lambda e: self.open_add_dialog()),
                ]),
                ft.Column(spacing=10, controls=cards),
            ],
        )
        return ft.Container(expand=True, bgcolor=ft.Colors.WHITE, padding=ft.Padding.symmetric(horizontal=16, vertical=10), content=body)

    def open_add_dialog(self) -> None:
        """Open the Add Subscription dialog."""
        name_field = ft.TextField(label="Name (e.g. Netflix)")
        amount_field = ft.TextField(label="Amount", keyboard_type=ft.KeyboardType.NUMBER)
        cats = db.list_categories("expense")
        category_dropdown = ft.Dropdown(label="Category", options=[ft.DropdownOption(str(c["id"]), c["name"]) for c in cats],
                                         value=str(cats[0]["id"]) if cats else None)
        accounts = db.list_accounts()
        account_dropdown = ft.Dropdown(label="Account", options=[ft.DropdownOption(str(a["id"]), a["name"]) for a in accounts],
                                        value=str(accounts[0]["id"]) if accounts else None)
        cycle_dropdown = ft.Dropdown(label="Cycle", options=[ft.DropdownOption("monthly", "Monthly"), ft.DropdownOption("yearly", "Yearly")], value="monthly")

        def close_dialog(e: ft.ControlEvent | None = None) -> None:
            dialog.open = False
            self.page.update()

        def save(e: ft.ControlEvent) -> None:
            try:
                amount = Decimal(amount_field.value.strip())
                if amount <= 0:
                    raise InvalidOperation
            except (InvalidOperation, AttributeError, ValueError):
                components.show_error(self.page, "Enter a valid amount.")
                return
            if not name_field.value or not category_dropdown.value or not account_dropdown.value:
                components.show_error(self.page, "Fill in all fields.")
                return
            next_date = dt.date.today().isoformat()
            db.add_recurring(
                name_field.value.strip(), amount, "expense", int(category_dropdown.value),
                int(account_dropdown.value), cycle_dropdown.value, next_date, kind="subscription",
            )
            close_dialog()
            self._refresh()

        dialog = ft.AlertDialog(
            modal=True, title=ft.Text("Add Subscription"),
            content=ft.Column(tight=True, width=320, controls=[name_field, amount_field, category_dropdown, account_dropdown, cycle_dropdown]),
            actions=[ft.TextButton("Cancel", on_click=close_dialog), ft.FilledButton("Save", on_click=save)],
        )
        self.page.open(dialog)


if __name__ == "__main__":
    print("OK")