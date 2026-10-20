from src.core.excs import BaseAppException


class GeoUnavailable(BaseAppException):
    pass


class GeoQuotaExceeded(BaseAppException):
    pass


class InvalidGeoResponse(BaseAppException):
    pass


class MissingClientLocation(BaseAppException):
    def __init__(self, clients: list[dict[str, str]]) -> None:
        self.clients = clients
