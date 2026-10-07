from uuid import uuid4
from src.core.uuid7 import uuid7

def unique_username(prefix: str = "test") -> str:
    # Берем последние 12 символов hex-строки
    return f"{prefix}_{uuid7().hex[-12:]}"

def unique_car_number(prefix: str = "A") -> str:
    # Берем последние 8 символов hex-строки и переводим в верхний регистр
    return f"{prefix}{uuid7().hex[-8:].upper()}XX"

def unique_phone() -> str:
    return uuid4().hex
