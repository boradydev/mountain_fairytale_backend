import types
from typing import Any, ClassVar, Union, get_args, get_origin

from pydantic import model_validator
from sqlalchemy import inspect

from src.common.api.schemas import BaseSchema


class BasePatchSchema(BaseSchema):
    """
    Базовая схема для PATCH-запросов.

    Все поля PATCH-схемы должны быть объявлены явно.

    Правила:
    - отсутствие поля означает «не изменять»;
    - пустой объект запрещён;
    - `null` разрешён только для nullable-полей сущности;
    - поля должны существовать в SQLAlchemy-сущности;
    - поля должны входить в `_ALLOWED_UPDATE_FIELDS`.
    """

    __entity__: ClassVar[type[Any] | None] = None

    @model_validator(mode="before")
    @classmethod
    def validate_not_empty(cls, data: Any) -> Any:
        if isinstance(data, dict) and not data:
            raise ValueError("Request body cannot be empty.")

        return data

    @model_validator(mode="before")
    @classmethod
    def validate_explicit_nulls(cls, data: Any) -> Any:
        if not isinstance(data, dict) or cls.__entity__ is None:
            return data

        mapper = inspect(cls.__entity__)

        for field_name in cls.model_fields:
            if field_name not in data or data[field_name] is not None:
                continue

            column = mapper.columns.get(field_name)

            if column is None:
                continue

            if not column.nullable:
                raise ValueError(
                    f"Field '{field_name}' cannot be null.",
                )

        return data

    @classmethod
    def __pydantic_on_complete__(cls) -> None:
        super().__pydantic_on_complete__()

        if cls.__entity__ is None:
            return

        cls._validate_entity_contract()

    @classmethod
    def _validate_entity_contract(cls) -> None:
        entity = cls.__entity__

        if entity is None:
            return

        mapper = inspect(entity)

        allowed_fields = getattr(
            entity,
            "_ALLOWED_UPDATE_FIELDS",
            set(),
        )

        entity_fields = {
            column.key
            for column in mapper.columns
        }

        schema_fields = set(cls.model_fields)

        unknown_fields = schema_fields - entity_fields

        if unknown_fields:
            fields = ", ".join(sorted(unknown_fields))
            raise AttributeError(
                f"{cls.__name__}: fields do not exist "
                f"in {entity.__name__}: {fields}",
            )

        forbidden_fields = schema_fields - allowed_fields

        if forbidden_fields:
            fields = ", ".join(sorted(forbidden_fields))
            raise AttributeError(
                f"{cls.__name__}: fields are not allowed "
                f"for update in {entity.__name__}: {fields}",
            )

        for field_name, field_info in cls.model_fields.items():
            if not _is_nullable(field_info.annotation):
                raise TypeError(
                    f"{cls.__name__}.{field_name} must allow None "
                    "because PATCH fields must distinguish "
                    "an omitted field from an explicit null.",
                )

    def changes(self) -> dict[str, Any]:
        """Возвращает только поля, переданные в PATCH-запросе."""
        return self.model_dump(exclude_unset=True)


def _is_nullable(annotation: Any) -> bool:
    origin = get_origin(annotation)

    if origin not in (Union, types.UnionType):
        return False

    return type(None) in get_args(annotation)