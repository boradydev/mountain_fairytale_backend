from src.core.excs import BaseAppException


class RepositoryException(BaseAppException):
    pass


class InvalidResultTypeException(RepositoryException):
    pass
