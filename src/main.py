import logging

import dotenv
import uvicorn

from src.core.app_logger import logger_config
from src.settings import UvicornSettings


if __name__ == "__main__":
    dotenv.load_dotenv()
    settings = UvicornSettings()
    logger_config()
    uvicorn.run(
        app="src.common.api.app:fastapi_app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=False,
        workers=None,
        factory=False,
    )
