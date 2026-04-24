import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from paos.api.router import router
from paos.config.settings import settings
from paos.skills.router import router as skills_router
from paos.storage.sqlite_store import SQLiteStorage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.data_dir, exist_ok=True)
    os.makedirs(os.path.join(settings.data_dir, "raw"), exist_ok=True)
    os.makedirs(os.path.join(settings.data_dir, "processed"), exist_ok=True)
    os.makedirs(os.path.join(settings.data_dir, "output"), exist_ok=True)
    os.makedirs(os.path.join(settings.data_dir, "fallback_queue"), exist_ok=True)

    storage = SQLiteStorage()
    storage.init_db()
    logger.info("PAOS startup complete. Data dir: %s", settings.data_dir)
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="Personal AI OS - 个人AI操作系统",
        lifespan=lifespan,
    )
    app.include_router(router)
    app.include_router(skills_router)
    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "paos.main:app",
        host=settings.server.host,
        port=settings.server.port,
        reload=True,
    )
