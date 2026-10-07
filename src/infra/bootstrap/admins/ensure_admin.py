from src.app.common.abcs.services.password_service import IPasswordService
from src.feat.employees.app.abcs.employee_uow_abcs import IEmployeesUOW
from src.feat.employees.app.usecases.create import CreateEmployeeDTO, CreateEmployeeUseCase
from src.domain.common.const import SYSTEM_ACTOR_ID
from src.infra.bootstrap.admins.settings import AdminSettings


async def ensure_admin(
    *,
    uow: IEmployeesUOW,
    password_service: IPasswordService,
) -> None:
    settings = AdminSettings()
    async with uow as _uow:
        admin = await _uow.employees.get_by_username(settings.ADMIN_USERNAME)
        if admin is not None:
            return

        dto = CreateEmployeeDTO(
            actor_id=SYSTEM_ACTOR_ID,
            username=settings.ADMIN_USERNAME,
            password=settings.ADMIN_PASSWORD,
            role="admin",
        )

        use_case = CreateEmployeeUseCase(
            uow=_uow,
            password_service=password_service,
        )
        await use_case.execute(dto)
