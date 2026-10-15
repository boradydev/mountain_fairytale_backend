from src.common.domain.excs import DomainException


class InactiveCommissionTargetException(DomainException):
    pass


class SameCommissionTargetException(DomainException):
    pass
