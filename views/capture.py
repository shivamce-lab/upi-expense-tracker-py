"""Capture hub: receipt OCR, voice input, and share-sheet inbox review — all offline-first."""
import datetime as dt
from decimal import Decimal, InvalidOperation

import flet as ft

import components
import db
from services import inbox as inbox_service
from services import ocr as ocr_service
from services import voice as voice_service
from services import classify


class CaptureView:
    """Builds the Capture screen: OCR, voice, and inbox review entry points."""

    def __init__(self, page: ft.Page, open_add_transaction=None) -> None:
        self.page = page
        self.open_add_transaction = open_add_transaction  # callback(prefill: dict) -> None
        self.container = ft.Container(expand=True, bgcolor=ft.Colors.WHITE)
        self.file_picker = ft.FilePicker()
        page.services.append(self.file_picker)

    def build(self) -> ft.Container:
        """Build (or rebuild) the Capture screen content."""
        self.container.content = self._build_body()
        return self.container

    def _refresh(self) -> None:
        self.container.content = self._build_body()
        self.page.update()

    def _build_body(self) -> ft.Control:
        unparsed, total = inbox_service.review_summary()

        inbox_banner: list[ft.Control] = []
        if unparsed > 0:
            inbox_banner.append(
                ft.Container(
                    padding=12, bgcolor=ft.Colors.AMBER_50, border_radius=10,
                    content=ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(f"⚠ {unparsed} unparsed message(s) — review?", size=13),
                            ft.TextButton("Review", on_click=lambda e: self._review_inbox()),
                        ],
                    ),
                )
            )

        voice_status = "Voice input available (Vosk)." if voice_service.is_available() else \
            "Voice input needs: pip install vosk (offline model required)."
        ocr_status = "Receipt scanning available." if ocr_service.is_available() else \
            "Receipt scanning needs: pip install pytesseract Pillow (+ Tesseract binary)."

        body = ft.Column(
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=18,
            controls=[
                ft.Text("Capture", size=22, weight=ft.FontWeight.BOLD),
                *inbox_banner,
                components.section_title("Scan a receipt"),
                ft.Container(
                    padding=14, border=ft.Border.all(1, ft.Colors.GREY_200), border_radius=12,
                    content=ft.Column(spacing=8, controls=[
                        ft.Text(ocr_status, size=12, color=ft.Colors.GREY_600),
                        ft.Button(content="Pick receipt image", icon=ft.Icons.IMAGE_OUTLINED, on_click=lambda e: self.page.run_task(self._pick_receipt)),
                    ]),
                ),
                components.section_title("Voice add"),
                ft.Container(
                    padding=14, border=ft.Border.all(1, ft.Colors.GREY_200), border_radius=12,
                    content=ft.Column(spacing=8, controls=[
                        ft.Text(voice_status, size=12, color=ft.Colors.GREY_600),
                        ft.Button(content="Say a command", icon=ft.Icons.MIC_NONE, on_click=lambda e: self._try_voice()),
                    ]),
                ),
                components.section_title(f"Inbox ({total} total message(s))"),
                ft.Button(content="Review inbox", icon=ft.Icons.INBOX_OUTLINED, on_click=lambda e: self._review_inbox()),
            ],
        )
        return ft.Container(expand=True, bgcolor=ft.Colors.WHITE, padding=ft.Padding.symmetric(horizontal=16, vertical=10), content=body)

    # ------------------------------------------------------------ receipt OCR
    async def _pick_receipt(self) -> None:
        if not ocr_service.is_available():
            components.show_error(self.page, "OCR unavailable: pip install pytesseract Pillow.")
            return
        result_files = await self.file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.IMAGE)
        if not result_files:
            return
        path = result_files[0].path
        try:
            result = ocr_service.extract_receipt(path)
        except Exception as ex:
            components.show_error(self.page, f"Could not read receipt: {ex}")
            return
        prefill = {
            "amount": result.get("amount"),
            "date": result.get("date") or dt.date.today().isoformat(),
            "note": result.get("vendor") or "",
            "category_id": classify.classify_to_category_id(result.get("vendor") or ""),
        }
        if self.open_add_transaction:
            self.open_add_transaction(prefill)
        else:
            components.show_info(self.page, f"Extracted: {prefill}")

    # ------------------------------------------------------------ voice

    def _try_voice(self) -> None:
        if not voice_service.is_available():
            components.show_error(self.page, "Voice input needs: pip install vosk (+ a small model).")
            return
        try:
            result = voice_service.listen_and_parse()
        except Exception as ex:
            components.show_error(self.page, str(ex))
            return
        self._prefill_from_voice(result)

    def _prefill_from_voice(self, result: dict) -> None:
        prefill = {
            "amount": str(result.get("amount")) if result.get("amount") is not None else None,
            "date": dt.date.today().isoformat(),
            "note": result.get("category") or "",
            "category_id": classify.classify_to_category_id(result.get("category") or ""),
        }
        if self.open_add_transaction:
            self.open_add_transaction(prefill)

    # ------------------------------------------------------------ inbox

    def _review_inbox(self) -> None:
        messages = db.list_inbox_messages(parsed=False)
        if not messages:
            components.show_info(self.page, "No unparsed messages to review.")
            return

        rows = []
        for m in messages:
            parsed = inbox_service.parse_message(m["raw_text"])
            preview = f"{parsed['amount']} · {parsed.get('merchant', '?')}" if parsed else "Could not parse"
            rows.append(
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Column(spacing=0, expand=True, controls=[
                            ft.Text(m["raw_text"][:60], size=12),
                            ft.Text(preview, size=11, color=ft.Colors.GREY_600),
                        ]),
                        ft.TextButton(
                            "Use", disabled=parsed is None,
                            on_click=lambda e, mid=m["id"], p=parsed: self._use_inbox_message(mid, p),
                        ),
                    ],
                )
            )

        def close_dialog(e: ft.ControlEvent | None = None) -> None:
            dialog.open = False
            self.page.update()

        dialog = ft.AlertDialog(
            modal=True, title=ft.Text("Review inbox"),
            content=ft.Column(tight=True, width=340, height=360, scroll=ft.ScrollMode.AUTO, controls=rows),
            actions=[ft.TextButton("Close", on_click=close_dialog)],
        )
        self.page.show_dialog(dialog)

    def _use_inbox_message(self, message_id: int, parsed: dict | None) -> None:
        if parsed is None:
            return
        db.mark_inbox_parsed(message_id)
        prefill = {
            "amount": parsed.get("amount"),
            "date": dt.date.today().isoformat(),
            "note": parsed.get("merchant") or "",
            "category_id": classify.classify_to_category_id(parsed.get("merchant") or ""),
        }
        if self.open_add_transaction:
            self.open_add_transaction(prefill)
        self._refresh()


if __name__ == "__main__":
    print("OK")