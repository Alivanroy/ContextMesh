"""ContextMesh — observability layer for AI coding agents."""
from __future__ import annotations

# Single source of truth: pyproject.toml ``[tool.poetry] version`` is read
# from installed package metadata when the package is installed; tests
# enforce it equals the value below so import-time access works in dev
# checkouts too.
__version__ = "0.3.0"
