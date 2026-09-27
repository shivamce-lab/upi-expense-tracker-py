"""Light/dark semantic color palettes for MyMoney."""

import flet as ft
import db


LIGHT = {
    "bg": ft.Colors.WHITE,
    "surface": ft.Colors.GREY_50,
    "border": ft.Colors.GREY_200,
    "text": ft.Colors.BLACK,
    "muted": ft.Colors.GREY_600,
    "icon": ft.Colors.GREY_700,
    "primary": ft.Colors.BLUE_700,
    "on_primary": ft.Colors.WHITE,
    "danger": ft.Colors.RED_700,
    "success": ft.Colors.GREEN_700,
    "mode": ft.ThemeMode.LIGHT,
}


DARK = {
    "bg": ft.Colors.GREY_900,
    "surface": ft.Colors.GREY_800,
    "border": ft.Colors.GREY_700,
    "text": ft.Colors.WHITE,
    "muted": ft.Colors.GREY_400,
    "icon": ft.Colors.GREY_300,
    "primary": ft.Colors.BLUE_400,
    "on_primary": ft.Colors.BLACK,
    "danger": ft.Colors.RED_400,
    "success": ft.Colors.GREEN_400,
    "mode": ft.ThemeMode.DARK,
}


def get_palette() -> dict:
    """Return the currently selected theme palette."""
    return (
        DARK
        if db.get_setting("theme", "light") == "dark"
        else LIGHT
    )


def apply_theme(page: ft.Page) -> dict:
    """Apply saved theme to the page."""
    palette = get_palette()

    page.theme_mode = palette["mode"]
    page.bgcolor = palette["bg"]

    return palette


def toggle_theme(page: ft.Page) -> dict:
    """Toggle light/dark mode and apply it."""
    current = db.get_setting("theme", "light")

    new_theme = "dark" if current == "light" else "light"

    db.set_setting("theme", new_theme)

    palette = get_palette()

    page.theme_mode = palette["mode"]
    page.bgcolor = palette["bg"]

    return palette


if __name__ == "__main__":
    assert LIGHT["mode"] == ft.ThemeMode.LIGHT
    assert DARK["mode"] == ft.ThemeMode.DARK
    print("Theme OK")