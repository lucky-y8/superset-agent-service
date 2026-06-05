"""FastAPI application entrypoint for the Superset Agent Service."""

from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from superset_agent_service.api.router import api_router
from superset_agent_service.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

if __name__ == "__main__":

    # ipv4
    # uvicorn.run(app, host="0.0.0.0", port=30011)


    # ipv6
    # 使用 "main:app" 字符串形式启动，这有助于 Uvicorn 在正确的上下文中初始化
    # 同时明确指定 loop 为 asyncio
    uvicorn.run(
        "main:app",
        # host="::",
        host="0.0.0.0",
        port=settings.SERVER_PORT,
        loop="asyncio",
        use_colors=True,
        reload=True  # 开发模式建议开启
    )
