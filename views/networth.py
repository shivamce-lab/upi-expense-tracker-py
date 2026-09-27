"""Net Worth screen: assets vs liabilities donut and a plain-English debt-check line."""
import flet as ft

import components
from services import networth


class NetWorthView:
    """Builds the Net Worth screen."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.container = ft.Container(expand=True, bgcolor=ft.Colors.WHITE)

    def build(self) -> ft.Container:
        """Build (or rebuild) the Net Worth screen content."""
        self.container.content = self._build_body()
        return self.container

    def refresh(self) -> None:
        """Rebuild content and update the page (call after accounts change)."""
        self.container.content = self._build_body()
        self.page.update()

    def _build_body(self) -> ft.Control:
        nw = networth.compute_networth()
        assets, liabilities, net_worth = nw["assets"], nw["liabilities"], nw["net_worth"]
        own_pct, owe_pct = nw["own_pct"], nw["owe_pct"]

        if assets == 0 and liabilities == 0:
            donut = components.empty_state("Add accounts to see your net worth.")
        else:
            donut = ft.PieChart(
                sections=[
                    ft.PieChartSection(
                        value=float(assets) or 0.01, title=f"{own_pct:.0f}%", color=ft.Colors.GREEN_400,
                        radius=60, title_style=ft.TextStyle(color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                    ),
                    ft.PieChartSection(
                        value=float(liabilities) or 0.01, title=f"{owe_pct:.0f}%", color=ft.Colors.RED_400,
                        radius=60, title_style=ft.TextStyle(color=ft.Colors.WHITE, size=12, weight=ft.FontWeight.BOLD),
                    ),
                ],
                sections_space=2, center_space_radius=45, height=220,
            )

        debt_line = networth.debt_check_line()

        body = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=18,
            controls=[
                ft.Text("Net Worth", size=22, weight=ft.FontWeight.BOLD),
                ft.Text(
                    f"₹{net_worth:,.2f}", size=30, weight=ft.FontWeight.BOLD,
                    color=ft.Colors.GREEN_600 if net_worth >= 0 else ft.Colors.RED_400,
                ),
                ft.Row(
                    controls=[
                        ft.Column(expand=True, controls=[
                            ft.Text("You own", size=11, color=ft.Colors.GREY_600),
                            ft.Text(f"₹{assets:,.2f} · {own_pct:.0f}%", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_600),
                        ]),
                        ft.Column(expand=True, controls=[
                            ft.Text("You owe", size=11, color=ft.Colors.GREY_600),
                            ft.Text(f"₹{liabilities:,.2f} · {owe_pct:.0f}%", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.RED_400),
                        ]),
                    ]
                ),
                donut,
                ft.Container(
                    padding=12, bgcolor=ft.Colors.GREY_50, border_radius=10,
                    content=ft.Text(debt_line, size=13, italic=True),
                ),
            ],
        )
        return ft.Container(
            expand=True, bgcolor=ft.Colors.WHITE,
            padding=ft.Padding.symmetric(horizontal=16, vertical=10), content=body,
        )


if __name__ == "__main__":
    print("OK")