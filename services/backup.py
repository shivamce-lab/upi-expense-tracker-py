"""Password-encrypted local backup/restore using stdlib zipfile + scrypt + HMAC. No cloud needed."""
import hashlib
import hmac
import json
import os
import zipfile
from pathlib import Path

import db

SALT_SIZE = 16
KEY_LEN = 32
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**14, 8, 1


def _derive_key(password: str, salt: bytes) -> bytes:
    """Derive a symmetric key from a password via scrypt."""
    return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=SCRYPT_N, r=SCRYPT_R, p=SCRYPT_P, dklen=KEY_LEN)


def _xor_stream(data: bytes, key: bytes) -> bytes:
    """Simple keystream XOR cipher: expand key via repeated SHA-256 to data length."""
    out = bytearray()
    counter = 0
    stream = b""
    while len(stream) < len(data):
        stream += hashlib.sha256(key + counter.to_bytes(4, "big")).digest()
        counter += 1
    for i, b in enumerate(data):
        out.append(b ^ stream[i])
    return bytes(out)


def create_backup(dest: str | Path, password: str) -> None:
    """Write a password-encrypted .mymoney archive (SQLite bytes + settings JSON) to dest."""
    dest = Path(dest)
    salt = os.urandom(SALT_SIZE)
    key = _derive_key(password, salt)

    db_bytes = Path(db.DB_PATH).read_bytes() if Path(db.DB_PATH).exists() else b""
    settings_json = json.dumps(db.all_settings()).encode("utf-8")

    payload = json.dumps(
        {"db_hex": db_bytes.hex(), "settings_hex": settings_json.hex()}
    ).encode("utf-8")

    encrypted = _xor_stream(payload, key)
    mac = hmac.new(key, encrypted, hashlib.sha256).digest()

    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("salt.bin", salt)
        zf.writestr("hmac.bin", mac)
        zf.writestr("payload.bin", encrypted)


def restore_backup(src: str | Path, password: str) -> None:
    """Validate HMAC and restore a .mymoney archive created by create_backup."""
    src = Path(src)
    with zipfile.ZipFile(src, "r") as zf:
        salt = zf.read("salt.bin")
        mac = zf.read("hmac.bin")
        encrypted = zf.read("payload.bin")

    key = _derive_key(password, salt)
    expected_mac = hmac.new(key, encrypted, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected_mac):
        raise ValueError("Incorrect password or corrupted backup file.")

    payload = json.loads(_xor_stream(encrypted, key).decode("utf-8"))
    db_bytes = bytes.fromhex(payload["db_hex"])
    settings = json.loads(bytes.fromhex(payload["settings_hex"]).decode("utf-8"))

    Path(db.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
    if db_bytes:
        Path(db.DB_PATH).write_bytes(db_bytes)
    for k, v in settings.items():
        db.set_setting(k, v)


if __name__ == "__main__":
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        dest = Path(tmp) / "test.mymoney"
        create_backup(dest, "hunter2")
        try:
            restore_backup(dest, "wrong-password")
            raise AssertionError("should have raised")
        except ValueError:
            pass
        restore_backup(dest, "hunter2")
    print("OK")