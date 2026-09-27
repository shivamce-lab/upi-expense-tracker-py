"""Shared reusable widgets and constants for MyMoney views."""
from decimal import Decimal
import flet as ft
CATEGORY_COLOR_PALETTE = [
    "#EF5350", "#EC407A", "#AB47BC", "#5C6BC0",
    "#29B6F6", "#26A69A", "#FFA726", "#8D6E63",
]



def show_error(page: ft.Page, message: str) -> None:
    """Surface an error to the user via a shared SnackBar helper."""
    page.show_dialog(ft.SnackBar(content=ft.Text(message), bgcolor=ft.Colors.RED_400))



def show_info(page: ft.Page, message: str, color: str = ft.Colors.GREEN_400) -> None:
    """Surface a non-error message to the user via SnackBar."""
    page.show_dialog(ft.SnackBar(content=ft.Text(message), bgcolor=color))



def _money(value: Decimal) -> str:
    """Format a Decimal as $X.XX."""
    return f"${value:,.2f}"



def stat_header(expense: Decimal, income: Decimal) -> ft.Control:
    """Three-column EXPENSE / INCOME / TOTAL stat row."""
    total = income - expense
    def col(label: str, value: Decimal, color: str) -> ft.Control:
        return ft.Column(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(label, size=11, color=ft.Colors.GREY_600, weight=ft.FontWeight.W_600),
                ft.Text(_money(value), size=16, weight=ft.FontWeight.BOLD, color=color),
            ],
        )
    total_color = ft.Colors.GREEN_600 if total >= 0 else ft.Colors.RED_400
    return ft.Container(
        padding=ft.Padding.symmetric(vertical=14, horizontal=8),
        bgcolor=ft.Colors.WHITE,
        border=ft.Border.all(1, ft.Colors.GREY_200),
        border_radius=12,
        content=ft.Row(
            controls=[
                col("EXPENSE", expense, ft.Colors.RED_400),
                col("INCOME", income, ft.Colors.GREEN_600),
                col("TOTAL", total, total_color),
            ]
        ),
    )



def category_row(
    category: dict,
    account_label: str,
    amount: Decimal,
    type_: str,
    on_click=None,
    on_long_press=None,
) -> ft.Control:
    """A single transaction-style row: icon circle, name, account label, right-aligned amount."""
    color = category.get("color") or CATEGORY_COLOR_PALETTE[0]
    icon = category.get("icon") or "❓"
    name = category.get("name") or "Uncategorized"
    amount_color = ft.Colors.RED_400 if type_ == "expense" else ft.Colors.GREEN_600
    sign = "-" if type_ == "expense" else "+"
    row_content = ft.Row(
        controls=[
            ft.CircleAvatar(bgcolor=color, content=ft.Text(icon, size=16), radius=18),
            ft.Column(
                spacing=0,
                expand=True,
                controls=[
                    ft.Text(name, size=14, weight=ft.FontWeight.W_600),
                    ft.Text(account_label, size=11, color=ft.Colors.GREY_600),
                ],
            ),
            ft.Text(f"{sign}{_money(amount)}", size=14, weight=ft.FontWeight.BOLD, color=amount_color),
        ]
    )
    gesture = ft.GestureDetector(
        content=ft.Container(content=row_content, padding=ft.Padding.symmetric(vertical=8, horizontal=4)),
        on_tap=on_click,
        on_long_press_start=(lambda e: on_long_press()) if on_long_press else None,
    )
    return gesture



def section_title(text: str) -> ft.Control:
    """Standard section title text."""
    return ft.Text(text, size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_700)



def pill(text: str, color: str) -> ft.Control:
    """A small colored pill/chip control."""
    return ft.Container(
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
        border_radius=20,
        bgcolor=color,
        content=ft.Text(text, size=11, color=ft.Colors.WHITE, weight=ft.FontWeight.W_600),
    )



def empty_state(message: str) -> ft.Control:
    """A friendly placeholder shown when a screen has zero rows to display."""
    return ft.Container(
        padding=30,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(ft.Icons.INBOX_OUTLINED, size=40, color=ft.Colors.GREY_400),
                ft.Text(message, size=13, color=ft.Colors.GREY_500, italic=True, text_align=ft.TextAlign.CENTER),
            ],
        ),
    )
