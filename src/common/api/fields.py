from decimal import Decimal
from typing import Annotated

from pydantic import Field


Quantity = Annotated[int, Field(gt=0)]
Price = Annotated[Decimal, Field(ge=0)]
Mileage = Annotated[float, Field(ge=0)]
Position = Annotated[int, Field(gt=0, le=100000)]
