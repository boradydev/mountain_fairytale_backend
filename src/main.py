import dotenv
import uvicorn

from src.settings import UvicornSettings


if __name__ == "__main__":
    dotenv.load_dotenv()
    settings = UvicornSettings()
    uvicorn.run(
        app=settings.FASTAPI_APP,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=False,
        workers=None,
        factory=False,
    )
