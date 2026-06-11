"""Authentication and authorization data models.

身份认证与权限控制相关的数据模型。
"""

from pydantic import BaseModel, Field


class PermissionContext(BaseModel):
    """Describe the identity and resource permissions of one request.

    描述一次请求的身份信息与资源权限。
    """

    user_id: str
    tenant_id: str | None = None
    roles: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_dataset_ids: list[str] = Field(default_factory=list)

    @property
    def is_admin(self) -> bool:
        """Return whether the current identity has an administrator role.

        返回当前身份是否具有管理员角色。
        """

        return "admin" in self.roles or "super_admin" in self.roles
