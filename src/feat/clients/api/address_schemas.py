from typing import Annotated, Literal

from pydantic import ConfigDict, Field, StringConstraints, model_validator

from src.common.api.schemas import BaseSchema


AddressPart = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=150)]


class AddressSearchReq(BaseSchema):
    model_config = ConfigDict(extra="forbid")

    district: Annotated[str, StringConstraints(strip_whitespace=True, max_length=150)] = ""
    locality: AddressPart
    street: AddressPart
    house: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]

    @model_validator(mode="after")
    def validate_address_length(self):
        if len(self.formatted) > 500:
            raise ValueError("Full address must not exceed 500 characters")
        return self

    @property
    def formatted(self) -> str:
        return ", ".join(part for part in (self.district, self.locality, self.street, self.house) if part)


class DeliveryAddress(AddressSearchReq):
    latitude: Annotated[float, Field(ge=43.4, le=46.6, allow_inf_nan=False)]
    longitude: Annotated[float, Field(ge=40.8, le=45.9, allow_inf_nan=False)]
    confirmed: Literal[True]
    source: Literal["geoapify", "manual"]


class AddressCandidate(BaseSchema):
    formatted: str
    latitude: float
    longitude: float
    confidence: float
    exact_house: bool


class AddressSearchResp(BaseSchema):
    candidates: list[AddressCandidate]
    attribution: str = "Powered by Geoapify; © OpenStreetMap contributors"
