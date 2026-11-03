from dataclasses import replace
from decimal import Decimal

import pytest

from src.common.domain.events import FieldChange
from src.common.infra.services.event_pud_service import EventPublisher
from src.core.uuid7 import uuid7
from src.feat.employees.domain.employee_entities import Employee
from src.feat.products.domain.product_entities import Product
from src.feat.products.domain.product_events import UpdateProductEvent


def test_creation_snapshot_and_change_field_validation():
    product = Product.create(actor_id=uuid7(), name="Water", base_price=Decimal("10"))
    event = product.pull_events()[0]
    assert event.data == {
        "name": "Water",
        "display_name": "Water",
        "base_price": 10,
        "is_free_price": False,
        "is_active": True,
    }
    product.update(actor_id=event.actor_id, name="Water", base_price=10)
    assert product.pull_events() == []
    with pytest.raises(ValueError, match="Unsupported audit fields"):
        product._add_event(
            UpdateProductEvent(
                actor_id=event.actor_id,
                product_id=product.product_id,
                changes={"password_hash": FieldChange(old="old", new="new")},
            )
        )


def test_free_price_product_keeps_zero_catalog_price_and_audits_mode_changes():
    product = Product.create(
        actor_id=uuid7(),
        name="Sanitary service",
        base_price=Decimal("125.50"),
        is_free_price=True,
    )

    assert product.base_price == Decimal("0")
    assert product.is_free_price is True
    created = product.pull_events()[0]
    assert created.data["base_price"] == Decimal("0")
    assert created.data["is_free_price"] is True

    product.update(actor_id=created.actor_id, is_free_price=False, base_price=Decimal("75.00"))
    changed = product.pull_events()[0]
    assert isinstance(changed, UpdateProductEvent)
    assert set(changed.changes) == {"base_price", "is_free_price"}
    assert product.base_price == Decimal("75.00")
    assert product.is_free_price is False


def test_password_values_never_enter_events_including_nested_payloads():
    employee = Employee.create(
        actor_id=uuid7(), username="staff", password_hash="hash", role="employee", commission_percent=Decimal("1")
    )
    event = employee.pull_events()[0]
    assert "password_hash" not in event.data
    employee.change_password(actor_id=employee.employee_id, new_password_hash="new-hash")
    changed = employee.pull_events()[0]
    assert changed.data == {}
    assert type(changed).__name__ == "EmployeePasswordChangedEvent"
    with pytest.raises(ValueError, match="Sensitive fields"):
        EventPublisher._to_record(replace(event, data={"nested": {"password_hash": "hidden"}}))
