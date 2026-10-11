import re
from typing import Annotated

from pydantic import BeforeValidator, Field


_LATIN_TO_CYRILLIC = str.maketrans(
    "ABEKMHOPCTYX",
    "АВЕКМНОРСТУХ",
)
CAR_NUMBER_PATTERN = r"^[АВЕКМНОРСТУХ][0-9]{3}[АВЕКМНОРСТУХ]{2}[0-9]{2,3}$"
_CAR_NUMBER_RE = re.compile(CAR_NUMBER_PATTERN)


def normalize_car_number(value: str) -> str:
    """Return a canonical type-1 Russian vehicle registration number."""
    compact = "".join(value.split()).upper().translate(_LATIN_TO_CYRILLIC)
    if not _CAR_NUMBER_RE.fullmatch(compact):
        raise ValueError("Expected a Russian type-1 registration number.")
    return compact


CarNumber = Annotated[
    str,
    BeforeValidator(normalize_car_number),
    Field(pattern=CAR_NUMBER_PATTERN),
]
