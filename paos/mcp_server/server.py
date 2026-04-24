"""
PAOS MCP Server — 基于 FastMCP
支持 stdio 和 sse 两种传输模式
"""

from mcp.server.fastmcp import FastMCP

from paos.mcp_server.tools import (
    paos_add_note,
    paos_complete_fallback,
    paos_generate_article,
    paos_get_processed,
    paos_health_check,
    paos_list_fallback,
    paos_list_index,
    paos_list_search_engines,
    paos_regenerate_summary,
    paos_update_tags,
    paos_web_search,
    paos_web_search_and_ingest,
)

mcp = FastMCP("paos")

mcp.add_tool(paos_list_index, name="paos_list_index")
mcp.add_tool(paos_list_fallback, name="paos_list_fallback")
mcp.add_tool(paos_get_processed, name="paos_get_processed")
mcp.add_tool(paos_health_check, name="paos_health_check")
mcp.add_tool(paos_add_note, name="paos_add_note")
mcp.add_tool(paos_complete_fallback, name="paos_complete_fallback")
mcp.add_tool(paos_update_tags, name="paos_update_tags")
mcp.add_tool(paos_regenerate_summary, name="paos_regenerate_summary")
mcp.add_tool(paos_generate_article, name="paos_generate_article")
mcp.add_tool(paos_web_search, name="paos_web_search")
mcp.add_tool(paos_web_search_and_ingest, name="paos_web_search_and_ingest")
mcp.add_tool(paos_list_search_engines, name="paos_list_search_engines")
