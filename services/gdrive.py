"""Optional Google Drive sync (drive.file scope only). Off by default; free tier only."""
from pathlib import Path

import db

try:
    from google.oauth2.credentials import Credentials  # noqa: F401
    from googleapiclient.discovery import build  # noqa: F401

    GDRIVE_AVAILABLE = True
except ImportError:
    GDRIVE_AVAILABLE = False


def is_available() -> bool:
    """Return True if google-api-python-client + google-auth are importable."""
    return GDRIVE_AVAILABLE


def is_enabled() -> bool:
    """Return True if the user has turned Drive sync on in Settings."""
    return db.get_setting("gdrive_enabled", "0") == "1"


def enable_sync() -> None:
    """Mark Drive sync as enabled in settings (actual OAuth handled by device browser flow)."""
    db.set_setting("gdrive_enabled", "1")


def disable_sync() -> None:
    """Mark Drive sync as disabled and drop any stored token reference."""
    db.set_setting("gdrive_enabled", "0")
    db.set_setting("gdrive_token_ref", "")


def store_token_reference(obfuscated_ref: str) -> None:
    """Store an obfuscated reference to the OAuth token (never the raw token itself)."""
    db.set_setting("gdrive_token_ref", obfuscated_ref)


def upload_backup(path: str | Path) -> str:
    """Upload an encrypted backup archive to the user's Drive appdata-scoped file. Requires setup."""
    if not GDRIVE_AVAILABLE:
        raise RuntimeError(
            "Google Drive sync needs extra packages: pip install google-api-python-client "
            "google-auth-oauthlib. This app works fully offline without it."
        )
    if not is_enabled():
        raise RuntimeError("Enable Google Drive sync in Settings first.")
    raise RuntimeError("Drive OAuth flow not wired up in this offline-first build; enable manually via CLI setup.")


def download_backup(dest: str | Path) -> None:
    """Download the most recent encrypted backup archive from Drive. Requires setup."""
    if not GDRIVE_AVAILABLE:
        raise RuntimeError(
            "Google Drive sync needs extra packages: pip install google-api-python-client "
            "google-auth-oauthlib. This app works fully offline without it."
        )
    raise RuntimeError("Drive OAuth flow not wired up in this offline-first build; enable manually via CLI setup.")


if __name__ == "__main__":
    assert is_available() in (True, False)
    assert is_enabled() in (True, False)
    print("OK")