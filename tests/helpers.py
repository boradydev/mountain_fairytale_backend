from itertools import count
from secrets import randbelow
from threading import Lock
from uuid import uuid4

from src.core.uuid7 import uuid7


_issued_car_numbers: set[str] = set()
_phone_capacity = 10**9
_phone_offset = randbelow(_phone_capacity)
_phone_sequence = count()
_phone_lock = Lock()
_phone_step = 618_033_989  # Coprime with 10**9: a permutation, without near-identical neighbours.


def unique_username(prefix: str = "test") -> str:
    # Берем последние 12 символов hex-строки
    return f"{prefix}_{uuid7().hex[-12:]}"


def unique_car_number() -> str:
    """Return a unique number that passes the Russian type-1 format check."""
    letters = "АВЕКМНОРСТУХ"
    while True:
        value = uuid4().hex
        first_letter = letters[int(value[:2], 16) % len(letters)]
        first_series_letter = letters[int(value[2:4], 16) % len(letters)]
        second_series_letter = letters[int(value[4:6], 16) % len(letters)]
        serial = int(value[6:10], 16) % 1000
        region = 100 + int(value[10:14], 16) % 900
        number = f"{first_letter}{serial:03d}{first_series_letter}{second_series_letter}{region:03d}"
        if number not in _issued_car_numbers:
            _issued_car_numbers.add(number)
            return number


def unique_phone() -> str:
    """Issue synthetic +79 numbers, unique within this process; never call or send SMS."""
    with _phone_lock:
        index = next(_phone_sequence)
        if index >= _phone_capacity:
            raise RuntimeError("Synthetic phone range exhausted")
        return f"+79{(_phone_offset + index * _phone_step) % _phone_capacity:09d}"


def unique_product_name(prefix: str = "product") -> str:
    return f"{prefix}_{uuid7().hex}"


def delivery_address(**overrides):
    value = {
        "district": "Шпаковский муниципальный округ",
        "locality": "г. Михайловск",
        "street": "Локомотивная улица",
        "house": "147",
        "latitude": 45.1373445,
        "longitude": 41.9974531,
        "confirmed": True,
        "source": "manual",
    }
    value.update(overrides)
    return value


def delivery_address_entity():
    value = delivery_address()
    return value
