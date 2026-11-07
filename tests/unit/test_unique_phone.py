import re
from concurrent.futures import ThreadPoolExecutor

from src.common.domain.search import extract_phone_search_digits
from src.feat.clients.api.client_schemas import CreateClientReq
from tests import helpers


def test_phone_format_and_ascii_digits():
    for _ in range(100):
        phone = helpers.unique_phone()
        assert re.fullmatch(r"\+79[0-9]{9}", phone)
        assert len(phone[1:]) == 11
        assert phone[1:].isascii()
        assert phone[1:].isdigit()


def test_ten_thousand_phones_are_unique():
    phones = [helpers.unique_phone() for _ in range(10_000)]
    assert len(set(phones)) == 10_000


def test_phone_accepted_by_current_client_schema():
    phone = helpers.unique_phone()
    request = CreateClientReq(name="Synthetic QA", phone=phone, address="Synthetic address", sleepingThresholdDays=30)
    assert request.phone == phone


def test_phone_supports_full_partial_and_formatted_search():
    phone = helpers.unique_phone()
    assert extract_phone_search_digits(phone) == phone[1:]
    assert extract_phone_search_digits(phone[-4:]) == phone[-4:]
    formatted = f"+7 ({phone[2:5]}) {phone[5:8]}-{phone[8:10]}-{phone[10:]}"
    assert extract_phone_search_digits(formatted) == phone[1:]


def test_threads_share_one_unique_sequence():
    def batch(_):
        return [helpers.unique_phone() for _ in range(1250)]

    with ThreadPoolExecutor(max_workers=8) as pool:
        phones = [phone for batch_result in pool.map(batch, range(8)) for phone in batch_result]
    assert len(set(phones)) == 10_000


def test_offset_wrap_preserves_format_and_uniqueness(monkeypatch):
    from itertools import count

    monkeypatch.setattr(helpers, "_phone_offset", 10**9 - 2)
    monkeypatch.setattr(helpers, "_phone_sequence", count())
    assert [helpers.unique_phone() for _ in range(3)] == ["+79999999998", "+79618033987", "+79236067976"]
