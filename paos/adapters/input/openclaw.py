from paos.adapters.input.base import BaseInputAdapter
from paos.core.models import InputItem


class OpenClawAdapter(BaseInputAdapter):
    """OpenClaw Webhook 输入适配器

    预期 OpenClaw 推送的数据格式示例：
    {
        "text": "用户通过手机发送的文本",
        "media_url": null,
        "timestamp": "2024-...",
        "sender_id": "user_123"
    }

    容错策略：
    - text 为空时，尝试读取 content 或 message 字段作为 fallback
    - sender_id、media_url、timestamp 缺失时使用 None 默认值
    """

    name = "openclaw"

    def parse(self, raw_data: dict) -> InputItem:
        # 提取 text，支持多个备选字段
        text = raw_data.get("text") or raw_data.get("content") or raw_data.get("message")

        if not text:
            raise ValueError(
                "OpenClaw adapter: 缺少文本内容。"
                "Expected 'text' field, or fallback 'content'/'message'."
            )

        # 可选字段，缺失时使用 None (.get() 默认返回 None)
        sender_id = raw_data.get("sender_id")
        media_url = raw_data.get("media_url")
        timestamp = raw_data.get("timestamp")

        return InputItem(
            source=self.name,
            content=text,
            metadata={
                "sender_id": sender_id,
                "media_url": media_url,
                "openclaw_timestamp": timestamp,
            },
        )
