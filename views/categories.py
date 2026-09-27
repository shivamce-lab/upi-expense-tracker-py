"""Categories screen: income/expense category lists with edit/delete, create via enhancements."""
import flet as ft

import components
import db
from services import enhancements


class CategoriesView:
    """Builds and manages the Categories screen. Category creation is delegated to
    services.enhancements.open_add_category_dialog (unlimited categories, already-existing
    public helper) rather than duplicating dialog logic here.
    """

    def __init__(self, page: ft.Page) -> None:
        self.page = page
        self.container = ft.Container(expand=True, bgcolor=ft.Colors.WHITE)

    def build(self) -> ft.Container:
        """Build (or rebuild) the Categories screen content."""
        self.container.content = self._build_body()
        return self.container

    def _refresh(self) -> None:
        self.container.content = self._build_body()
        self.page.update()

    def _category_list(self, categories: list[dict]) -> ft.Control:
        if not categories:
            return components.empty_state("No categories yet.")
        rows = []
        for c in categories:
            rows.append(
                ft.Row(
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    controls=[
                        ft.Row(spacing=10, controls=[
                            ft.CircleAvatar(bgcolor=c["color"], content=ft.Text(c["icon"]), radius=16),
                            ft.Text(c["name"], size=14),
                        ]),
                        ft.PopupMenuButton(
                            icon=ft.Icons.MORE_VERT,
                            items=[
                                ft.PopupMenuItem(content="Edit", on_click=lambda e, cid=c["id"]: self.open_edit_dialog(cid)),
                                ft.PopupMenuItem(content="Delete", on_click=lambda e, cid=c["id"]: self.open_delete_dialog(cid)),
                            ],
                        ),
                    ],
                )
            )
        return ft.Column(spacing=8, controls=rows)

    def _build_body(self) -> ft.Control:
        income_cats = db.list_categories("income")
        expense_cats = db.list_categories("expense")

        body = ft.Column(
            scroll=ft.ScrollMode.AUTO, expand=True, spacing=18,
            controls=[
                ft.Row(alignment=ft.MainAxisAlignment.SPACE_BETWEEN, controls=[
                    ft.Column(spacing=2, controls=[
                        ft.Text("Categories", size=22, weight=ft.FontWeight.BOLD),
                        ft.Text("Create & customize your categories, no limit", size=12, color=ft.Colors.GREY_600),
                    ]),
                    ft.IconButton(icon=ft.Icons.ADD_CIRCLE_OUTLINE, on_click=lambda e: self.open_add_dialog()),
                ]),
                components.section_title("Income categories"),
                self._category_list(income_cats),
                components.section_title("Expense categories"),
                self._category_list(expense_cats),
            ],
        )
        return ft.Container(padding=ft.Padding.symmetric(horizontal=16, vertical=10), content=body)

    # ---------------------------------------------------------------- dialog

    def open_add_dialog(self) -> None:
        """Open the Create Category dialog via the shared enhancements helper."""
        enhancements.open_add_category_dialog(self.page, on_saved=self._refresh)

    def open_edit_dialog(self, category_id: int) -> None:
        """Open the edit dialog for an existing category via the shared enhancements helper.

        Falls back to the add flow if enhancements does not expose an edit variant,
        since enhancements.py's public contract is not to be modified here.
        """
        cats = {c["id"]: c for c in db.list_categories()}
        cat = cats.get(category_id)
        if not cat:
            return
        if hasattr(enhancements, "open_edit_category_dialog"):
            enhancements.open_edit_category_dialog(self.page, cat, on_saved=self._refresh)
        else:
            enhancements.open_add_category_dialog(self.page, on_saved=self._refresh, prefill=cat)

    def open_delete_dialog(self, category_id: int) -> None:
        """Open a confirmation dialog before deleting a category."""

        def close_dialog(e: ft.ControlEvent | None = None) -> None:
            dialog.open = False
            self.page.update()

        def confirm_delete(e: ft.ControlEvent) -> None:
            try:
                db.delete_category(category_id)
            except Exception as ex:
                components.show_error(self.page, f"Could not delete category: {ex}")
            close_dialog()
            self._refresh()

        dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Delete category?"),
            content=ft.Text("Existing transactions will keep this category id."),
            actions=[
                ft.TextButton("Cancel", on_click=close_dialog),
                ft.TextButton("Delete", on_click=confirm_delete, style=ft.ButtonStyle(color=ft.Colors.RED_400)),
            ],
        )
        self.page.show_dialog(dialog)


if __name__ == "__main__":
    print("OK")