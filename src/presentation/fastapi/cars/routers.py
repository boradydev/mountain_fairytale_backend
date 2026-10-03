from types import NoneType
from uuid import UUID

from fastapi import APIRouter, status

from src.app.cars.usecases.activate import ActivateCarDTO
from src.app.cars.usecases.check_duplicate import CheckCarDuplicateDTO
from src.app.cars.usecases.create import CreateCarDTO
from src.app.cars.usecases.deactivate import DeactivateCarDTO
from src.app.cars.usecases.get import GetCarDTO
from src.app.cars.usecases.update import UpdateCarDTO
from src.presentation.fastapi.common.deps import (
    AccessTokenPayloadDep,
    Context,
)
from src.presentation.fastapi.common.schemas import StdResponse
from src.presentation.fastapi.cars.schemas import (
    CarResp,
    CarsResp,
    CreateCarReq,
    UpdateCarReq,
)
from src.domain.cars.excs import CarNotFoundException, CarNumberAlreadyExistsException
from src.presentation.fastapi.common.handlers import map_exceptions_to_responses

GET_CAR_RESPONSES = map_exceptions_to_responses(CarNotFoundException)
GET_CARS_RESPONSES = map_exceptions_to_responses()
CREATE_CAR_RESPONSES = map_exceptions_to_responses(CarNumberAlreadyExistsException)
UPDATE_CAR_RESPONSES = map_exceptions_to_responses(CarNotFoundException, CarNumberAlreadyExistsException)
DELETE_CAR_RESPONSES = map_exceptions_to_responses(CarNotFoundException)
CHECK_DUPLICATE_RESPONSES = map_exceptions_to_responses()

cars_router = APIRouter(
    prefix="/cars",
    tags=["Автомобили"],
)


@cars_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[CarsResp],
    responses=GET_CARS_RESPONSES,
)
async def get_cars(
    ctx: Context,
) -> StdResponse[CarsResp]:
    cars = await ctx.cars_use_cases.get_cars().execute()

    return StdResponse(
        data=CarsResp(
            cars=[
                CarResp.model_validate(car)
                for car in cars
            ],
        ),
    )


@cars_router.get(
    "/check-duplicate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[CarResp | NoneType],
    responses=CHECK_DUPLICATE_RESPONSES,
)
async def check_duplicate(
    number: str,
    ctx: Context,
) -> StdResponse[CarResp | None]:
    car = await ctx.cars_use_cases.check_duplicate().execute(
        CheckCarDuplicateDTO(
            number=number,
        ),
    )

    return StdResponse(
        data=(
            CarResp.model_validate(car)
            if car is not None
            else None
        ),
    )


@cars_router.get(
    "/{car_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[CarResp],
    responses=GET_CAR_RESPONSES,
)
async def get_car(
    car_id: UUID,
    ctx: Context,
) -> StdResponse[CarResp]:
    car = await ctx.cars_use_cases.get_car().execute(
        GetCarDTO(
            car_id=car_id,
        ),
    )

    return StdResponse(
        data=CarResp.model_validate(car),
    )


@cars_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=StdResponse[CarResp],
    responses=CREATE_CAR_RESPONSES,
)
async def create_car(
    body: CreateCarReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[CarResp]:
    car = await ctx.cars_use_cases.create_car().execute(
        CreateCarDTO(
            actor_id=UUID(access_token_payload.employee_id),
            model=body.model,
            number=body.number,
            current_mileage=body.current_mileage,
        ),
    )

    return StdResponse(
        data=CarResp.model_validate(car),
    )


@cars_router.patch(
    "/{car_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[CarResp],
    responses=UPDATE_CAR_RESPONSES,
)
async def update_car(
    car_id: UUID,
    body: UpdateCarReq,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[CarResp]:
    car = await ctx.cars_use_cases.update_car().execute(
        UpdateCarDTO(
            actor_id=UUID(access_token_payload.employee_id),
            car_id=car_id,
            model=body.model,
            number=body.number,
            current_mileage=body.current_mileage,
        ),
    )

    return StdResponse(
        data=CarResp.model_validate(car),
    )


@cars_router.put(
    "/{car_id:uuid}/deactivate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
    responses=DELETE_CAR_RESPONSES,
)
async def deactivate_car(
    car_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[NoneType]:
    await ctx.cars_use_cases.deactivate_car().execute(
        DeactivateCarDTO(
            actor_id=UUID(access_token_payload.employee_id),
            car_id=car_id,
        ),
    )

    return StdResponse(
        message="Автомобиль деактивирован.",
    )


@cars_router.put(
    "/{car_id:uuid}/activate",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
    responses=DELETE_CAR_RESPONSES,
)
async def activate_car(
    car_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[NoneType]:
    await ctx.cars_use_cases.activate_car().execute(
        ActivateCarDTO(
            actor_id=UUID(access_token_payload.employee_id),
            car_id=car_id,
        ),
    )

    return StdResponse(
        message="Автомобиль активирован.",
    )
