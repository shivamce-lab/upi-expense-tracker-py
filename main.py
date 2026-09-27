import os
from decimal import Decimal
from pathlib import Path

import flet as ft

import db
import state
import components
from services import enhancements
enhancements.patch_components_money() 

import theme
from services import reminders
from services import recurring as recurring_service
from services import inbox as inbox_service
from views.records import RecordsView
from views.analysis import AnalysisView
from views.budgets import BudgetsView
from views.accounts import AccountsView
from views.categories import CategoriesView
from views.bills import BillsView
from views.subscriptions import SubscriptionsView
from views.networth import NetWorthView
from views.calendar_view import CalendarView
from views.capture import CaptureView
from views.split_screen import SplitScreenView
from views.settings import SettingsView
from views.lock import LockView, is_locked
from views.onboarding import OnboardingView, is_onboarded

DEFAULT_EXPENSE_CATEGORIES = [
    ("Food", "🍔"), ("Bills", "🧾"), ("Shopping", "🛍️"),
    ("Transport", "🚗"), ("Health", "💊"), ("Entertainment", "🎬"),
]
DEFAULT_INCOME_CATEGORIES = [("Salary", "💰"), ("Business", "💼")]
DEFAULT_ACCOUNTS = [("Wallet", "Wallet"), ("Card", "Card"), ("Cash", "Cash")]


def seed_defaults() -> None:
    """Seed default categories and accounts on first run if their tables are empty."""
    if not db.list_categories():
        palette = components.CATEGORY_COLOR_PALETTE
        for i, (name, icon) in enumerate(DEFAULT_EXPENSE_CATEGORIES):
            db.add_category(name, "expense", icon, palette[i % len(palette)])
        for i, (name, icon) in enumerate(DEFAULT_INCOME_CATEGORIES):
            db.add_category(name, "income", icon, palette[(i + 6) % len(palette)])
    if not db.list_accounts():
        for name, type_ in DEFAULT_ACCOUNTS:
            db.add_account(name, type_, Decimal("0"))


def main(page: ft.Page) -> None:
    """App entry point: DB init, lock gate, onboarding gate, then the main shell."""
    db.init_db()
    seed_defaults()

    page.title = "MyMoney"
    page.scroll = ft.ScrollMode.AUTO
    page.padding = 0
    theme.apply_theme(page)

    try:
        inbox_service.ingest_inbox_file()
    except Exception:
        pass

    try:
        recurring_service.run_due_all()
    except Exception:
        pass

    def start_app_shell() -> None:
        """Build and mount the main navigable app shell."""
        page.controls.clear()
        build_shell(page)
        page.update()
        try:
            reminders.notify_due(page)
        except Exception as ex:
            components.show_error(page, f"Reminder check failed: {ex}")

    def show_onboarding_if_needed() -> None:
        """Show onboarding on first run, else go straight to the shell."""
        if is_onboarded():
            start_app_shell()
            return
        page.controls.clear()
        onboarding = OnboardingView(page, on_done=start_app_shell)
        page.add(onboarding.build())
        page.update()

    if is_locked():
        def on_unlock() -> None:
            show_onboarding_if_needed()

        lock_view = LockView(page, on_unlock=on_unlock)
        page.add(lock_view.build())
        page.update()
    else:
        show_onboarding_if_needed()

def build_shell(page: ft.Page) -> None:
    """Build the header, NavigationBar, drawer, FAB, and view routing for the main app."""
    palette = theme.get_palette()
    prior_tab = {"screen": "records", "index": 0}
    content = ft.Container(expand=True, bgcolor=palette["bg"])
    nav_screens = ["records", "analysis", "budgets", "accounts", "categories"]

    records_view = RecordsView(page)
    analysis_view = AnalysisView(page)
    budgets_view = BudgetsView(page)
    accounts_view = AccountsView(page)
    categories_view = CategoriesView(page)
    subscriptions_view = SubscriptionsView(page)
    networth_view = NetWorthView(page)
    calendar_view = CalendarView(page)
    split_view = SplitScreenView(page)

    def on_theme_change(palette: dict) -> None:
        content.bgcolor = palette["bg"]
        page.update()

    settings_view = SettingsView(page, on_theme_change=on_theme_change)

    def open_add_transaction_prefill(prefill: dict) -> None:
        """Route capture (OCR/voice/inbox) results into the Records Add dialog."""
        go_to_tab("records", 0)
        if hasattr(records_view, "open_add_dialog_prefill"):
            records_view.open_add_dialog_prefill(prefill)
        else:
            components.show_info(page, f"Captured: {prefill}. Fill in the Add Transaction dialog.")
            records_view.open_add_dialog()

    capture_view = CaptureView(page, open_add_transaction=open_add_transaction_prefill)

    def go_to_tab(screen: str, index: int) -> None:
        state.set_screen(screen)
        nav_bar.selected_index = index
        content.content = nav_builders[screen]()
        update_fab()
        page.update()

    bills_view = BillsView(page, go_back=lambda: go_to_tab(prior_tab["screen"], prior_tab["index"]))

    nav_builders = {
        "records": lambda: records_view.build(),
        "analysis": lambda: analysis_view.build(),
        "budgets": lambda: budgets_view.build(),
        "accounts": lambda: accounts_view.build(),
        "categories": lambda: categories_view.build(),
        "subscriptions": lambda: subscriptions_view.build(),
        "networth": lambda: networth_view.build(),
        "calendar": lambda: calendar_view.build(),
        "capture": lambda: capture_view.build(),
        "split": lambda: split_view.build(),
        "settings": lambda: settings_view.build(),
    }

    nav_bar = ft.NavigationBar(
        selected_index=0,
        bgcolor=ft.Colors.WHITE,
        destinations=[
            ft.NavigationBarDestination(icon=ft.Icons.LIST_ALT, label="Records"),
            ft.NavigationBarDestination(icon=ft.Icons.PIE_CHART, label="Analysis"),
            ft.NavigationBarDestination(icon=ft.Icons.SAVINGS, label="Budgets"),
            ft.NavigationBarDestination(icon=ft.Icons.ACCOUNT_BALANCE_WALLET, label="Accounts"),
            ft.NavigationBarDestination(icon=ft.Icons.CATEGORY, label="Categories"),
        ],
    )

    fab = ft.FloatingActionButton(icon=ft.Icons.ADD, visible=True, bgcolor=ft.Colors.BLUE_400)

    def update_fab() -> None:
        screen = state.get_screen()
        fab.visible = screen in ("records", "bills", "categories")
        page.update()

    def fab_clicked(e: ft.ControlEvent) -> None:
        screen = state.get_screen()
        if screen == "records":
            records_view.open_add_dialog()
        elif screen == "bills":
            bills_view.open_add_dialog()
        elif screen == "categories":
            categories_view.open_add_dialog()

    fab.on_click = fab_clicked

    def nav_changed(e: ft.ControlEvent) -> None:
        idx = e.control.selected_index
        go_to_tab(nav_screens[idx], idx)

    nav_bar.on_change = nav_changed

    def open_bills(e: ft.ControlEvent | None = None) -> None:
        prior_tab["screen"] = state.get_screen()
        prior_tab["index"] = nav_bar.selected_index
        state.set_screen("bills")
        content.content = bills_view.build()
        update_fab()
        page.update()

    def open_drawer_screen(screen: str) -> None:
        """Open a non-nav-bar screen (reachable only via the drawer)."""
        prior_tab["screen"] = state.get_screen() if state.get_screen() in nav_screens else prior_tab["screen"]
        prior_tab["index"] = nav_bar.selected_index
        state.set_screen(screen)
        content.content = nav_builders[screen]()
        update_fab()
        page.run_task(page.close_drawer)
        page.update()

    drawer = ft.NavigationDrawer(
        controls=[
            ft.Container(height=12),
            ft.NavigationDrawerDestination(icon=ft.Icons.SUBSCRIPTIONS_OUTLINED, label="Subscriptions"),
            ft.NavigationDrawerDestination(icon=ft.Icons.ACCOUNT_BALANCE_OUTLINED, label="Net Worth"),
            ft.NavigationDrawerDestination(icon=ft.Icons.CALENDAR_MONTH_OUTLINED, label="Calendar"),
            ft.NavigationDrawerDestination(icon=ft.Icons.DOCUMENT_SCANNER_OUTLINED, label="Capture"),
            ft.NavigationDrawerDestination(icon=ft.Icons.GROUP_OUTLINED, label="Split Bills"),
            ft.NavigationDrawerDestination(icon=ft.Icons.SETTINGS_OUTLINED, label="Settings"),
        ],
    )
    drawer_screens = ["subscriptions", "networth", "calendar", "capture", "split", "settings"]

    def drawer_changed(e: ft.ControlEvent) -> None:
        idx = e.control.selected_index
        if idx is not None and 0 <= idx < len(drawer_screens):
            open_drawer_screen(drawer_screens[idx])

    drawer.on_change = drawer_changed
    page.drawer = drawer

    def open_dev_noop(e: ft.ControlEvent | None = None) -> None:
        # Dev/build-meter screen intentionally not part of this build.
        pass

    title_row = ft.Row(
        controls=[
            ft.IconButton(icon=ft.Icons.MENU, on_click=lambda e: page.run_task(page.show_drawer)),
            ft.Text("MyMoney", size=22, weight=ft.FontWeight.BOLD),
        ]
    )

    header = ft.Container(
        bgcolor=ft.Colors.WHITE,
        padding=ft.Padding.symmetric(horizontal=8, vertical=6),
        content=ft.Row(
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
            controls=[
                title_row,
                ft.Row(
                    spacing=0,
                    controls=[
                        ft.IconButton(icon=ft.Icons.SEARCH, on_click=lambda e: None),
                        ft.IconButton(icon=ft.Icons.NOTIFICATIONS_NONE, on_click=open_bills),
                    ],
                ),
            ],
        ),
    )

    content.content = nav_builders["records"]()
    state.set_screen("records")

    page.add(ft.Column(expand=True, spacing=0, controls=[header, content]))
    page.navigation_bar = nav_bar
    page.floating_action_button = fab
    update_fab()


ft.run(main)