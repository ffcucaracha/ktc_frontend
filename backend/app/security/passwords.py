import secrets
import string

from pwdlib import PasswordHash

PASSWORD_ALPHABET = string.ascii_letters + string.digits + "-_"


def hash_password(password: str) -> str:
    return PasswordHash.recommended().hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return PasswordHash.recommended().verify(password, password_hash)


def generate_temporary_password(length: int = 24) -> str:
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))
