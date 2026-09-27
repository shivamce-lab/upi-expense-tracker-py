"""Calendar screen: month grid highlighting days with activity, tap a day to see its transactions."""
import calendar
import datetime as dt
from decimal import Decimal

import flet as ft

import components
import db


class CalendarView:
    """Builds a monthly calendar with per-day expense/income indicators."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.container = ft.Container(expand=True, bgcolor=ft.Colors.WHITE)
        today = dt.date.today()
        self.year, self.month = today.year, today.month
        self.selected_date: str | None = None

    def build(self) -> ft.Container:
        """Build (or rebuild) the Calendar screen content."""
        self.container.content = self._build_body()
        return self.container

    def _refresh(self) -> None:
        self.container.content = self._build_body()
        self.page.update()

    def _build_body(self) -> ft.Control:
        last_day = calendar.monthrange(self.year, self.month)[1]
        start = f"{self.year:04d}-{self.month:02d}-01"
        end = f"{self.year:04d}-{self.month:02d}-{last_day:02d}"
        daily = {d["date"]: d for d in db.daily_totals(start, end)}

        def prev_month(e: ft.ControlEvent) -> None:
            self.month -= 1
            if self.month == 0:
                self.month, self.year = 12, self.year - 1
            self.selected_date = None
            self._refresh()

        def next_month(e: ft.ControlEvent) -> None:
            self.month += 1
            if self.month == 13:
                self.month, self.year = 1, self.year + 1
            self.selected_date = None
            self._refresh()

        nav = ft.Row(
            alignment=ft.MainAxisAlignment.CENTER,
            controls=[
                ft.IconButton(icon=ft.Icons.CHEVRON_LEFT, on_click=prev_month),
                ft.Text(dt.date(self.year, self.month, 1).strftime("%B, %Y"), size=15, weight=ft.FontWeight.W_600),
                ft.IconButton(icon=ft.Icons.CHEVRON_RIGHT, on_click=next_month),
            ],
        )

        weekday_labels = ft.Row(
            controls=[ft.Container(width=44, alignment=ft.Alignment.CENTER, content=ft.Text(lbl, size=10, color=ft.Colors.GREY_500))
                      for lbl in ["S", "M", "T", "W", "T", "F", "S"]]
        )

        first_weekday = (dt.date(self.year, self.month, 1).weekday() + 1) % 7  # 0 = Sunday
        cells: list[ft.Control] = [ft.Container(width=44, height=44) for _ in range(first_weekday)]

        def pick_day(date_str: str) -> None:
            self.selected_date = date_str
            self._refresh()

        for day in range(1, last_day + 1):
            date_str = f"{self.year:04d}-{self.month:02d}-{day:02d}"
            info = daily.get(date_str)
            has_expense = info and info["expense"] > 0
            has_income = info and info["income"] > 0
            is_selected = date_str == self.selected_date

            dot_row = ft.Row(
                alignment=ft.MainAxisAlignment.CENTER,
                spacing=2,
                controls=[
                    *( [ft.Container(width=5, height=5, bgcolor=ft.Colors.RED_400, border_radius=3)] if has_expense else [] ),
                    *( [ft.Container(width=5, height=5, bgcolor=ft.Colors.GREEN_500, border_radius=3)] if has_income else [] ),
                ],
            )
            cells.append(
                ft.Container(
                    width=44, height=44, border_radius=8,
                    bgcolor=ft.Colors.BLUE_50 if is_selected else None,
                    alignment=ft.Alignment.CENTER,
                    on_click=lambda e, d=date_str: pick_day(d),
                    content=ft.Column(
                        spacing=2, horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        controls=[ft.Text(str(day), size=13, weight=ft.FontWeight.W_600 if is_selected else ft.FontWeight.NORMAL), dot_row],
                    ),
                )
            )

        grid = ft.Row(wrap=True, spacing=0, run_spacing=4, controls=cells)

        day_section: list[ft.Control] = []
        if self.selected_date:
            txns = db.list_transactions(self.selected_date, self.selected_date)
            day_section.append(components.section_title(f"Transactions on {self.selected_date}"))
            if not txns:
                day_section.append(components.empty_state("No transactions on this day."))
            else:
                rows = []
                for t in txns:
                    category = {"name": t.get("category_name"), "icon": t.get("category_icon"), "color": t.get("category_color")}
                    rows.append(components.category_row(category, t.get("account_name") or "", t["amount"], t["type"]))
                day_section.append(ft.Column(spacing=6, controls=rows))

        body = ft.Column(
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=16,
            controls=[
                ft.Text("Calendar", size=22, weight=ft.FontWeight.BOLD),
                nav, weekday_labels, grid,
                *day_section,
            ],
        )
        return ft.Container(expand=True, bgcolor=ft.Colors.WHITE, padding=ft.Padding.symmetric(horizontal=16, vertical=10), content=body)


if __name__ == "__main__":
    print("OK")