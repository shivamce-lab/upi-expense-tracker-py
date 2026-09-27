"""Bill-splitting screen: per-transaction participants, shares, and settlement status."""
from decimal import Decimal, InvalidOperation

import flet as ft

import components
import db
from services import split as split_service


class SplitScreenView:
    """Builds the bill-splitting screen: add participants to a transaction, track settlement."""

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.container = ft.Container(expand=True, bgcolor=ft.Colors.WHITE)

    def build(self) -> ft.Container:
        """Build (or rebuild) the Split screen content."""
        self.container.content = self._build_body()
        return self.container

    def refresh(self) -> None:
        """Rebuild content and update the page."""
        self.container.content = self._build_body()
        self.page.update()

    def _build_body(self) -> ft.Control:
        totals = split_service.person_totals()
        totals_section: list[ft.Control] = []
        if not totals:
            totals_section.append(components.empty_state("No bill splits yet."))
        else:
            for t in totals:
                totals_section.append(
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(t["person"], size=14, weight=ft.FontWeight.W_600),
                            ft.Text(f"Owes ₹{t['owed']:,.2f}  ({t['unsettled']} unsettled)", size=12, color=ft.Colors.RED_400 if t["owed"] > 0 else ft.Colors.GREEN_600),
                        ],
                    )
                )

        expense_txns = [t for t in db.list_transactions() if t["type"] == "expense"][:30]
        splits_by_txn = {t["id"]: db.list_person_splits(t["id"]) for t in expense_txns}

        txn_cards: list[ft.Control] = []
        for t in expense_txns:
            splits = splits_by_txn.get(t["id"], [])
            split_rows = []
            for s in splits:
                split_rows.append(
                    ft.Row(
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        controls=[
                            ft.Text(f"{s['person']}: ₹{s['share']:,.2f}", size=12),
                            ft.Switch(
                                value=bool(s["settled"]),
                                label="Settled",
                                on_change=lambda e, sid=s["id"]: self._toggle_settled(sid, e.control.value),
                            ),
                        ],
                    )
                )
            txn_cards.append(
                ft.Container(
                    padding=12, border=ft.Border.all(1, ft.Colors.GREY_200), border_radius=12,
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Row(
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                controls=[
                                    ft.Text(f"{t.get('category_name') or 'Uncategorized'} · ₹{t['amount']:,.2f}", size=13, weight=ft.FontWeight.W_600),
                                    ft.TextButton("Split with…", on_click=lambda e, tid=t["id"]: self._open_split_dialog(tid)),
                                ],
                            ),
                            ft.Text(t.get("note") or "", size=11, color=ft.Colors.GREY_600),
                            *split_rows,
                        ],
                    ),
                )
            )

        body = ft.Column(
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=18,
            controls=[
                ft.Text("Split Bills", size=22, weight=ft.FontWeight.BOLD),
                components.section_title("Who owes what"),
                ft.Column(spacing=8, controls=totals_section),
                components.section_title("Recent expenses"),
                ft.Column(spacing=10, controls=txn_cards) if txn_cards else components.empty_state("No expenses to split yet."),
            ],
        )
        return ft.Container(expand=True, bgcolor=ft.Colors.WHITE, padding=ft.Padding.symmetric(horizontal=16, vertical=10), content=body)

    def _toggle_settled(self, split_id: int, value: bool) -> None:
        try:
            if value:
                split_service.settle(split_id)
            else:
                split_service.unsettle(split_id)
        except Exception as ex:
            components.show_error(self.page, f"Could not update split: {ex}")
        self.refresh()

    def _open_split_dialog(self, txn_id: int) -> None:
        rows_container = ft.Column(spacing=6)
        entries: list[dict] = []

        def add_row(e: ft.ControlEvent | None = None) -> None:
            name_field = ft.TextField(label="Name", width=140)
            share_field = ft.TextField(label="Share", width=100, keyboard_type=ft.KeyboardType.NUMBER)
            entries.append({"name": name_field, "share": share_field})
            rows_container.controls.append(ft.Row(controls=[name_field, share_field]))
            self.page.update()

        add_row()

        def close_dialog(e: ft.ControlEvent | None = None) -> None:
            dialog.open = False
            self.page.update()

        def save(e: ft.ControlEvent) -> None:
            shares: dict[str, Decimal] = {}
            for entry in entries:
                name = (entry["name"].value or "").strip()
                if not name:
                    continue
                try:
                    share = Decimal(entry["share"].value.strip())
                except (InvalidOperation, AttributeError, ValueError):
                    continue
                shares[name] = share
            if not shares:
                components.show_error(self.page, "Add at least one valid participant and share.")
                return
            try:
                split_service.split_transaction(txn_id, shares)
            except Exception as ex:
                components.show_error(self.page, f"Could not save split: {ex}")
                return
            close_dialog()
            self.refresh()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Split with…"),
            content=ft.Column(
                tight=True, width=320,
                controls=[rows_container, ft.TextButton("+ Add person", on_click=add_row)],
            ),
            actions=[ft.TextButton("Cancel", on_click=close_dialog), ft.FilledButton("Save", on_click=save)],
        )
        self.page.show_dialog(dialog)


if __name__ == "__main__":
    print("OK")