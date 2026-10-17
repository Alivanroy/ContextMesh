"""Temporary file for CRYPTAGION SARIF line-hash verification. Do not merge."""
import hashlib

CHUNK = 4096
# Moved down by three lines for the verification.


def digest(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()
