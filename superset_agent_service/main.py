"""FastAPI application entrypoint for the Superset Agent Service.

Superset Agent Service 的 FastAPI 应用入口。
"""

from contextlib import asynccontextmanager
import logging
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, RedirectResponse
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from superset_agent_service.api.router import api_router
from superset_agent_service.config import settings

STATIC_DIR = Path(__file__).resolve().parent / "static"


def configure_logging() -> None:
    """Configure project loggers so Agent and MCP debug logs reach the console.

    配置项目日志器，让 Agent 与 MCP 调试日志能输出到控制台。
    """

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        force=False,
    )
    logging.getLogger("superset_agent_service").setLevel(level)


configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Provide the application lifespan hook for future startup resources.

    提供应用生命周期钩子，便于以后管理启动和关闭资源。
    """

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

if settings.ENVIRONMENT.lower() in {"local", "development", "test"}:
    # StaticFiles serves CSS and JavaScript without introducing a separate
    # frontend build tool.  The entire console is local-only because its MCP
    # tool caller intentionally exposes low-level development capabilities.
    # StaticFiles 无需额外前端构建工具即可提供 CSS 和 JavaScript。由于该控制台
    # 暴露了底层 MCP 调试能力，所以整个页面只在本地开发环境启用。
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        """Make the development console the convenient local entry point.

        将开发控制台设置为便捷的本地入口。
        """

        return RedirectResponse(url="/debug")

    @app.get("/debug", include_in_schema=False)
    async def debug_console() -> FileResponse:
        """Return the local Agent/MCP development console.

        返回本地 Agent/MCP 开发控制台页面。
        """

        return FileResponse(STATIC_DIR / "debug.html")

    @app.get("/usage", include_in_schema=False)
    async def usage_dashboard() -> FileResponse:
        """Return the local operational Usage Dashboard.

        返回本地 Agent 运营指标看板。
        """

        return FileResponse(STATIC_DIR / "usage.html")


if __name__ == "__main__":
    # Use the full import path here.  The previous "main:app" value only works
    # when the current directory is the package directory, while developers
    # normally start this command from the repository root.
    # 此处使用完整导入路径。原来的 "main:app" 仅在当前目录恰好是包目录时有效，
    # 而开发者通常会从仓库根目录启动服务。
    uvicorn.run(
        "superset_agent_service.main:app",
        # host="0.0.0.0",
        host="::",
        # port=settings.SERVER_PORT,
        port=9003,
        loop="asyncio",
        use_colors=True,
        reload=True,
    )
