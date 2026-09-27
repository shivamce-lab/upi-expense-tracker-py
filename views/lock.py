"""Passcode lock screen shown on cold start when settings['passcode_hash'] exists."""
import hashlib
import os
import time

import flet as ft

import components
import db

_fail_count = {"n": 0}


def _hash_passcode(code: str, salt: str) -> str:
    """Hash a passcode with scrypt against the per-install salt."""
    return hashlib.scrypt(code.encode("utf-8"), salt=salt.encode("utf-8"), n=2**14, r=8, p=1, dklen=32).hex()


def ensure_salt() -> str:
    """Return the per-install passcode salt, generating one on first use."""
    salt = db.get_setting("passcode_salt")
    if not salt:
        salt = os.urandom(16).hex()
        db.set_setting("passcode_salt", salt)
    return salt


def set_passcode(code: str) -> None:
    """Hash and persist a new passcode."""
    salt = ensure_salt()
    db.set_setting("passcode_hash", _hash_passcode(code, salt))


def is_locked() -> bool:
    """Return True if a passcode has been configured."""
    return bool(db.get_setting("passcode_hash"))


def verify(code: str) -> bool:
    """Check a passcode attempt against the stored hash."""
    salt = ensure_salt()
    stored = db.get_setting("passcode_hash")
    return stored is not None and _hash_passcode(code, salt) == stored


class LockView:
    """Builds the passcode entry screen with exponential slow-down on wrong attempts."""

    def __init__(self, page: ft.Page, on_unlock) -> None:
        self.page = page
        self.on_unlock = on_unlock

    def build(self) -> ft.Container:
        """Build the lock screen content."""
        code_field = ft.TextField(label="Passcode", password=True, can_reveal_password=True, width=220)
        status = ft.Text("", color=ft.Colors.RED_400, size=12)

        def submit(e: ft.ControlEvent) -> None:
            if verify(code_field.value or ""):
                _fail_count["n"] = 0
                self.on_unlock()
            else:
                _fail_count["n"] += 1
                delay = min(2 ** _fail_count["n"], 30)
                status.value = f"Incorrect. Try again in {delay}s."
                self.page.update()
                time.sleep(delay)
                status.value = ""
                self.page.update()

        return ft.Container(
            expand=True,
            bgcolor=ft.Colors.WHITE,
            alignment=ft.Alignment.CENTER,
            content=ft.Column(
                scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=[
                    ft.Icon(ft.Icons.LOCK_OUTLINE, size=48, color=ft.Colors.GREY_500),
                    ft.Text("MyMoney is locked", size=18, weight=ft.FontWeight.BOLD),
                    code_field,
                    ft.FilledButton("Unlock", on_click=submit),
                    status,
                ],
            ),
        )


if __name__ == "__main__":
    h1 = _hash_passcode("1234", "salt")
    h2 = _hash_passcode("1234", "salt")
    h3 = _hash_passcode("4321", "salt")
    assert h1 == h2 and h1 != h3
    print("OK")