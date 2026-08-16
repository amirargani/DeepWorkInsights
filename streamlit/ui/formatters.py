"""Localization and number formatting utility functions.

Provides helper functions to format numbers, decimals, percentages, and Plotly
separators according to English (EN) or German (DE) locale conventions.
"""

import pandas as pd


def format_number(val, lang: str = "EN") -> str:
    """Formats integers or floats with localized thousands separator ('.' for DE, ',' for EN)."""
    if val is None or pd.isna(val):
        return "N/A"
    try:
        n = int(round(float(val)))
        if lang == "DE":
            return f"{n:,}".replace(",", ".")
        return f"{n:,}"
    except (ValueError, TypeError):
        return str(val)


def format_decimal(val, lang: str = "EN", decimals: int = 2) -> str:
    """Formats float numbers with localized decimal & thousands separators."""
    if val is None or pd.isna(val):
        return "N/A"
    try:
        f_val = float(val)
        formatted = f"{f_val:,.{decimals}f}"
        if lang == "DE":
            formatted = formatted.replace(",", "X").replace(".", ",").replace("X", ".")
        return formatted
    except (ValueError, TypeError):
        return str(val)


def format_percent(val, lang: str = "EN", decimals: int = 2) -> str:
    """Formats percentages with localized decimal separator."""
    if val is None or pd.isna(val):
        return "N/A"
    dec_str = format_decimal(val, lang=lang, decimals=decimals)
    return f"{dec_str}%"


def get_plotly_separators(lang: str = "EN") -> str:
    """Returns Plotly separators string.

    For DE: decimal separator is ',', thousands separator is '.' -> ',.'
    For EN: decimal separator is '.', thousands separator is ',' -> '.,'
    """
    return ",." if lang == "DE" else ".,"


def format_date(val, lang: str = "EN") -> str:
    """Formats date objects or YYYY-MM-DD strings to localized format (DD.MM.YYYY for DE, YYYY-MM-DD for EN)."""
    if val is None or pd.isna(val):
        return "N/A"
    try:
        dt = pd.to_datetime(val)
        if lang == "DE":
            return dt.strftime("%d.%m.%Y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return str(val)

