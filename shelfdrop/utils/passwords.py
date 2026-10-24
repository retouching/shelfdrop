"""Passwords kept as their scrypt: a random salt, the parameters written with the hash, and a
comparison in constant time. Pure: the standard library alone."""

import base64
import hashlib
import hmac
import secrets
from typing import Final

# The cost of one hash: about 32 MiB of memory and a tenth of a second.
COST: Final = 2**15
BLOCK_SIZE: Final = 8
PARALLELISM: Final = 1
KEY_BYTES: Final = 32
SALT_BYTES: Final = 16
SCHEME: Final = "scrypt"
# The highest cost a stored hash may ask for: a hash written by hand cannot exhaust memory.
COST_MAX: Final = 2**20


def encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def derive(password: str, salt: bytes, cost: int, block_size: int, parallelism: int) -> bytes:
    return hashlib.scrypt(
        password.encode(),
        salt=salt,
        n=cost,
        r=block_size,
        p=parallelism,
        maxmem=2 * 128 * cost * block_size * parallelism,
        dklen=KEY_BYTES,
    )


def hash_password(password: str) -> str:
    """`scrypt$<n>$<r>$<p>$<salt>$<hash>`, the salt and the hash in base64url."""
    salt = secrets.token_bytes(SALT_BYTES)
    digest = derive(password, salt, COST, BLOCK_SIZE, PARALLELISM)
    return f"{SCHEME}${COST}${BLOCK_SIZE}${PARALLELISM}${encode(salt)}${encode(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """Whether `password` gives `stored` again, with the parameters `stored` names; False for
    a hash it cannot read."""
    parts = stored.split("$")
    if len(parts) != 6 or parts[0] != SCHEME or not all(p.isdigit() for p in parts[1:4]):
        return False
    cost, block_size, parallelism = (int(p) for p in parts[1:4])
    if not (1 < cost <= COST_MAX and cost & (cost - 1) == 0 and 0 < block_size <= 32):
        return False
    if not 0 < parallelism <= 16:
        return False
    try:
        salt, expected = decode(parts[4]), decode(parts[5])
    except ValueError:
        return False
    return hmac.compare_digest(derive(password, salt, cost, block_size, parallelism), expected)
