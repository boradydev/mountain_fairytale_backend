from decimal import Decimal

import pytest

from src.core.uuid7 import uuid7
from src.feat.commissions.domain.commission_entities import PointCommission
from src.feat.delivery_document.api.delivery_document_schemas import UpdatePointReq
from src.feat.delivery_document.domain.delivery_document_entities import Point
from src.feat.delivery_document.domain.delivery_document_excs import DeliveryDocumentUpdateException
from src.feat.sales_rep.domain.sales_rep_entities import SalesRepresentative


def unassigned():
    point = Point(point_id=uuid7(), client_id=uuid7(), snapshot_sales_representative_id=None)
    point.commission = PointCommission(
        point_id=point.point_id,
        sales_representative_id=None,
        commission_percent=Decimal(0),
        turnover=Decimal("100.10"),
        commission_payable=Decimal(0),
    )
    return point


@pytest.mark.parametrize("rate", [Decimal(0), Decimal("2.5")])
def test_assignment_freezes_rate_and_audits_snapshot(rate):
    point = unassigned()
    rep = SalesRepresentative(sales_representative_id=uuid7(), is_active=True, commission_percent=rate)
    point.assign_missing_representative(actor_id=uuid7(), representative=rep)
    assert point.snapshot_sales_representative_id == rep.sales_representative_id
    assert point.commission.sales_representative_id == rep.sales_representative_id
    assert point.commission.commission_percent == rate
    event = point.pull_events()[0]
    assert event.changes["snapshot_sales_representative_id"].old is None
    assert event.changes["snapshot_sales_representative_id"].new == rep.sales_representative_id
    rep.commission_percent = Decimal(99)
    point.commission.recalculate(Decimal("100.10"))
    assert point.commission.commission_payable == Decimal("100.10") * rate / 100
    with pytest.raises(DeliveryDocumentUpdateException):
        point.assign_missing_representative(actor_id=uuid7(), representative=rep)


def test_omission_is_distinct_from_explicit_null():
    assert "sales_representative_id" not in UpdatePointReq(items=[]).model_fields_set
    assert "sales_representative_id" in UpdatePointReq(items=[], salesRepresentativeId=None).model_fields_set
