from fastapi import APIRouter

from src.presentation.fastapi.auth.routers import auth_router
from src.presentation.fastapi.cars.routers import cars_router
from src.presentation.fastapi.employees.routers import employees_router
from src.presentation.fastapi.me.routers import me_router


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