import types
from typing import Any, Union, get_args, get_origin, get_type_hints

from pydantic import Field, create_model, model_validator

from src.api.fastapi.common.schemas import BaseSchema


_PATCH_NULLABLE_MARKER = "patch_nullable"


class StrictPatchModel(BaseSchema):
    """
    Базовая модель для PATCH-схем.

    Поля PATCH-схемы всегда являются необязательными:
    отсутствие поля означает «не изменять значение».

    При этом явный `null` разрешён только для тех полей,
    которые nullable в доменной модели.
    """

    @model_validator(mode="before")
    @classmethod
    def validate_explicit_nulls(cls, data: Any) -> Any:
        """
        Запрещает явный `null` для non-nullable полей.

        Важно:
        - отсутствие поля разрешено;
        - `field=None` разрешено только если доменный тип допускает None;
        - обычный `ValueError` автоматически преобразуется Pydantic
          в стандартный ValidationError.
        """
        if not isinstance(data, dict):
            return data

        for field_name, field_info in cls.model_fields.items():
            if field_name not in data:
                continue

            if data[field_name] is not None:
                continue

            extra = field_info.json_schema_extra or {}

            if extra.get(_PATCH_NULLABLE_MARKER) is False:
                raise ValueError(f"Поле '{field_name}' не может быть null.")

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


def create_patch_schema_for_domain(
    entity_cls: type[Any],
) -> type[BaseSchema]:
    """
    Создаёт Pydantic-схему PATCH для доменной сущности.

    `_ALLOWED_UPDATE_FIELDS` определяет поля, которые разрешено изменять.

    Для каждого поля:
    - отсутствие поля означает «не изменять»;
    - `null` разрешён только если доменный тип допускает None;
    - тип значения берётся непосредственно из доменной модели.
    """
    fields_spec: dict[str, Any] = {}

    allowed_fields = getattr(
        entity_cls,
        "_ALLOWED_UPDATE_FIELDS",
        set(),
    )

    # get_type_hints() надёжнее __annotations__:
    # разрешает forward references и учитывает типизацию класса.
    annotations = get_type_hints(entity_cls)

    for field_name in allowed_fields:
        private_field_name = f"_{field_name}"

        if private_field_name not in annotations:
            continue

        domain_type = annotations[private_field_name]
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
