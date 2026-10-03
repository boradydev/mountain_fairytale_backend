import inflection
from pydantic import BaseModel, ConfigDict


class BaseSchemaOrigin(BaseModel):
    """Базовая схема с поддержкой snake_case."""


class BaseSchema(BaseSchemaOrigin):
    """Базовая схема с поддержкой camelCase."""

    model_config = ConfigDict(
        from_attributes=True,
        alias_generator=lambda s: inflection.camelize(s, uppercase_first_letter=False),
        populate_by_name=True,
    )


class StdResponse[Data](BaseSchema):
    offset: int | None = None
    limit: int | None = None
    total: int | None = None
    message: str | None = None
    data: Data | None = None
