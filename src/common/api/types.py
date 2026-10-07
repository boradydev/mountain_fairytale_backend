from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Resp:
    status_code: int
    detail: str
