from typing import Annotated

from pydantic import Field

Quantity = Annotated[int, Field(gt=0)]
Price = Annotated[float, Field(ge=0)]
Mileage = Annotated[float, Field(ge=0)]
