"""Accounts screen: total balance header, month expense/income, net worth card, account cards, import."""
import datetime as dt
from decimal import Decimal, InvalidOperation

import flet as ft

import components
import db
from services import networth as networth_service
from services import io_utils


class AccountsView:
    """Builds and manages the Accounts screen, Add Account dialog, and CSV import."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.container = ft.Container(expand=True, bgcolor=ft.Colors.WHITE)
        self.import_picker = ft.FilePicker()
        page.services.append(self.import_picker)

    def build(self) -> ft.Container:
        """Build (or rebuild) the Accounts screen content."""
        self.container.content = self._build_body()
        return self.container

    def _refresh(self) -> None:
        self.container.content = self._build_body()
        self.page.update()

    def _build_body(self) -> ft.Control:
        accounts = db.list_accounts()
        total_balance = sum((a["balance"] for a in accounts), Decimal("0.00"))

        today = dt.date.today()
        month_totals = db.month_totals(today.year, today.month)

        header = ft.Column(
            spacing=2,
            controls=[
                ft.Text("All Accounts", size=12, color=ft.Colors.GREY_600),
                ft.Text(f"${total_balance:,.2f}", size=26, weight=ft.FontWeight.BOLD),
            ],
        )

        sub_stats = ft.Row(
            controls=[
                ft.Column(expand=True, controls=[
                    ft.Text("EXPENSE SO FAR", size=11, color=ft.Colors.GREY_600),
                    ft.Text(f"${month_totals['expense']:,.2f}", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400),
                ]),
                ft.Column(expand=True, controls=[
                    ft.Text("INCOME SO FAR", size=11, color=ft.Colors.GREY_600),
                    ft.Text(f"${month_totals['income']:,.2f}", size=15, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600),
                ]),
            ]
        )

        # Net Worth compact card
        nw = networth_service.compute_networth()
        networth_card = ft.Container(
            padding=14, bgcolor=ft.Colors.GREY_50, border_radius=12,
            content=ft.Column(
                spacing=6,
                controls=[
                    ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                        ft.Text("NET WORTH", size=11, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_600),
                        ft.Text(f"${nw['net_worth']:,.2f}", size=16, weight=ft.FontWeight.BOLD,
                                color=ft.Colors.GREEN_600 if nw["net_worth"] >= 0 else ft.Colors.RED_400),
                    ]),
                    ft.Row(controls=[
                        ft.Text(f"You own {nw['own_pct']:.0f}%", size=11, color=ft.Colors.GREEN_600, expand=True),
                        ft.Text(f"You owe {nw['owe_pct']:.0f}%", size=11, color=ft.Colors.RED_400),
                    ]),
                    ft.ProgressBar(value=nw["own_pct"] / 100 if nw["own_pct"] else 0, color=ft.Colors.GREEN_400, bgcolor=ft.Colors.RED_200, height=6),
                ],
            ),
        )

        account_cards: list[ft.Control] = []
        if not accounts:
            account_cards.append(components.empty_state("No accounts yet. Add one to get started."))
        else:
            icon_map = {"Wallet": "👛", "Card": "💳", "Bank": "🏦", "Cash": "💵"}
            for a in accounts:
                last_date = db.last_transaction_date(a["id"]) or "—"
                account_cards.append(
                    ft.Container(
                        padding=12, border=ft.Border.all(1, ft.Colors.GREY_200), border_radius=12,
                        content=ft.Row(controls=[
                            ft.CircleAvatar(bgcolor=ft.Colors.BLUE_50, content=ft.Text(icon_map.get(a["type"], "💰")), radius=18),
                            ft.Column(expand=True, spacing=0, controls=[
                                ft.Text(a["name"], size=14, weight=ft.FontWeight.W_600),
                                ft.Text(f"Last: {last_date}", size=11, color=ft.Colors.GREY_600),
                            ]),
                            ft.Text(f"${a['balance']:,.2f}", size=14, weight=ft.FontWeight.BOLD),
                        ]),
                    )
                )

        add_button = ft.Button(content="ADD NEW ACCOUNT", icon=ft.Icons.ADD, on_click=lambda e: self.open_add_dialog())
        import_button = ft.OutlinedButton("IMPORT STATEMENT (CSV)", icon=ft.Icons.UPLOAD_FILE, on_click=lambda e: self.page.run_task(self._pick_import_file))

        return ft.Column(
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=18,
            controls=[
                ft.Container(padding=ft.Padding.only(left=16, right=16, top=10), content=header),
                ft.Container(padding=ft.Padding.symmetric(horizontal=16), content=sub_stats),
                ft.Container(padding=ft.Padding.symmetric(horizontal=16), content=networth_card),
                ft.Container(padding=ft.Padding.symmetric(horizontal=16), content=ft.Row(controls=[add_button, import_button], wrap=True)),
                ft.Container(padding=ft.Padding.symmetric(horizontal=16), content=ft.Column(spacing=10, controls=account_cards)),
            ],
        )

    async def _pick_import_file(self) -> None:
        result = await self.import_picker.pick_files(allow_multiple=False, allowed_extensions=["csv"])
        if not result:
            return
        path = result[0].path
        try:
            inserted, skipped = io_utils.import_csv(path)
            components.show_info(self.page, f"Imported {inserted} transaction(s), skipped {skipped}.")
        except Exception as ex:
            components.show_error(self.page, f"Import failed: {ex}")
        self._refresh()

    def open_add_dialog(self) -> None:
        """Open the Add Account dialog."""
        name_field = ft.TextField(label="Name")
        type_dropdown = ft.Dropdown(
            label="Type",
            options=[ft.DropdownOption("Wallet"), ft.DropdownOption("Card"), ft.DropdownOption("Bank"), ft.DropdownOption("Cash")],
            value="Wallet",
        )
        balance_field = ft.TextField(label="Opening balance", value="0", keyboard_type=ft.KeyboardType.NUMBER)

        def close_dialog(e: ft.ControlEvent | None = None) -> None:
            dialog.open = False
            self.page.update()

        def save(e: ft.ControlEvent) -> None:
            if not name_field.value or not name_field.value.strip():
                components.show_error(self.page, "Enter an account name.")
                return
            try:
                opening = Decimal(balance_field.value.strip() or "0")
            except InvalidOperation:
                components.show_error(self.page, "Enter a valid opening balance.")
                return
            try:
                db.add_account(name_field.value.strip(), type_dropdown.value, opening)
            except Exception as ex:
                components.show_error(self.page, f"Could not add account: {ex}")
                return
            close_dialog()
            self._refresh()

        dialog = ft.AlertDialog(
            modal=True, title=ft.Text("Add account"),
            content=ft.Column(tight=True, width=300, controls=[name_field, type_dropdown, balance_field]),
            actions=[ft.TextButton("Cancel", on_click=close_dialog), ft.FilledButton("Save", on_click=save)],
        )
        self.page.open(dialog)


if __name__ == "__main__":
    print("OK")