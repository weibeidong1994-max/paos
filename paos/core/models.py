from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field


class InputItem(BaseModel):
    """输入层原始数据模型"""

    source: str = Field(..., description="输入来源标识，如 natural_language / openclaw / xiaohongshu")
    content: str = Field(..., description="原始内容")
    metadata: dict[str, Any] = Field(default_factory=dict, description="附加元数据")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProcessedItem(BaseModel):
    """处理层提纯后的数据模型"""

    id: int | None = None
    source: str
    raw_content: str
    distilled_content: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GenerationRequest(BaseModel):
    """输出层生成请求"""

    adapter: str = Field(default="article", description="输出适配器名称")
    limit: int = Field(default=5, ge=1, le=50, description="使用的最近条目数")
    prompt_override: str | None = Field(default=None, description="可选的自定义提示词")


class CreateInputRequest(BaseModel):
    """通用输入接口请求模型"""

    source: str = Field(..., description="输入来源标识")
    data: dict[str, Any] = Field(default_factory=dict, description="原始数据负载")


class GenerationResult(BaseModel):
    """输出层生成结果"""

    adapter: str
    content: str
    file_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
