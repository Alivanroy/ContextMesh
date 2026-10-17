"""Temporary file for CRYPTAGION SARIF line-hash verification. Do not merge."""
import hashlib


def digest(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()
