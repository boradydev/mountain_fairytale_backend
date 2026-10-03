from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FastapiSettings:
    ROOT_PATH: str = "/api/v1"
