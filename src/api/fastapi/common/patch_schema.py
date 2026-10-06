import types
from typing import Any, Union, get_args, get_origin, get_type_hints

from pydantic import Field, create_model, model_validator
from sqlalchemy.orm import Mapped

from src.api.fastapi.common.schemas import BaseSchema


_PATCH_NULLABLE_MARKER = "patch_nullable"


class StrictPatchModel(BaseSchema):
    """
    Базовая модель для PATCH-схем.

    Поля PATCH-схемы всегда необязательны:
    отсутствие поля означает «не изменять значение».

    Явный `null` разрешён только для nullable-полей.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_explicit_nulls(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data

        for field_name, field_info in cls.model_fields.items():
            if field_name not in data or data[field_name] is not None:
                continue

            extra = field_info.json_schema_extra or {}

            if extra.get(_PATCH_NULLABLE_MARKER) is False:
                raise ValueError(
                    f"Field '{field_name}' cannot be null.",
                )

        return data

    @model_validator(mode="before")
    @classmethod
    def validate_not_empty(cls, data: Any) -> Any:
        """Проверяет, что в PATCH-запросе передано хотя бы одно поле."""
        if isinstance(data, dict) and not data:
            raise ValueError("Request body cannot be empty.")
        return data


def _is_nullable(annotation: Any) -> bool:
    """Возвращает True, если тип допускает None."""
    origin = get_origin(annotation)

    if origin not in (Union, types.UnionType):
        return False

    return type(None) in get_args(annotation)


def _make_optional(annotation: Any) -> Any:
    """Делает тип необязательным для PATCH."""
    if _is_nullable(annotation):
        return annotation

    return annotation | None


def _unwrap_mapped(annotation: Any) -> Any:
    """Извлекает Python-тип из SQLAlchemy Mapped[T]."""
    if get_origin(annotation) is Mapped:
        return get_args(annotation)[0]

    return annotation


def create_patch_schema_for_domain(
    entity_cls: type[Any],
    *,
    exclude_fields: set[str] = None,
) -> type[BaseSchema]:
    """
    Создаёт PATCH-схему на основе SQLAlchemy-модели.

    `_ALLOWED_UPDATE_FIELDS` определяет поля,
    которые разрешено изменять.
    """
    fields_spec: dict[str, Any] = {}
    exclude_fields = exclude_fields or set()

    allowed_fields = getattr(
        entity_cls,
        "_ALLOWED_UPDATE_FIELDS",
        set(),
    )

    annotations = get_type_hints(entity_cls)

    for field_name in allowed_fields:
        if field_name not in annotations or field_name in exclude_fields:
            continue

        domain_type = _unwrap_mapped(
            annotations[field_name],
        )

        nullable = _is_nullable(domain_type)

        fields_spec[field_name] = (
            _make_optional(domain_type),
            Field(
                default=None,
                json_schema_extra={
                    _PATCH_NULLABLE_MARKER: nullable,
                },
            ),
        )

    return create_model(
        f"{entity_cls.__name__}PatchReq",
        __base__=StrictPatchModel,
        **fields_spec,
    )
