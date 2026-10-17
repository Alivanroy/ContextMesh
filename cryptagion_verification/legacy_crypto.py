"""CRYPTAGION provider verification only (temporary branch, never merged).

Second push: the MD5 call moves down; the SHA-1 call is removed.
"""
import hashlib


def fingerprint(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()
