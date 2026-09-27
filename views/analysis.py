"""Analysis screen: expense pie/legend, insights, plus weekly, monthly, and 6-month charts."""
import calendar
import datetime as dt
from decimal import Decimal

import flet as ft

import components
import db
from services import charts
from services import insights as insights_service


class AnalysisView:
    """Builds the Analysis screen, refreshed each time it becomes active."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page

    def build(self) -> ft.Container:
        """Build the Analysis screen content."""
        today = dt.date.today()
        year, month = today.year, today.month
        last_day = calendar.monthrange(year, month)[1]
        start = f"{year:04d}-{month:02d}-01"
        end = f"{year:04d}-{month:02d}-{last_day:02d}"

        cats = db.category_totals(start, end)
        total = sum((c["total"] for c in cats), Decimal("0.00"))

        legend_rows: list[ft.Control] = []
        if not cats:
            legend_rows.append(components.empty_state("No expenses recorded this month yet."))
        else:
            for c in cats:
                pct = float(c["total"] / total) * 100 if total else 0
                legend_rows.append(
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Row(spacing=8, controls=[
                                        ft.CircleAvatar(bgcolor=c["color"], radius=8),
                                        ft.Text(c["name"], size=13),
                                    ]),
                                    ft.Text(f"-${c['total']:,.2f}   {pct:.0f}%", size=12, color=ft.Colors.RED_400),
                                ],
                            ),
                            ft.ProgressBar(value=pct / 100, color=c["color"], bgcolor=ft.Colors.GREY_100, height=4),
                        ],
                    )
                )

        # AI insight lines (pure-Python stats, fully offline by default)
        try:
            insight_lines = insights_service.generate_insights(year, month)
        except Exception:
            insight_lines = ["Insights unavailable right now."]

        insight_controls = [
            ft.Container(
                padding=10, bgcolor=ft.Colors.BLUE_50, border_radius=10,
                content=ft.Text(f"💡 {line}", size=13),
            )
            for line in insight_lines
        ]

        deep_insight_row: list[ft.Control] = []
        if insights_service.has_ai_key():
            deep_insight_row.append(
                ft.OutlinedButton(
                    "Deep Insight (uses your saved API key, needs internet)",
                    icon=ft.Icons.AUTO_AWESOME,
                    on_click=lambda e: components.show_info(
                        self.page, "Deep Insight is optional and calls your configured provider directly; not wired to a live call in this offline-first build."
                    ),
                )
            )

        body = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=22,
            controls=[
                ft.Text("Analysis", size=22, weight=ft.FontWeight.BOLD),
                components.section_title("INSIGHTS"),
                ft.Column(spacing=8, controls=insight_controls),
                *deep_insight_row,
                components.section_title("EXPENSE OVERVIEW"),
                charts.category_pie(start, end),
                ft.Column(spacing=10, controls=legend_rows),
                components.section_title("This week"),
                charts.weekly_bar(),
                components.section_title("This month"),
                charts.monthly_line(),
                components.section_title("Last 6 months"),
                charts.month_over_month(),
            ],
        )

        return ft.Container(
            expand=True, bgcolor=ft.Colors.WHITE,
            padding=ft.Padding.symmetric(horizontal=16, vertical=10), content=body,
        )