from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from src.common.domain.entities import BaseEntity
from src.common.domain.money import commission_amount


class PointCommission(BaseEntity):
    __tablename__ = "point_commissions"
    __table_args__ = (
        CheckConstraint("commission_percent BETWEEN 0 AND 100"),
        CheckConstraint("turnover >= 0"),
        CheckConstraint("commission_payable >= 0"),
    )

    point_id: Mapped[UUID] = mapped_column(ForeignKey("points.point_id", ondelete="CASCADE"), primary_key=True)
    sales_representative_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("sales_representatives.sales_representative_id"), nullable=True, index=True
    )
    commission_percent: Mapped[Decimal] = mapped_column(Numeric)
    turnover: Mapped[Decimal] = mapped_column(Numeric)
    commission_payable: Mapped[Decimal] = mapped_column(Numeric)

    def recalculate(self, turnover: Decimal) -> None:
        self.turnover = turnover
        self.commission_payable = commission_amount(turnover, self.commission_percent)


class DocumentEmployeeCommission(BaseEntity):
    __tablename__ = "document_employee_commissions"
    __table_args__ = (
        CheckConstraint("commission_percent BETWEEN 0 AND 100"),
        CheckConstraint("turnover >= 0"),
        CheckConstraint("commission_payable >= 0"),
    )

    delivery_document_id: Mapped[UUID] = mapped_column(
        ForeignKey("delivery_documents.delivery_document_id", ondelete="CASCADE"), primary_key=True
    )
    employee_id: Mapped[UUID] = mapped_column(ForeignKey("employees.employee_id"), primary_key=True)
    commission_percent: Mapped[Decimal] = mapped_column(Numeric)
    turnover: Mapped[Decimal] = mapped_column(Numeric)
    commission_payable: Mapped[Decimal] = mapped_column(Numeric)

    def recalculate(self, turnover: Decimal) -> None:
        self.turnover = turnover
        self.commission_payable = commission_amount(turnover, self.commission_percent)
