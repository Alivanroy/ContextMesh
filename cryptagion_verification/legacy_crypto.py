"""CRYPTAGION provider verification only (temporary branch, never merged)."""
import hashlib


def fingerprint(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def cache_key(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()
