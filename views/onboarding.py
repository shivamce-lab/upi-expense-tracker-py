"""First-run 3-step onboarding: currency, first account, first two categories."""
import flet as ft

import components
import db

EMOJI_CHOICES = ["🍔", "🧾", "🛍️", "🚗", "💊", "🎬", "💰", "💼"]


class OnboardingView:
    """Builds the 3-step onboarding flow, writes settings['onboarded'] = '1' on completion."""

    def __init__(self, page: ft.Page, on_done) -> None:
        self.page = page
        self.on_done = on_done
        self.step = 0
        self.state = {"currency": "₹", "account_name": "Wallet", "cat1": "Food", "cat2": "Salary"}

    def build(self) -> ft.Container:
        """Build the current onboarding step."""
        return ft.Container(expand=True, bgcolor=ft.Colors.WHITE, padding=24, content=self._step_content())

    def _refresh(self) -> None:
        self.page.controls.clear()
        self.page.add(self.build())
        self.page.update()

    def _step_content(self) -> ft.Control:
        if self.step == 0:
            currency_field = ft.TextField(label="Currency symbol", value=self.state["currency"], width=200)

            def next_step(e: ft.ControlEvent) -> None:
                self.state["currency"] = currency_field.value or "₹"
                self.step = 1
                self._refresh()

            return ft.Column(
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Text("Welcome to MyMoney", size=22, weight=ft.FontWeight.BOLD),
                    ft.Text("Step 1 of 3 — Choose your currency", size=13, color=ft.Colors.GREY_600),
                    currency_field,
                    ft.FilledButton("Next", on_click=next_step),
                ],
            )
        if self.step == 1:
            account_field = ft.TextField(label="First account name", value=self.state["account_name"], width=240)

            def next_step(e: ft.ControlEvent) -> None:
                self.state["account_name"] = account_field.value or "Wallet"
                self.step = 2
                self._refresh()

            return ft.Column(
                scroll=ft.ScrollMode.AUTO,
                controls=[
                    ft.Text("Step 2 of 3 — Your first account", size=16, weight=ft.FontWeight.BOLD),
                    account_field,
                    ft.FilledButton("Next", on_click=next_step),
                ],
            )

        cat1_field = ft.TextField(label="Expense category", value=self.state["cat1"], width=240)
        cat2_field = ft.TextField(label="Income category", value=self.state["cat2"], width=240)

        def finish(e: ft.ControlEvent) -> None:
            self.state["cat1"] = cat1_field.value or "Food"
            self.state["cat2"] = cat2_field.value or "Salary"
            db.set_setting("currency_symbol", self.state["currency"])
            if not db.list_accounts():
                db.add_account(self.state["account_name"], "Wallet")
            palette = components.CATEGORY_COLOR_PALETTE
            if not db.list_categories("expense"):
                db.add_category(self.state["cat1"], "expense", "🍔", palette[0])
            if not db.list_categories("income"):
                db.add_category(self.state["cat2"], "income", "💰", palette[6])
            db.set_setting("onboarded", "1")
            self.on_done()

        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            controls=[
                ft.Text("Step 3 of 3 — Your first categories", size=16, weight=ft.FontWeight.BOLD),
                cat1_field,
                cat2_field,
                ft.FilledButton("Finish", on_click=finish),
            ],
        )


def is_onboarded() -> bool:
    """Return True if onboarding has already been completed."""
    return db.get_setting("onboarded", "0") == "1"


if __name__ == "__main__":
    assert is_onboarded() in (True, False)
    print("OK")