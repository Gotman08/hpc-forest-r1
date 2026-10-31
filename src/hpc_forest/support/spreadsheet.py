"""CSV cells that a spreadsheet opens as text, never as a formula.

Exports carry model rationales, reasons and imported names: untrusted text.
"""
from __future__ import annotations

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def inert(value):
    """Quote text a spreadsheet would evaluate; numbers and other values pass unchanged."""
    return "'" + value if isinstance(value, str) and value.startswith(FORMULA_PREFIXES) else value


def inert_row(row: dict) -> dict:
    return {key: inert(value) for key, value in row.items()}
