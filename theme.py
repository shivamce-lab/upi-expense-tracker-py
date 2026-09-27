"""Light/dark semantic color palettes for MyMoney, persisted via settings['theme']."""
import flet as ft

import db

LIGHT = {
    "bg": ft.Colors.WHITE,
    "surface": ft.Colors.GREY_50,
    "border": ft.Colors.GREY_200,
    "text": ft.Colors.BLACK,
    "muted": ft.Colors.GREY_600,
    "mode": ft.ThemeMode.LIGHT,
}

DARK = {
    "bg": ft.Colors.GREY_900,
    "surface": ft.Colors.GREY_800,
    "border": ft.Colors.GREY_700,
    "text": ft.Colors.WHITE,
    "muted": ft.Colors.GREY_400,
    "mode": ft.ThemeMode.DARK,
}


def get_palette() -> dict:
    """Return the currently persisted palette dict (LIGHT or DARK)."""
    return DARK if db.get_setting("theme", "light") == "dark" else LIGHT


def toggle_theme(page: ft.Page) -> dict:
    """Flip the persisted theme, apply it to the page, and return the new palette."""
    current = db.get_setting("theme", "light")
    new = "dark" if current == "light" else "light"
    db.set_setting("theme", new)
    palette = get_palette()
    page.theme_mode = palette["mode"]
    page.bgcolor = palette["bg"]
    page.update()
    return palette


def apply_theme(page: ft.Page) -> dict:
    """Apply the persisted theme to the page on load, return the palette."""
    palette = get_palette()
    page.theme_mode = palette["mode"]
    page.bgcolor = palette["bg"]
    return palette


if __name__ == "__main__":
    assert LIGHT["mode"] == ft.ThemeMode.LIGHT
    assert DARK["mode"] == ft.ThemeMode.DARK
    print("OK")