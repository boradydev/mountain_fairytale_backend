from fastapi import APIRouter

from src.presentation.fastapi.employees.routers import (
    # auth_router,
    employees_router,
    # me_router,
)


public = APIRouter(
    prefix="/public",
)

# public.include_router(auth_router)

protected = APIRouter(
    prefix="/protected",
)
# protected.include_router(me_router)
protected.include_router(employees_router)
