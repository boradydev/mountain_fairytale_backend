from types import NoneType
from uuid import UUID

from fastapi import APIRouter, status

from src.app.cars.usecases.check_duplicate import CheckCarDuplicateDTO
from src.app.cars.usecases.create import CreateCarDTO
from src.app.cars.usecases.delete import DeleteCarDTO
from src.app.cars.usecases.get import GetCarDTO
from src.app.cars.usecases.update import UpdateCarDTO
from src.presentation.fastapi.common.deps import (
    AccessTokenPayloadDep,
    Context,
)
from src.presentation.fastapi.common.schemas import StdResponse
from src.presentation.fastapi.cars import responses
from src.presentation.fastapi.cars.schemas import (
    CarResp,
    CarsResp,
    CreateCarReq,
    UpdateCarReq,
)


cars_router = APIRouter(
    prefix="/cars",
    tags=["Автомобили"],
)


@cars_router.get(
    "",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[CarsResp],
    responses=responses.GET_CARS,
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
    responses=responses.CHECK_DUPLICATE,
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
    responses=responses.GET_CAR,
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
    responses=responses.CREATE_CAR,
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
    responses=responses.UPDATE_CAR,
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


@cars_router.delete(
    "/{car_id:uuid}",
    status_code=status.HTTP_200_OK,
    response_model=StdResponse[NoneType],
    responses=responses.DELETE_CAR,
)
async def delete_car(
    car_id: UUID,
    ctx: Context,
    access_token_payload: AccessTokenPayloadDep,
) -> StdResponse[NoneType]:
    await ctx.cars_use_cases.delete_car().execute(
        DeleteCarDTO(
            actor_id=UUID(access_token_payload.employee_id),
            car_id=car_id,
        ),
    )

    return StdResponse(
        message="Автомобиль удалён.",
    )