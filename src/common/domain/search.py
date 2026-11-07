import re


def extract_phone_search_digits(term: str) -> str:
    """Normalize phone-shaped search terms; mixed text must not match phone digits."""
    term = term.strip()
    if re.fullmatch(r"[0-9 +().-]+", term) is None:
        return ""
    return re.sub(r"[^0-9]", "", term)
