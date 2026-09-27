"""Settings screen: theme toggle, passcode, backup/restore, Drive sync, currency, recurring."""
import datetime as dt

import flet as ft

import components
import db
import theme
from services import backup as backup_service
from services import gdrive
from services import recurring as recurring_service
from views.lock import set_passcode


class SettingsView:
    """Builds the Settings screen."""

    def __init__(self, page: ft.Page, on_theme_change=None) -> None:
        self.page = page
        self.on_theme_change = on_theme_change
        self.container = ft.Container(expand=True, bgcolor=ft.Colors.WHITE)
        self.file_picker = ft.FilePicker(self._on_restore_picked)
        page.services.append(self.file_picker)
        self._pending_restore_password: str | None = None

    def build(self) -> ft.Container:
        """Build (or rebuild) the Settings screen content."""
        self.container.content = self._build_body()
        return self.container

    def refresh(self) -> None:
        """Rebuild content and update the page."""
        self.container.content = self._build_body()
        self.page.update()

    def _build_body(self) -> ft.Control:
        current_theme = db.get_setting("theme", "light")
        currency = db.get_setting("currency_symbol", "$")

        theme_switch = ft.Switch(
            value=current_theme == "dark", label="Dark theme",
            on_change=lambda e: self._toggle_theme(),
        )

        currency_field = ft.TextField(label="Currency symbol", value=currency, width=120)

        def save_currency(e: ft.ControlEvent) -> None:
            db.set_setting("currency_symbol", currency_field.value or "$")
            components.show_info(self.page, "Currency updated.")

        passcode_status = "Passcode is set." if db.get_setting("passcode_hash") else "No passcode set."
        passcode_field = ft.TextField(label="New passcode", password=True, can_reveal_password=True, width=180)

        def set_pin(e: ft.ControlEvent) -> None:
            if not passcode_field.value or len(passcode_field.value) < 4:
                components.show_error(self.page, "Passcode must be at least 4 digits.")
                return
            set_passcode(passcode_field.value)
            components.show_info(self.page, "Passcode set.")
            self.refresh()

        def clear_pin(e: ft.ControlEvent) -> None:
            db.set_setting("passcode_hash", "")
            components.show_info(self.page, "Passcode removed.")
            self.refresh()

        backup_password_field = ft.TextField(label="Backup password", password=True, can_reveal_password=True, width=200)

        def do_backup(e: ft.ControlEvent) -> None:
            if not backup_password_field.value:
                components.show_error(self.page, "Enter a password to encrypt the backup.")
                return
            dest = db.DB_PATH.parent / f"mymoney_backup_{dt.date.today().isoformat()}.mymoney"
            try:
                backup_service.create_backup(dest, backup_password_field.value)
                components.show_info(self.page, f"Backup saved to {dest}")
            except Exception as ex:
                components.show_error(self.page, f"Backup failed: {ex}")

        def do_restore(e: ft.ControlEvent) -> None:
            if not backup_password_field.value:
                components.show_error(self.page, "Enter the backup's password first.")
                return
            self._pending_restore_password = backup_password_field.value
            self.file_picker.pick_files(allow_multiple=False)

        gdrive_switch = ft.Switch(
            value=gdrive.is_enabled(), label="Sync to Google Drive (optional)",
            on_change=lambda e: self._toggle_gdrive(e.control.value),
        )
        gdrive_note = "Uses Drive's drive.file scope only. Off by default." if gdrive.is_available() else \
            "Needs: pip install google-api-python-client google-auth-oauthlib (optional)."

        def run_recurring_now(e: ft.ControlEvent) -> None:
            result = recurring_service.run_due_all()
            components.show_info(
                self.page,
                f"Inserted {result['recurring']} recurring + {result['subscription']} subscription transaction(s).",
            )

        openai_key_field = ft.TextField(label="OpenAI API key (optional)", value=db.get_setting("openai_api_key", ""), password=True, can_reveal_password=True, width=280)
        gemini_key_field = ft.TextField(label="Gemini API key (optional)", value=db.get_setting("gemini_api_key", ""), password=True, can_reveal_password=True, width=280)

        def save_ai_keys(e: ft.ControlEvent) -> None:
            db.set_setting("openai_api_key", openai_key_field.value or "")
            db.set_setting("gemini_api_key", gemini_key_field.value or "")
            components.show_info(self.page, "AI keys saved (used only if you tap Deep Insight; fully optional).")

        body = ft.Column(
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=22,
            controls=[
                ft.Text("Settings", size=22, weight=ft.FontWeight.BOLD),

                components.section_title("Appearance"),
                theme_switch,

                components.section_title("Currency"),
                ft.Row(controls=[currency_field, ft.TextButton("Save", on_click=save_currency)]),

                components.section_title("Passcode lock"),
                ft.Text(passcode_status, size=12, color=ft.Colors.GREY_600),
                ft.Row(controls=[passcode_field, ft.TextButton("Set", on_click=set_pin), ft.TextButton("Remove", on_click=clear_pin)]),

                components.section_title("Recurring & subscriptions"),
                ft.Button(content="Run due now", icon=ft.Icons.REPLAY, on_click=run_recurring_now),

                components.section_title("Backup & restore"),
                backup_password_field,
                ft.Row(controls=[
                    ft.Button(content="Create encrypted backup", icon=ft.Icons.LOCK_OUTLINE, on_click=do_backup),
                    ft.OutlinedButton("Restore from file", icon=ft.Icons.RESTORE, on_click=do_restore),
                ]),

                components.section_title("Google Drive sync (optional, off by default)"),
                gdrive_switch,
                ft.Text(gdrive_note, size=11, color=ft.Colors.GREY_500),

                components.section_title("AI insight keys (optional, fully offline without these)"),
                openai_key_field, gemini_key_field,
                ft.TextButton("Save keys", on_click=save_ai_keys),
            ],
        )
        return ft.Container(expand=True, bgcolor=ft.Colors.WHITE, padding=ft.Padding.symmetric(horizontal=16, vertical=10), content=body)

    def _toggle_theme(self) -> None:
        palette = theme.toggle_theme(self.page)
        if self.on_theme_change:
            self.on_theme_change(palette)
        self.refresh()

    def _toggle_gdrive(self, value: bool) -> None:
        if value:
            gdrive.enable_sync()
        else:
            gdrive.disable_sync()
        components.show_info(self.page, "Google Drive sync " + ("enabled." if value else "disabled."))

    def _on_restore_picked(self, e: ft.FilePickerResultEvent) -> None:
        if not e.files or not self._pending_restore_password:
            return
        path = e.files[0].path
        try:
            backup_service.restore_backup(path, self._pending_restore_password)
            components.show_info(self.page, "Restore complete. Restart the app to see restored data.")
        except Exception as ex:
            components.show_error(self.page, f"Restore failed: {ex}")
        finally:
            self._pending_restore_password = None


if __name__ == "__main__":
    print("OK")