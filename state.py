"""Module-level UI state shared across views (no persistence, no classes needed)."""
import datetime as dt
_state = {
    "year": dt.date.today().year,
    "month": dt.date.today().month,
    "screen": "records",
}



def get_month() -> tuple[int, int]:
    """Return the currently selected (year, month) tuple."""
    return _state["year"], _state["month"]



def set_month(year: int, month: int) -> None:
    """Set the currently selected (year, month)."""
    _state["year"] = year
    _state["month"] = month



def get_screen() -> str:
    """Return the current top-level screen identifier."""
    return _state["screen"]



def set_screen(screen: str) -> None:
    """Set the current top-level screen identifier."""
    _state["screen"] = screen
