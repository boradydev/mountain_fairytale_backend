from fastapi import APIRouter, Depends

from src.api.fastapi.auth.auth_routers import auth_router
from src.api.fastapi.cars.car_routers import cars_router
from src.api.fastapi.common.deps import verify_access_token, verify_admin_access
from src.api.fastapi.drivers.driver_routers import drivers_router
from src.api.fastapi.employees.employee_routers import employees_router
from src.api.fastapi.me.me_routers import me_router


public = APIRouter(
    prefix="/public",
)

public.include_router(auth_router)


protected = APIRouter(
    prefix="/protected",
    dependencies=[Depends(verify_access_token)]
)

protected.include_router(me_router)
protected.include_router(cars_router)
protected.include_router(drivers_router)


admin = APIRouter(
    prefix="/admin",
    dependencies=[Depends(verify_admin_access)]
)

admin.include_router(employees_router)
