import pytest

from src.common.domain.search import extract_phone_search_digits


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("QA-CORE-00", ""),
        ("QA-CORE-01", ""),
        ("  qa-core-01  ", ""),
        ("Ленина, 10", ""),
        ("QA-TEST-0001", ""),
        ("Иванов", ""),
        ("01", "01"),
        (" 01 ", "01"),
        ("0", "0"),
        ("79991234567", "79991234567"),
        ("123-45", "12345"),
        ("+7 (999) 123-45-67", "79991234567"),
        (" (12). 34-5+ ", "12345"),
        ("+", ""),
        ("---", ""),
        (" (). + - ", ""),
        ("12A34", ""),
        ("12a34", ""),
        ("", ""),
        ("   ", ""),
        ("%", ""),
        ("_", ""),
        ("\\", ""),
        ("12/34", ""),
        ("12\t34", ""),
        ("12\n34", ""),
        ("12\u00a034", ""),
        ("１２３", ""),
        ("١٢3", ""),
    ],
)
def test_extract_phone_search_digits(term, expected):
    assert extract_phone_search_digits(term) == expected
