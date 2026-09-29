import logging

from fastapi import FastAPI

from src.presentation.fastapi.lifespan import lifespan


logger = logging.getLogger(__name__)

fastapi_app = FastAPI(lifespan=lifespan)
