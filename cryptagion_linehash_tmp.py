"""Temporary file for CRYPTAGION SARIF line-hash verification. Do not merge."""
import hashlib

CHUNK = 4096
# Moved down by three lines for the verification.


def digest_bytes(data: bytes, *, upper: bool = False) -> str:
    """Hex digest; the surrounding lines changed, the matched line did not."""
    return hashlib.md5(data).hexdigest()


def other() -> int:
    return CHUNK * 2
