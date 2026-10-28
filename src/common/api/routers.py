from fastapi import APIRouter, Depends

from src.common.api.client_compatibility import app_info_router, require_client_version
from src.common.api.deps import get_access_token_pyload, verify_admin_access
from src.common.api.monitoring_routers import monitoring_router
from src.feat.audit_event.api.audit_routers import events_router
from src.feat.auth.api.auth_routers import auth_router
from src.feat.cars.api.car_routers import cars_router
from src.feat.clients.api.client_routers import clients_router
from src.feat.clients.api.location_routers import location_router
from src.feat.commissions.api.commission_routers import commissions_router
from src.feat.dashboard_updates.api.dashboard_updates_routers import dashboard_updates_router
from src.feat.delivery_document.api.delivery_day_routers import delivery_days_router
from src.feat.delivery_document.api.delivery_document_routers import (
    delivery_route_sheets_router,
    pickup_sheets_router,
)
from src.feat.drivers.api.driver_routers import drivers_router
from src.feat.employees.api.employee_routers import employees_router
from src.feat.me.me_routers import me_router
from src.feat.pay_methods.api.pay_method_routers import payment_methods_router
from src.feat.products.api.product_routers import products_router
from src.feat.sales_rep.api.sales_rep_routers import sales_representatives_router


public = APIRouter(prefix="/public")
public.include_router(auth_router, dependencies=[Depends(require_client_version)])
public.include_router(app_info_router)
public.include_router(monitoring_router)


protected = APIRouter(
    prefix="/protected",
    dependencies=[Depends(require_client_version), Depends(get_access_token_pyload)],
)
protected.include_router(location_router)
protected.include_router(me_router)
protected.include_router(events_router)
protected.include_router(cars_router)
protected.include_router(clients_router)
protected.include_router(commissions_router)
protected.include_router(delivery_days_router)
protected.include_router(dashboard_updates_router)
protected.include_router(delivery_route_sheets_router)
protected.include_router(pickup_sheets_router)
protected.include_router(drivers_router)
protected.include_router(payment_methods_router)
protected.include_router(products_router)
protected.include_router(sales_representatives_router)


admin = APIRouter(
    prefix="/admin",
    dependencies=[Depends(require_client_version), Depends(verify_admin_access)],
)
admin.include_router(employees_router)
