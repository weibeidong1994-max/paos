#!/usr/bin/env python3
"""
PAOS MCP Server 启动入口

使用方式：
    python -m paos.mcp_server          # stdio 模式（默认，MCP 客户端最常用）
    python -m paos.mcp_server --sse    # SSE 模式，可通过 HTTP 访问

Hermes 配置示例：
    mcp_servers:
      paos:
        command: "python"
        args: ["-m", "paos.mcp_server"]
"""

import argparse
import asyncio

from paos.mcp_server.server import mcp


def main():
    parser = argparse.ArgumentParser(description="PAOS MCP Server")
    parser.add_argument("--sse", action="store_true", help="使用 SSE 模式运行（默认 stdio）")
    parser.add_argument("--host", default="127.0.0.1", help="SSE 模式监听地址")
    parser.add_argument("--port", type=int, default=8001, help="SSE 模式监听端口")
    args = parser.parse_args()

    if args.sse:
        print(f"Starting PAOS MCP Server in SSE mode on http://{args.host}:{args.port}")
        mcp.settings.port = args.port
        mcp.settings.host = args.host
        mcp.run(transport="sse")
    else:
        print("Starting PAOS MCP Server in stdio mode...")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
