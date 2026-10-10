import types
from typing import Any, ClassVar, Union, get_args, get_origin

from pydantic import model_validator
from sqlalchemy import inspect

from src.common.api.schemas import BaseSchema


class BasePatchSchema(BaseSchema):
    """PATCH schema with explicit entity-field and composition contracts."""

    __entity__: ClassVar[type[Any] | None] = None
    __composition_fields__: ClassVar[set[str]] = set()

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
            if field_name in cls.__composition_fields__:
                continue
            column = mapper.columns.get(field_name)
            if column is not None and not column.nullable:
                raise ValueError(f"Field '{field_name}' cannot be null.")
        return data

    @classmethod
    def __pydantic_on_complete__(cls) -> None:
        super().__pydantic_on_complete__()
        if cls.__entity__ is not None:
            cls._validate_entity_contract()

    @classmethod
    def _validate_entity_contract(cls) -> None:
        entity = cls.__entity__
        if entity is None:
            return
        mapper = inspect(entity)
        allowed_fields = getattr(entity, "_ALLOWED_UPDATE_FIELDS", set())
        composition_fields = cls.__composition_fields__
        entity_fields = {column.key for column in mapper.columns}
        schema_fields = set(cls.model_fields)

        unknown = schema_fields - entity_fields - composition_fields
        if unknown:
            raise AttributeError(
                f"{cls.__name__}: fields do not exist in {entity.__name__}: "
                f"{', '.join(sorted(unknown))}",
            )
        forbidden = schema_fields - allowed_fields - composition_fields
        if forbidden:
            raise AttributeError(
                f"{cls.__name__}: fields are not allowed for update in "
                f"{entity.__name__}: {', '.join(sorted(forbidden))}",
            )
        for name, info in cls.model_fields.items():
            if not _is_nullable(info.annotation):
                raise TypeError(
                    f"{cls.__name__}.{name} must allow None so PATCH can "
                    "distinguish an omitted field from explicit null.",
                )

    def changes(self) -> dict[str, Any]:
        return self.model_dump(exclude_unset=True)


def _is_nullable(annotation: Any) -> bool:
    origin = get_origin(annotation)
    return origin in (Union, types.UnionType) and type(None) in get_args(annotation)
