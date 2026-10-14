from dataclasses import replace

import pytest

from src.common.domain.events import FieldChange
from src.common.infra.services.event_pud_service import EventPublisher
from src.core.uuid7 import uuid7
from src.feat.employees.domain.employee_entities import Employee
from src.feat.products.domain.product_entities import Product
from src.feat.products.domain.product_events import UpdateProductEvent


def test_creation_snapshot_and_change_field_validation():
    product = Product.create(actor_id=uuid7(), name="Water", base_price=10)
    event = product.pull_events()[0]
    assert event.data == {"name": "Water", "display_name": "Water", "base_price": 10, "is_active": True}
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


def test_password_values_never_enter_events_including_nested_payloads():
    employee = Employee.create(
        actor_id=uuid7(), username="staff", password_hash="hash", role="employee", commission_percent=1
    )
    event = employee.pull_events()[0]
    assert "password_hash" not in event.data
    employee.change_password(actor_id=employee.employee_id, new_password_hash="new-hash")
    changed = employee.pull_events()[0]
    assert changed.data == {}
    assert type(changed).__name__ == "EmployeePasswordChangedEvent"
    with pytest.raises(ValueError, match="Sensitive fields"):
        EventPublisher._to_record(replace(event, data={"nested": {"password_hash": "hidden"}}))
