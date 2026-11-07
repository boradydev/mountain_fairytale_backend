from src.feat.cars.domain.car_number import normalize_car_number
from tests.helpers import unique_car_number


def test_unique_car_number_generates_distinct_valid_numbers() -> None:
    numbers = [unique_car_number() for _ in range(1_000)]

    assert len(set(numbers)) == len(numbers)
    assert all(normalize_car_number(number) == number for number in numbers)
