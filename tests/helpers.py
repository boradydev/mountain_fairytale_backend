from uuid import uuid4

from src.core.uuid7 import uuid7


def unique_username(prefix: str = "test") -> str:
    # Берем последние 12 символов hex-строки
    return f"{prefix}_{uuid7().hex[-12:]}"


def unique_car_number() -> str:
    """Return a unique number that passes the Russian type-1 format check."""
    value = uuid7().hex
    letters = "АВЕКМНОРСТУХ"
    first_letter = letters[int(value[:2], 16) % len(letters)]
    first_series_letter = letters[int(value[2:4], 16) % len(letters)]
    second_series_letter = letters[int(value[4:6], 16) % len(letters)]
    serial = int(value[6:10], 16) % 1000
    region = 100 + int(value[10:13], 16) % 900
    return f"{first_letter}{serial:03d}{first_series_letter}{second_series_letter}{region:03d}"


def unique_phone() -> str:
    return uuid4().hex


def unique_product_name(prefix: str = "product") -> str:
    return f"{prefix}_{uuid7().hex}"
