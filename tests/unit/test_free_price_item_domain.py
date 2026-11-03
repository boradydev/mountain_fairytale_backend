from decimal import Decimal
from types import SimpleNamespace

import pytest

from src.core.uuid7 import uuid7
from src.feat.delivery_document.api.delivery_document_schemas import CreateItemReq, UpdateItemReq
from src.feat.delivery_document.domain.delivery_document_entities import Item, Point, _validate_point_clients
from src.feat.delivery_document.domain.delivery_document_events import UpdateItemEvent
from src.feat.delivery_document.domain.delivery_document_excs import DeliveryDocumentUpdateException


def test_legacy_item_requests_default_to_standard_item_without_driver_note():
    common = {
        "productId": uuid7(),
        "productName": "Water",
        "quantity": 1,
        "price": 10,
    }

    created = CreateItemReq.model_validate(common)
    updated = UpdateItemReq.model_validate(common)

    assert created.is_free_price is False
    assert created.driver_note == ""
    assert updated.is_free_price is None
    assert updated.driver_note is None


def test_free_price_item_snapshots_mode_and_audits_driver_note_updates():
    actor_id = uuid7()
    point_id = uuid7()
    product_id = uuid7()
    item = Item.create(
        actor_id=actor_id,
        point_id=point_id,
        product_id=product_id,
        product_name="Sanitary service",
        quantity=1,
        price=Decimal("0"),
        is_free_price=True,
        driver_note="  Забрать кулер  ",
    )

    assert item.snapshot()["is_free_price"] is True
    assert item.snapshot()["driver_note"] == "Забрать кулер"
    created = item.pull_events()[0]
    assert created.data["is_free_price"] is True
    assert created.data["driver_note"] == "Забрать кулер"

    item.update(actor_id=actor_id, quantity=1, price=Decimal("50"), driver_note="Отдать кулер")
    changed = item.pull_events()[0]
    assert isinstance(changed, UpdateItemEvent)
    assert changed.changes["driver_note"].old == "Забрать кулер"
    assert changed.changes["driver_note"].new == "Отдать кулер"

    item.update(actor_id=actor_id, quantity=1, price=Decimal("50"), driver_note="")
    assert item.driver_note == ""


def test_driver_note_is_only_allowed_for_free_price_items_and_limited_to_1000_chars():
    with pytest.raises(DeliveryDocumentUpdateException) as invalid_note:
        Item.create(
            actor_id=uuid7(),
            point_id=uuid7(),
            product_id=uuid7(),
            product_name="Water",
            quantity=1,
            price=Decimal("10"),
            driver_note="Deliver after 3pm",
        )
    assert invalid_note.value.field == "driver_note"
    assert invalid_note.value.message == "Driver notes are available only for free-price items."

    with pytest.raises(DeliveryDocumentUpdateException) as long_note:
        Item.create(
            actor_id=uuid7(),
            point_id=uuid7(),
            product_id=uuid7(),
            product_name="Sanitary service",
            quantity=1,
            price=Decimal("0"),
            is_free_price=True,
            driver_note="x" * 1001,
        )
    assert long_note.value.field == "driver_note"
    assert long_note.value.message == "Driver note cannot exceed 1000 characters."


def test_existing_item_keeps_free_price_snapshot_when_update_fields_are_omitted():
    actor_id = uuid7()
    client_id = uuid7()
    point_id = uuid7()
    delivery_document_id = uuid7()
    product_id = uuid7()
    item = Item.create(
        actor_id=actor_id,
        point_id=point_id,
        product_id=product_id,
        product_name="Sanitary service",
        quantity=1,
        price=Decimal("0"),
        is_free_price=True,
        driver_note="Забрать кулер",
    )
    point = Point(
        point_id=point_id,
        delivery_document_id=delivery_document_id,
        client_id=client_id,
        payment_method_id=None,
        is_delivered=True,
        non_delivery_reason="",
        memo="",
        position=0,
        items=[item],
    )

    request_item = SimpleNamespace(
        product_id=product_id,
        product_name="Sanitary service",
        quantity=2,
        price=Decimal("35"),
        is_free_price=None,
        driver_note=None,
    )
    point.update(
        actor_id=actor_id,
        client_id=client_id,
        position=0,
        items=[request_item],
        payment_method_id=None,
    )

    assert point.items[0].is_free_price is True
    assert point.items[0].driver_note == "Забрать кулер"
    assert point.items[0].quantity == 2

    request_item.is_free_price = False
    with pytest.raises(DeliveryDocumentUpdateException) as changed_snapshot:
        point.update(
            actor_id=actor_id,
            client_id=client_id,
            position=0,
            items=[request_item],
            payment_method_id=None,
        )
    assert changed_snapshot.value.field == "is_free_price"
    assert changed_snapshot.value.message == "An item's free-price snapshot cannot be changed."


def test_new_standard_item_in_patch_defaults_omitted_snapshot_to_false():
    actor_id = uuid7()
    client_id = uuid7()
    point = Point(
        point_id=uuid7(),
        delivery_document_id=uuid7(),
        client_id=client_id,
        payment_method_id=None,
        is_delivered=True,
        non_delivery_reason="",
        memo="",
        position=0,
        items=[],
    )

    point.update(
        actor_id=actor_id,
        client_id=client_id,
        position=0,
        payment_method_id=None,
        items=[
            SimpleNamespace(
                product_id=uuid7(),
                product_name="Water",
                quantity=1,
                price=Decimal("10"),
                is_free_price=None,
                driver_note=None,
            )
        ],
    )

    assert point.items[0].is_free_price is False
    assert point.items[0].driver_note == ""


def test_pickup_rejects_free_price_items_and_driver_notes():
    point = SimpleNamespace(
        client_id=None,
        items=[SimpleNamespace(is_free_price=True, driver_note="")],
    )

    with pytest.raises(DeliveryDocumentUpdateException) as free_item_error:
        _validate_point_clients("pickup_sheet", [point])
    assert free_item_error.value.field == "is_free_price"

    point.items = [SimpleNamespace(is_free_price=False, driver_note="Driver note")]
    with pytest.raises(DeliveryDocumentUpdateException) as note_error:
        _validate_point_clients("pickup_sheet", [point])
    assert note_error.value.field == "is_free_price"
