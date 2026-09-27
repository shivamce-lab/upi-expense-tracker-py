"""Budgets screen: period-filtered budget cards, unbudgeted categories, and new-budget dialog."""
import datetime as dt
from decimal import Decimal, InvalidOperation


import flet as ft


import components
import db




class BudgetsView:
    """Builds and manages the Budgets screen and its New Budget dialog."""


    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.container = ft.Container(expand=True, bgcolor=ft.Colors.WHITE)
        self.period = "monthly"


    def build(self) -> ft.Container:
        """Build (or rebuild) the Budgets screen content."""
        self.container.content = self._build_body()
        return self.container


    def _refresh(self) -> None:
        self.container.content = self._build_body()
        self.page.update()


    def _build_body(self) -> ft.Control:
        period_index = {"weekly": 0, "monthly": 1, "yearly": 2}[self.period]
        tabs = ft.CupertinoSegmentedButton(
            selected_index=period_index,
            controls=[ft.Text("Weekly"), ft.Text("Monthly"), ft.Text("Yearly")],
            on_change=self._period_changed,
        )


        budgets = db.list_budgets(self.period)
        statuses = [(b, db.budget_status(b["id"])) for b in budgets]


        total_budget = sum((s["limit"] for _, s in statuses), Decimal("0.00"))
        total_spent = sum((s["spent"] for _, s in statuses), Decimal("0.00"))


        summary_card = ft.Container(
            padding=16,
            bgcolor=ft.Colors.GREY_50,
            border_radius=12,
            content=ft.Row(
                controls=[
                    ft.Column(
                        expand=True,
                        controls=[
                            ft.Text("TOTAL BUDGET", size=11, color=ft.Colors.GREY_600),
                            ft.Text(f"₹{total_budget:,.2f}", size=16, weight=ft.FontWeight.BOLD),
                        ],
                    ),
                    ft.Column(
                        expand=True,
                        controls=[
                            ft.Text("TOTAL SPENT", size=11, color=ft.Colors.GREY_600),
                            ft.Text(f"₹{total_spent:,.2f}", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400),
                        ],
                    ),
                ]
            ),
        )


        month_label = dt.date.today().strftime("%b, %Y")
        budget_cards: list[ft.Control] = []
        if not statuses:
            budget_cards.append(components.empty_state("No budgets set for this period yet."))
        else:
            for b, s in statuses:
                over = s["spent"] >= s["limit"] and s["limit"] > 0
                bar_color = ft.Colors.RED_400 if over else ft.Colors.GREEN_500
                pct = min(1.0, s["pct"])
                card_controls = [
                    ft.Row(
                        controls=[
                            ft.CircleAvatar(bgcolor=b["category_color"], content=ft.Text(b["category_icon"]), radius=16),
                            ft.Text(b["category_name"], size=14, weight=ft.FontWeight.W_600, expand=True),
                        ]
                    ),
                    ft.Text(f"Limit: ₹{s['limit']:,.2f}", size=12, color=ft.Colors.GREY_700),
                    ft.Text(f"Spent: ₹{s['spent']:,.2f}", size=12, color=ft.Colors.GREY_700),
                    ft.Text(f"Remaining: ₹{s['remaining']:,.2f}", size=12, color=ft.Colors.GREY_700),
                    ft.ProgressBar(value=pct, color=bar_color, bgcolor=ft.Colors.GREY_100, height=6),
                ]
                if over:
                    card_controls.append(
                        ft.Text("Limit exceeded", size=12, italic=True, color=ft.Colors.RED_400)
                    )
                budget_cards.append(
                    ft.Container(
                        padding=14,
                        border=ft.Border.all(1, ft.Colors.GREY_200),
                        border_radius=12,
                        content=ft.Column(spacing=6, controls=card_controls),
                    )
                )


        expense_cats = db.list_categories("expense")
        budgeted_cat_ids = {b["category_id"] for b in budgets}
        unbudgeted = [c for c in expense_cats if c["id"] not in budgeted_cat_ids]


        unbudgeted_cards: list[ft.Control] = []
        if unbudgeted:
            for c in unbudgeted:
                unbudgeted_cards.append(
                    ft.Container(
                        padding=12,
                        border=ft.Border.all(1, ft.Colors.GREY_200),
                        border_radius=12,
                        content=ft.Row(
                            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            controls=[
                                ft.Row(
                                    spacing=8,
                                    controls=[
                                        ft.CircleAvatar(bgcolor=c["color"], content=ft.Text(c["icon"]), radius=14),
                                        ft.Text(c["name"], size=13),
                                    ],
                                ),
                                ft.TextButton(
                                    "SET BUDGET",
                                    on_click=lambda e, cid=c["id"]: self.open_add_dialog(preselect_category=cid),
                                ),
                            ],
                        ),
                    )
                )


        sections: list[ft.Control] = [
            tabs,
            summary_card,
            components.section_title(f"Budgeted categories: {month_label}"),
            ft.Column(spacing=10, controls=budget_cards),
        ]
        if unbudgeted_cards:
            sections.append(components.section_title("Not budgeted this month"))
            sections.append(ft.Column(spacing=10, controls=unbudgeted_cards))


        return ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=16,
            controls=[
                ft.Container(padding=ft.Padding.symmetric(horizontal=16, vertical=6), content=ft.Column(spacing=16, controls=sections))
            ],
        )


    def _period_changed(self, e: ft.ControlEvent) -> None:
        self.period = ["weekly", "monthly", "yearly"][e.control.selected_index]
        self._refresh()


    # ---------------------------------------------------------------- dialog


    def open_add_dialog(self, preselect_category: int | None = None) -> None:
        """Open the New Budget dialog, optionally pre-filled with a category."""
        expense_cats = db.list_categories("expense")
        category_dropdown = ft.Dropdown(
            label="Category",
            options=[ft.DropdownOption(str(c["id"]), f"{c['icon']} {c['name']}") for c in expense_cats],
            value=str(preselect_category) if preselect_category else (str(expense_cats[0]["id"]) if expense_cats else None),
        )
        period_dropdown = ft.Dropdown(
            label="Period",
            options=[ft.DropdownOption("weekly", "Weekly"), ft.DropdownOption("monthly", "Monthly"), ft.DropdownOption("yearly", "Yearly")],
            value=self.period,
        )
        limit_field = ft.TextField(label="Limit amount", keyboard_type=ft.KeyboardType.NUMBER)


        picked_date = {"value": dt.date.today().isoformat()}
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
            try:
                limit_amount = Decimal(limit_field.value.strip())
                if limit_amount <= 0:
                    raise InvalidOperation
            except (InvalidOperation, AttributeError, ValueError):
                components.show_error(self.page, "Enter a valid positive limit amount.")
                return
            if not category_dropdown.value:
                components.show_error(self.page, "Select a category.")
                return
            try:
                db.add_budget(
                    int(category_dropdown.value),
                    period_dropdown.value,
                    limit_amount,
                    picked_date["value"],
                )
            except Exception as ex:
                components.show_error(self.page, f"Could not save budget: {ex}")
                return
            self.period = period_dropdown.value
            close_dialog()
            self._refresh()


        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("New budget"),
            content=ft.Column(
                tight=True,
                width=320,
                controls=[category_dropdown, period_dropdown, limit_field, date_button],
            ),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.FilledButton("Save", on_click=save),
            ],
        )
        self.page.show_dialog(dialog)
