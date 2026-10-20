from dataclasses import dataclass

from src.core.excs import BaseAppException


class GeoUnavailable(BaseAppException):
    pass


class GeoQuotaExceeded(BaseAppException):
    pass


class InvalidGeoResponse(BaseAppException):
    pass


@dataclass(slots=True)
class MissingClientLocation(BaseAppException):
    clients: list[dict[str, str]]
