import logging

from fastapi import FastAPI

from src.common.api import routers
from src.common.api.exc_map import APP_EXCEPTION_MAP
from src.common.api.excs_handlers import (
    get_business_exception_handler,
    get_unknown_exception_handler,
)
from src.common.api.health_routers import health_router
from src.common.api.lifespan import lifespan
from src.common.api.request_ids import install_request_ids
from src.common.api.settings import FastapiSettings
from src.core.build_info import APP_VERSION
from src.core.excs import BaseAppException
from src.core.monitoring import initialize_monitoring


logger = logging.getLogger(__name__)

settings = FastapiSettings()
initialize_monitoring()
fastapi_app = FastAPI(lifespan=lifespan, version=APP_VERSION)
fastapi_app.root_path = settings.ROOT_PATH
install_request_ids(fastapi_app)

fastapi_app.add_exception_handler(
    BaseAppException,
    get_business_exception_handler(APP_EXCEPTION_MAP, logger=logger),
)
fastapi_app.add_exception_handler(
    Exception,
    get_unknown_exception_handler(logger=logger),
)

fastapi_app.include_router(routers.public)
fastapi_app.include_router(routers.protected)
fastapi_app.include_router(routers.admin)
fastapi_app.include_router(health_router)
