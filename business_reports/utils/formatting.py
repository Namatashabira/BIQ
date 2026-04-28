def format_currency(amount: float, currency: str = "UGX") -> str:
    """
    Formats a number as a currency string with thousand separators.
    Example: 1234567 → "UGX 1,234,567"
    """
    if amount is None:
        amount = 0
    return f"{currency} {amount:,.0f}"


def format_percentage(value: float, decimals: int = 2) -> str:
    """
    Formats a float as a percentage string.
    Example: 0.1543 → "15.43%"
    """
    if value is None:
        value = 0
    return f"{value * 100:.{decimals}f}%"


def truncate_text(text: str, max_length: int = 50) -> str:
    """
    Truncates text to a maximum length, adding ellipsis if needed.
    """
    if not text:
        return ""
    return text if len(text) <= max_length else text[:max_length] + "..."


def format_number(amount: float, decimals: int = 0) -> str:
    """
    Formats a number with comma as thousands separator.
    """
    if amount is None:
        amount = 0
    return f"{amount:,.{decimals}f}"
