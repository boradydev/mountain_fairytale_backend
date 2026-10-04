from fastapi import APIRouter

from src.api.fastapi.auth.auth_routers import auth_router
from src.api.fastapi.cars.car_routers import cars_router
from src.api.fastapi.employees.employee_routers import employees_router
from src.api.fastapi.me.me_routers import me_router


public = APIRouter(
    prefix="/public",
)

public.include_router(auth_router)


protected = APIRouter(
    prefix="/protected",
)

protected.include_router(me_router)
protected.include_router(employees_router)
protected.include_router(cars_router)