from __future__ import annotations

import base64
import hashlib
import hmac
import os


_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SALT_BYTES = 16
_KEY_BYTES = 32
_UNUSABLE_PASSWORD_PREFIX = "!"


def normalize_email(email: str) -> str:
    return email.strip().lower()


def make_unusable_password_hash() -> str:
    return f"{_UNUSABLE_PASSWORD_PREFIX}{base64.urlsafe_b64encode(os.urandom(24)).decode('ascii')}"


def hash_password(password: str) -> str:
    salt = os.urandom(_SALT_BYTES)
    derived = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_KEY_BYTES,
    )
    salt_encoded = base64.urlsafe_b64encode(salt).decode("ascii")
    derived_encoded = base64.urlsafe_b64encode(derived).decode("ascii")
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${salt_encoded}${derived_encoded}"


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash or password_hash.startswith(_UNUSABLE_PASSWORD_PREFIX):
        return False

    try:
        algorithm, n_raw, r_raw, p_raw, salt_encoded, expected_encoded = password_hash.split("$", 5)
    except ValueError:
        return False
    if algorithm != "scrypt":
        return False

    try:
        salt = base64.urlsafe_b64decode(salt_encoded.encode("ascii"))
        expected = base64.urlsafe_b64decode(expected_encoded.encode("ascii"))
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_raw),
            r=int(r_raw),
            p=int(p_raw),
            dklen=len(expected),
        )
    except Exception:
        return False

    return hmac.compare_digest(derived, expected)
