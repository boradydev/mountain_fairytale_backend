from uuid import UUID

from src.common.api.schemas import BaseSchema


class CurrentEmployeeResp(BaseSchema):
    employee_id: UUID
    username: str
    role: str
