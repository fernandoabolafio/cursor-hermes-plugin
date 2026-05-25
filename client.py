"""Cursor plugin availability check.

The bridge is launched per-call in tools.py (context manager pattern).
This module only provides the check_fn used by the tool registry.
"""

from __future__ import annotations

import os


def check_cursor_available() -> bool:
    """Return True when cursor-sdk is importable and CURSOR_API_KEY is set."""
    try:
        import cursor_sdk  # noqa: F401
        return bool(os.environ.get("CURSOR_API_KEY", "").strip())
    except ImportError:
        return False
