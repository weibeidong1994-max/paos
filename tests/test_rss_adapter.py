import pytest

from paos.adapters.input.rss import RSSAdapter
from paos.core.models import InputItem

SAMPLE_RSS = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>First Post</title>
      <description>This is the first post.</description>
      <link>https://example.com/1</link>
    </item>
    <item>
      <title>Second Post</title>
      <description>This is the second post.</description>
      <link>https://example.com/2</link>
    </item>
  </channel>
</rss>
"""


def test_rss_adapter_parses_first_item():
    adapter = RSSAdapter()
    item = adapter.parse({"content": SAMPLE_RSS})

    assert item.source == "rss"
    assert "Test Feed" in item.content
    assert "First Post" in item.content
    assert "https://example.com/1" in item.content
    assert item.metadata["total_entries"] == 2
    assert item.metadata["feed_title"] == "Test Feed"
    assert item.metadata["item_link"] == "https://example.com/1"


def test_rss_adapter_missing_content():
    adapter = RSSAdapter()
    with pytest.raises(ValueError, match="RSS content is required"):
        adapter.parse({})


def test_rss_adapter_invalid_xml():
    adapter = RSSAdapter()
    with pytest.raises(ValueError, match="Invalid RSS XML"):
        adapter.parse({"content": "<not valid xml"})


def test_rss_adapter_no_channel():
    adapter = RSSAdapter()
    xml = "<rss version='2.0'><item><title>Orphan</title></item></rss>"
    with pytest.raises(ValueError, match="missing <channel>"):
        adapter.parse({"content": xml})


def test_rss_adapter_no_items():
    adapter = RSSAdapter()
    xml = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Empty Feed</title>
  </channel>
</rss>
"""
    with pytest.raises(ValueError, match="no <item> entries"):
        adapter.parse({"content": xml})


def test_rss_adapter_item_without_description():
    """当 item 缺少 description 时，应尝试读取 summary；都缺失则置为空"""
    adapter = RSSAdapter()
    xml = """<?xml version="1.0"?>
<rss version="2.0">
  <channel>
    <title>Minimal Feed</title>
    <item>
      <title>Only Title</title>
      <link>https://example.com/3</link>
    </item>
  </channel>
</rss>
"""
    item = adapter.parse({"content": xml})
    assert item.source == "rss"
    assert "Minimal Feed" in item.content
    assert "Only Title" in item.content
    assert "https://example.com/3" in item.content
    # description 为空，content 中应只有标题和链接
    assert "原文：" in item.content
