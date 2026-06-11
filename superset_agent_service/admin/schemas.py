"""Schemas for administrative runtime configuration APIs.

管理端运行时配置接口使用的数据模型。
"""

from pydantic import BaseModel


class RuntimeConfig(BaseModel):
    """Represent the safe subset of Runtime configuration returned by the API.

    表示接口可安全返回的 Runtime 配置子集。
    """

    default_model_provider: str
    default_model_name: str
    max_agent_steps: int
    max_run_seconds: int
