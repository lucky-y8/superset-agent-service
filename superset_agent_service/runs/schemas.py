"""Schemas that describe run lifecycle traces and their events.

描述运行生命周期轨迹及其事件的数据模型。
"""

from datetime import UTC, datetime
from pydantic import BaseModel, Field


class RunEvent(BaseModel):
    """Represent one timestamped event emitted during an Agent run.

    表示 Agent 运行期间产生的一条带时间戳事件。
    """

    event_type: str
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class RunTrace(BaseModel):
    """Collect the current status and durable events of one Agent run.

    汇总一次 Agent 运行的当前状态和持久化事件。
    """

    run_id: str
    user_id: str
    status: str
    events: list[RunEvent] = Field(default_factory=list)
