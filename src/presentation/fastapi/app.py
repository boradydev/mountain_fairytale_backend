import logging

from fastapi import FastAPI

from src.presentation.fastapi.common import routers
from src.presentation.fastapi.lifespan import lifespan
from src.presentation.fastapi.settings import FastapiSettings

logger = logging.getLogger(__name__)

settings = FastapiSettings()
fastapi_app = FastAPI(lifespan=lifespan)
fastapi_app.root_path = settings.ROOT_PATH

fastapi_app.include_router(routers.public)
fastapi_app.include_router(routers.protected)
