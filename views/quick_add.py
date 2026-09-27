"""Quick Add screen: 6 most-used categories as big tap targets, then a number pad."""
from decimal import Decimal, InvalidOperation

import flet as ft

import components
import db


class QuickAddView:
    """Builds the Quick Add screen (top categories -> number pad -> save)."""

    def __init__(self, page: ft.Page, on_saved=None) -> None:
        self.page = page
        self.on_saved = on_saved
        self.container = ft.Container(expand=True, bgcolor=ft.Colors.WHITE)
        self.selected_category: dict | None = None
        self.entered = "0"

    def build(self) -> ft.Container:
        """Build (or rebuild) the Quick Add screen content."""
        self.container.content = self._build_body()
        return self.container

    def _refresh(self) -> None:
        self.container.content = self._build_body()
        self.page.update()

    def _top_categories(self) -> list[dict]:
        """Return the 6 expense categories with the most transactions (fallback: first 6)."""
        txns = db.list_transactions()
        counts: dict[int, int] = {}
        for t in txns:
            if t["type"] == "expense" and t.get("category_id"):
                counts[t["category_id"]] = counts.get(t["category_id"], 0) + 1
        cats = {c["id"]: c for c in db.list_categories("expense")}
        ranked = sorted(cats.values(), key=lambda c: counts.get(c["id"], 0), reverse=True)
        return ranked[:6]

    def _build_body(self) -> ft.Control:
        if self.selected_category is None:
            cats = self._top_categories()
            if not cats:
                grid = components.empty_state("Add an expense category first.")
            else:
                tiles = []
                for c in cats:
                    tiles.append(
                        ft.Container(
                            width=100, height=100, bgcolor=c["color"], border_radius=16,
                            alignment=ft.alignment.center,
                            content=ft.Column(
                                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                controls=[ft.Text(c["icon"], size=28), ft.Text(c["name"], size=12, color=ft.Colors.WHITE)],
                            ),
                            on_click=lambda e, cat=c: self._pick_category(cat),
                        )
                    )
                grid = ft.Row(wrap=True, spacing=12, run_spacing=12, controls=tiles)
            return ft.Column(
                scroll=ft.ScrollMode.AUTO, expand=True, spacing=16,
                controls=[ft.Text("Quick Add", size=22, weight=ft.FontWeight.BOLD), grid],
            )

        return self._numpad_view()

    def _pick_category(self, category: dict) -> None:
        self.selected_category = category
        self.entered = "0"
        self._refresh()

    def _numpad_view(self) -> ft.Control:
        display = ft.Text(f"${self.entered}", size=32, weight=ft.FontWeight.BOLD)

        def press(digit: str) -> None:
            if digit == "." and "." in self.entered:
                return
            if self.entered == "0" and digit != ".":
                self.entered = digit
            else:
                self.entered += digit
            display.value = f"${self.entered}"
            self.page.update()

        def backspace(e: ft.ControlEvent) -> None:
            self.entered = self.entered[:-1] or "0"
            display.value = f"${self.entered}"
            self.page.update()

        def save(e: ft.ControlEvent) -> None:
            try:
                amount = Decimal(self.entered)
                if amount <= 0:
                    raise InvalidOperation
            except InvalidOperation:
                components.show_error(self.page, "Enter a valid amount.")
                return
            accounts = db.list_accounts()
            if not accounts:
                components.show_error(self.page, "Add an account first.")
                return
            import datetime as dt

            db.add_transaction(amount, "expense", self.selected_category["id"], accounts[0]["id"], dt.date.today().isoformat())
            components.show_info(self.page, f"Added {amount} to {self.selected_category['name']}.")
            self.selected_category = None
            self.entered = "0"
            self._refresh()
            if self.on_saved:
                self.on_saved()

        keys = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"], [".", "0", "⌫"]]
        rows = []
        for row in keys:
            buttons = []
            for k in row:
                if k == "⌫":
                    buttons.append(ft.IconButton(icon=ft.Icons.BACKSPACE_OUTLINED, on_click=backspace))
                else:
                    buttons.append(ft.ElevatedButton(k, width=70, height=56, on_click=lambda e, d=k: press(d)))
            rows.append(ft.Row(alignment=ft.MainAxisAlignment.CENTER, controls=buttons))

        return ft.Column(
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=16,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Row(
                    controls=[
                        ft.IconButton(icon=ft.Icons.ARROW_BACK, on_click=lambda e: self._back()),
                        ft.Text(f"{self.selected_category['icon']} {self.selected_category['name']}", size=16, weight=ft.FontWeight.BOLD),
                    ]
                ),
                display,
                *rows,
                ft.FilledButton("Save", on_click=save, width=200),
            ],
        )

    def _back(self) -> None:
        self.selected_category = None
        self._refresh()


if __name__ == "__main__":
    print("OK")