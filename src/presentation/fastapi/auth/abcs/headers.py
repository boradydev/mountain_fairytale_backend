from abc import ABC, abstractmethod


class ISystemHeaderManager(ABC):
    @property
    @abstractmethod
    def user_agent(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def ip_address(self) -> str:
        raise NotImplementedError
