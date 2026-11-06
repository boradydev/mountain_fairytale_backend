from src.feat.clients.app.abcs.client_uow_abcs import IClientsUOW
from src.feat.clients.app.usecases.get import GetClientDTO
from src.feat.clients.domain.client_excs import ClientNotFoundException
from src.feat.clients.domain.client_order_models import LatestOrder


class GetLatestOrderUseCase:
    def __init__(self, uow: IClientsUOW) -> None:
        self._uow = uow

    async def execute(self, dto: GetClientDTO) -> LatestOrder | None:
        async with self._uow as uow:
            if await uow.clients.get_by_id(dto.client_id) is None:
                raise ClientNotFoundException(client_id=dto.client_id)
            return await uow.clients.get_latest_order(dto.client_id)
