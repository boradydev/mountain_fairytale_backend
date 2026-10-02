import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError

from src.core.excs import BaseAppException
from src.presentation.fastapi.common import routers
from src.presentation.fastapi.common.handlers import get_business_exception_handler, \
    validation_exception_handler, get_unknown_exception_handler
from src.presentation.fastapi.employees.handlers import EMPLOYEE_EXCEPTION_MAP
from src.presentation.fastapi.lifespan import lifespan
from src.presentation.fastapi.settings import FastapiSettings

logger = logging.getLogger(__name__)

settings = FastapiSettings()
fastapi_app = FastAPI(lifespan=lifespan)
fastapi_app.root_path = settings.ROOT_PATH

fastapi_app.add_exception_handler(
    BaseAppException,
    get_business_exception_handler(EMPLOYEE_EXCEPTION_MAP),
)
fastapi_app.add_exception_handler(
    RequestValidationError,
    validation_exception_handler,
)
fastapi_app.add_exception_handler(
    Exception,
    get_unknown_exception_handler(logger=logger),
)

fastapi_app.include_router(routers.public)
fastapi_app.include_router(routers.protected)
