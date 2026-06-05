"""Factory for creating a configured Superset MCP client."""

from superset_agent_service.config import settings
from superset_agent_service.tools.mcp_client import MCPClient


def get_superset_mcp_client() -> MCPClient | None:
    if settings.SUPERSET_MCP_URL is None:
        return None
    return MCPClient(
        base_url=str(settings.SUPERSET_MCP_URL),
        bearer_token=settings.SUPERSET_MCP_TOKEN,
    )
