"""AES-GCM encryption of a case bundle, decryptable in the browser with WebCrypto.

File layout of ``data.bin.enc``::

    b"FWV1" | salt (16 B) | iv (12 B) | AES-GCM ciphertext (+16 B tag)

Key = PBKDF2-HMAC-SHA256(passphrase, salt, ITERATIONS, 32 B).
The JS side (site/js/crypto.js) must use the same constants.
"""
import os
import secrets
import sys
from pathlib import Path

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

MAGIC = b"FWV1"
ITERATIONS = 200_000


def derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=ITERATIONS)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt_file(src: Path, dst: Path, passphrase: str) -> None:
    salt = os.urandom(16)
    iv = os.urandom(12)
    key = derive_key(passphrase, salt)
    ct = AESGCM(key).encrypt(iv, src.read_bytes(), None)
    dst.write_bytes(MAGIC + salt + iv + ct)


def decrypt_file(src: Path, passphrase: str) -> bytes:
    blob = src.read_bytes()
    assert blob[:4] == MAGIC, "not a FWV1 bundle"
    salt, iv, ct = blob[4:20], blob[20:32], blob[32:]
    return AESGCM(derive_key(passphrase, salt)).decrypt(iv, ct, None)


def new_passphrase() -> str:
    return secrets.token_urlsafe(12)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        sys.exit("usage: encrypt.py <data.bin> <passphrase>  (writes <data.bin>.enc)")
    src = Path(sys.argv[1])
    encrypt_file(src, src.with_suffix(src.suffix + ".enc"), sys.argv[2])
