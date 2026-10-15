from abc import abstractmethod

from src.common.app.abcs.uow_abcs import InterfaceUOW
from src.feat.commissions.domain.commission_repo_abcs import ICommissionsRepository


class ICommissionsUOW(InterfaceUOW):
    @property
    @abstractmethod
    def commissions(self) -> ICommissionsRepository: ...
