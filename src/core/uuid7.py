import uuid

import uuid6


def uuid7() -> uuid.UUID:
    """
    Генерирует UUIDv7 и возвращает его как стандартный объект uuid.UUID.

    Это решает проблему с generic-типизацией библиотеки uuid6 в pyright.
    """
    # Конструктор uuid.UUID принимает сырые байты или строку от uuid6
    return uuid.UUID(bytes=uuid6.uuid7().bytes)
