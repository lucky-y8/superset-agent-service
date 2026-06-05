"""Minimal MCP client boundary for calling external MCP tools."""

import httpx


class MCPClient:
    def __init__(self, base_url: str, bearer_token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.bearer_token = bearer_token

    async def call_tool(
        self, name: str, arguments: dict[str, object]
    ) -> dict[str, object]:
        headers = {}
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                self.base_url,
                headers=headers,
                json={"method": "tools/call", "params": {"name": name, "arguments": arguments}},
            )
            response.raise_for_status()
            return response.json()
