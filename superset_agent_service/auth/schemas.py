"""Authentication and authorization data models."""

from pydantic import BaseModel, Field


class PermissionContext(BaseModel):
    user_id: str
    tenant_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_dataset_ids: list[str] = Field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        return "admin" in self.roles or "super_admin" in self.roles
