"""Shared reusable widgets and constants for MyMoney views."""

from decimal import Decimal

import flet as ft

import theme


CATEGORY_COLOR_PALETTE = [
    "#EF5350", "#EC407A", "#AB47BC", "#5C6BC0",
    "#29B6F6", "#26A69A", "#FFA726", "#8D6E63",
]


def show_error(page: ft.Page, message: str) -> None:
    """Surface an error to the user via a shared SnackBar helper."""
    palette = theme.get_palette()

    page.show_dialog(
        ft.SnackBar(
            content=ft.Text(
                message,
                color=palette["on_primary"],
            ),
            bgcolor=palette["danger"],
        )
    )


def show_info(
    page: ft.Page,
    message: str,
    color: str | None = None,
) -> None:
    """Surface a non-error message to the user via SnackBar."""
    palette = theme.get_palette()

    page.show_dialog(
        ft.SnackBar(
            content=ft.Text(
                message,
                color=palette["on_primary"],
            ),
            bgcolor=color or palette["success"],
        )
    )


def _money(value: Decimal) -> str:
    """Format a Decimal as ₹X.XX."""
    return f"₹{value:,.2f}"


def stat_header(
    expense: Decimal,
    income: Decimal,
) -> ft.Control:
    """Three-column EXPENSE / INCOME / TOTAL stat row."""

    palette = theme.get_palette()
    total = income - expense

    def col(
        label: str,
        value: Decimal,
        color: str,
    ) -> ft.Control:
        return ft.Column(
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Text(
                    label,
                    size=11,
                    color=palette["muted"],
                    weight=ft.FontWeight.W_600,
                ),
                ft.Text(
                    _money(value),
                    size=16,
                    weight=ft.FontWeight.BOLD,
                    color=color,
                ),
            ],
        )

    total_color = (
        palette["success"]
        if total >= 0
        else palette["danger"]
    )

    return ft.Container(
        padding=ft.Padding.symmetric(
            vertical=14,
            horizontal=8,
        ),
        bgcolor=palette["surface"],
        border=ft.Border.all(
            1,
            palette["border"],
        ),
        border_radius=12,
        content=ft.Row(
            controls=[
                col(
                    "EXPENSE",
                    expense,
                    palette["danger"],
                ),
                col(
                    "INCOME",
                    income,
                    palette["success"],
                ),
                col(
                    "TOTAL",
                    total,
                    total_color,
                ),
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
    """A single transaction-style row."""

    palette = theme.get_palette()

    color = category.get("color") or CATEGORY_COLOR_PALETTE[0]
    icon = category.get("icon") or "❓"
    name = category.get("name") or "Uncategorized"

    amount_color = (
        palette["danger"]
        if type_ == "expense"
        else palette["success"]
    )

    sign = "-" if type_ == "expense" else "+"

    row_content = ft.Row(
        controls=[
            ft.CircleAvatar(
                bgcolor=color,
                content=ft.Text(
                    icon,
                    size=16,
                ),
                radius=18,
            ),

            ft.Column(
                spacing=0,
                expand=True,
                controls=[
                    ft.Text(
                        name,
                        size=14,
                        weight=ft.FontWeight.W_600,
                        color=palette["text"],
                    ),
                    ft.Text(
                        account_label,
                        size=11,
                        color=palette["muted"],
                    ),
                ],
            ),

            ft.Text(
                f"{sign}{_money(amount)}",
                size=14,
                weight=ft.FontWeight.BOLD,
                color=amount_color,
            ),
        ]
    )

    gesture = ft.GestureDetector(
        content=ft.Container(
            content=row_content,
            padding=ft.Padding.symmetric(
                vertical=8,
                horizontal=4,
            ),
        ),
        on_tap=on_click,
        on_long_press_start=(
            lambda e: on_long_press()
            if on_long_press
            else None
        ),
    )

    return gesture


def section_title(text: str) -> ft.Control:
    """Standard section title text."""

    palette = theme.get_palette()

    return ft.Text(
        text,
        size=13,
        weight=ft.FontWeight.BOLD,
        color=palette["text"],
    )


def pill(text: str, color: str) -> ft.Control:
    """A small colored pill/chip control."""

    palette = theme.get_palette()

    return ft.Container(
        padding=ft.Padding.symmetric(
            horizontal=10,
            vertical=4,
        ),
        border_radius=20,
        bgcolor=color,
        content=ft.Text(
            text,
            size=11,
            color=palette["on_primary"],
            weight=ft.FontWeight.W_600,
        ),
    )


def empty_state(message: str) -> ft.Control:
    """Placeholder shown when a screen has zero rows."""

    palette = theme.get_palette()

    return ft.Container(
        padding=30,
        alignment=ft.Alignment.CENTER,
        content=ft.Column(
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            controls=[
                ft.Icon(
                    ft.Icons.INBOX_OUTLINED,
                    size=40,
                    color=palette["muted"],
                ),
                ft.Text(
                    message,
                    size=13,
                    color=palette["muted"],
                    italic=True,
                    text_align=ft.TextAlign.CENTER,
                ),
            ],
        ),
    )