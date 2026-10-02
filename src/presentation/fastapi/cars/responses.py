from src.domain.cars.excs import (
    CarNotFoundException,
    CarNumberAlreadyExistsException,
)
from src.presentation.fastapi.common.handlers import get_swagger_exc


GET_CAR = get_swagger_exc(
    CarNotFoundException,
)

GET_CARS = get_swagger_exc()

CREATE_CAR = get_swagger_exc(
    CarNumberAlreadyExistsException,
)

UPDATE_CAR = get_swagger_exc(
    CarNotFoundException,
    CarNumberAlreadyExistsException,
)

DELETE_CAR = get_swagger_exc(
    CarNotFoundException,
)

CHECK_DUPLICATE = get_swagger_exc()