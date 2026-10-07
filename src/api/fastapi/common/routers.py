from fastapi import APIRouter, Depends

from src.feat.auth.api.auth_routers import auth_router
from src.feat.cars.api.car_routers import cars_router
from src.api.fastapi.common.deps import verify_access_token, verify_admin_access
from src.feat.drivers.api.driver_routers import drivers_router
from src.feat.employees.api.employee_routers import employees_router
from src.api.fastapi.me.me_routers import me_router
from src.feat.pay_methods.api.pay_method_routers import payment_methods_router
from src.feat.products.api.product_routers import products_router
from src.feat.sales_rep.api.sales_rep_routers import sales_representatives_router


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
protected.include_router(payment_methods_router)
protected.include_router(products_router)
protected.include_router(sales_representatives_router)


admin = APIRouter(
    prefix="/admin",
    dependencies=[Depends(verify_admin_access)]
)

admin.include_router(employees_router)
