import asyncio
import sys
from contextlib import asynccontextmanager

import uvicorn
# Windows 系统需要设置事件循环策略
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from starlette.middleware.cors import CORSMiddleware

from initialization import api_router
from config import settings
from listening_ripples.utilities.network import log_network_info


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

settings.SERVER_PORT = 30011

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
     FastAPI 的应用生命周期钩子。
    """
    # 应用启动时执行 可以做些 初始化数据库连接、加载模型、打印日志
    log_network_info(settings.SERVER_PORT)
    yield
    # 应用关闭时执行（yield 之后） 可以做些 关闭数据库连接、释放资源、清理缓存
    ...

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)

if __name__ == "__main__":

    # ipv4
    # uvicorn.run(app, host="0.0.0.0", port=30011)


    # ipv6
    # 使用 "main:app" 字符串形式启动，这有助于 Uvicorn 在正确的上下文中初始化
    # 同时明确指定 loop 为 asyncio
    uvicorn.run(
        "main:app",
        host="::",
        port=settings.SERVER_PORT,
        loop="asyncio",
        use_colors=True,
        reload=True  # 开发模式建议开启
    )