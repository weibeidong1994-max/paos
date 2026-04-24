from paos.adapters.input.base import BaseInputAdapter
from paos.core.models import InputItem

import xml.etree.ElementTree as ET


class RSSAdapter(BaseInputAdapter):
    """RSS 输入适配器，解析 RSS 2.0 XML 格式"""

    name = "rss"

    def parse(self, raw_data: dict) -> InputItem:
        # 支持直接传入 RSS XML 字符串
        rss_content = raw_data.get("content")
        if not rss_content:
            raise ValueError("RSS content is required (field: 'content')")

        try:
            root = ET.fromstring(rss_content)
        except ET.ParseError as e:
            raise ValueError(f"Invalid RSS XML: {e}") from e

        # 查找 channel/title
        channel = root.find("channel")
        if channel is None:
            raise ValueError("Invalid RSS: missing <channel> element")

        feed_title_elem = channel.find("title")
        feed_title = feed_title_elem.text if feed_title_elem is not None else "Untitled Feed"

        # 查找所有 item，取第一个
        items = channel.findall("item")
        if not items:
            raise ValueError("RSS feed has no <item> entries")

        first_item = items[0]

        item_title_elem = first_item.find("title")
        item_title = item_title_elem.text if item_title_elem is not None else ""

        item_desc_elem = first_item.find("description")
        # description 可能缺失，尝试 summary
        if item_desc_elem is None:
            item_desc_elem = first_item.find("summary")
        item_description = item_desc_elem.text if item_desc_elem is not None else ""

        item_link_elem = first_item.find("link")
        item_link = item_link_elem.text if item_link_elem is not None else ""

        # 构造 content 字符串
        content = f"【{feed_title}】{item_title}\n\n{item_description}\n\n原文：{item_link}"

        metadata = {
            "feed_title": feed_title,
            "item_link": item_link,
            "total_entries": len(items),
        }

        return InputItem(
            source=self.name,
            content=content,
            metadata=metadata,
        )
