"""Subscriptions screen: per-subscription cards with next renewal and cycle progress."""
import datetime as dt
from decimal import Decimal, InvalidOperation

import flet as ft

import components
import db
from services import subscriptions as subs_service


class SubscriptionsView:
    """Builds and manages the Subscriptions screen (backed by services.subscriptions)."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.container = ft.Container(expand=True, bgcolor=ft.Colors.WHITE)

    def build(self) -> ft.Container:
        """Build (or rebuild) the Subscriptions screen content."""
        self.container.content = self._build_body()
        return self.container

    def refresh(self) -> None:
        """Rebuild content and update the page."""
        self.container.content = self._build_body()
        self.page.update()

    def _build_body(self) -> ft.Control:
        subs = subs_service.list_subscriptions()
        total_monthly = subs_service.total_monthly_spend()

        cards: list[ft.Control] = []
        if not subs:
            cards.append(components.empty_state("No subscriptions tracked yet. Tap + to add one."))
        else:
            for s in subs:
                bar_color = ft.Colors.RED_400 if s["days_left"] <= 2 else ft.Colors.BLUE_400
                cards.append(
                    ft.Container(
                        padding=14,
                        border=ft.Border.all(1, ft.Colors.GREY_200),
                        border_radius=12,
                        content=ft.Column(
                            spacing=6,
                            controls=[
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(s["name"], size=14, weight=ft.FontWeight.W_600),
                                        ft.PopupMenuButton(
                                            icon=ft.Icons.MORE_VERT,
                                            items=[
                                                ft.PopupMenuItem(
                                                    content="Cancel subscription",
                                                    on_click=lambda e, sid=s["id"]: self._cancel(sid),
                                                ),
                                            ],
                                        ),
                                    ],
                                ),
                                ft.Text(f"Next renewal: {s['next_date']} ({s['days_left']}d)", size=12, color=ft.Colors.GREY_600),
                                ft.ProgressBar(value=s["progress"], color=bar_color, bgcolor=ft.Colors.GREY_100, height=6),
                                ft.Row(
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    controls=[
                                        ft.Text(f"Monthly: ₹{s['monthly_cost']:,.2f}", size=11, color=ft.Colors.GREY_600),
                                        ft.Text(f"Yearly: ₹{s['yearly_cost']:,.2f}", size=11, color=ft.Colors.GREY_600),
                                    ],
                                ),
                            ],
                        ),
                    )
                )

        summary = ft.Container(
            padding=14,
            bgcolor=ft.Colors.GREY_50,
            border_radius=12,
            content=ft.Row(
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                controls=[
                    ft.Text("Total monthly cost", size=13, color=ft.Colors.GREY_700),
                    ft.Text(f"₹{total_monthly:,.2f}", size=16, weight=ft.FontWeight.BOLD),
                ],
            ),
        )

        body = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=16,
            controls=[
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Text("Subscriptions", size=22, weight=ft.FontWeight.BOLD),
                        ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE, on_click=lambda e: self.open_add_dialog()),
                    ],
                ),
                summary,
                ft.Column(spacing=10, controls=cards),
            ],
        )
        return ft.Container(
            expand=True, bgcolor=ft.Colors.WHITE,
            padding=ft.Padding.symmetric(horizontal=16, vertical=10), content=body,
        )

    def _cancel(self, sub_id: int) -> None:
        try:
            subs_service.cancel_subscription(sub_id)
            components.show_info(self.page, "Subscription cancelled.")
        except Exception as ex:
            components.show_error(self.page, f"Could not cancel: {ex}")
        self.refresh()

    def open_add_dialog(self) -> None:
        """Open the Add Subscription dialog."""
        name_field = ft.TextField(label="Name (e.g. Netflix)")
        amount_field = ft.TextField(label="Amount", keyboard_type=ft.KeyboardType.NUMBER)
        cats = db.list_categories("expense")
        category_dropdown = ft.Dropdown(
            label="Category",
            options=[ft.DropdownOption(str(c["id"]), c["name"]) for c in cats],
            value=str(cats[0]["id"]) if cats else None,
        )
        accounts = db.list_accounts()
        account_dropdown = ft.Dropdown(
            label="Account",
            options=[ft.DropdownOption(str(a["id"]), a["name"]) for a in accounts],
            value=str(accounts[0]["id"]) if accounts else None,
        )
        cycle_dropdown = ft.Dropdown(
            label="Cycle",
            options=[ft.DropdownOption("weekly", "Weekly"), ft.DropdownOption("monthly", "Monthly"), ft.DropdownOption("yearly", "Yearly")],
            value="monthly",
        )

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
            try:
                subs_service.add_subscription(
                    name_field.value.strip(), amount, int(category_dropdown.value),
                    int(account_dropdown.value), cycle_dropdown.value,
                )
            except Exception as ex:
                components.show_error(self.page, f"Could not add subscription: {ex}")
                return
            close_dialog()
            self.refresh()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add Subscription"),
            content=ft.Column(tight=True, width=320, controls=[name_field, amount_field, category_dropdown, account_dropdown, cycle_dropdown]),
            actions=[ft.TextButton("Cancel", on_click=close_dialog), ft.FilledButton("Save", on_click=save)],
        )
        self.page.show_dialog(dialog)


if __name__ == "__main__":
    print("OK")