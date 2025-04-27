from collections.abc import Generator
from typing import Any

import requests
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route
from mcp.server.sse import SseServerTransport
from mcp.server import Server
import uvicorn

AIRS_API_URL = "https://service.api.aisecurity.paloaltonetworks.com/v1/scan/sync/request"
# 这些会话变量在 handle_sse 中动态设置
AIRS_API_KEY: str
AIRS_PROFILENAME: str
PORT=8080
# 初始化 FastMCP
mcp = FastMCP("PANW-AI-Security")

@mcp.tool()
def scan_with_airs_api(tool_parameters: dict[str, Any]) -> dict[str, Any]:
    """
    调用 Palo Alto Networks AI Security API 进行内容检测。
    
    Args:
        tool_parameters: 包含以下参数:
            - inputoroutput: 输入类型，可以是"input"、"output"、"codeinput"或"codeoutput"
            - query: 要检查的文本内容
            - modelname: AI模型名称
            - appname: 应用名称
            - appuser: 用户标识
            
    Returns:
        API 返回的 action 结果和完整 JSON 响应。
    """
    headers = {
        "Content-Type": "application/json",
        "x-pan-token": AIRS_API_KEY
    }

    contents = {}
    if tool_parameters.get("inputoroutput") == "input":
        contents["prompt"] = tool_parameters["query"]
    elif tool_parameters.get("inputoroutput") == "output":
        contents["response"] = tool_parameters["query"]
    elif tool_parameters.get("inputoroutput") == "codeinput":
        contents["code_prompt"] = tool_parameters["query"]
    elif tool_parameters.get("inputoroutput") == "codeoutput":
        contents["code_response"] = tool_parameters["query"]


    data = {
        "metadata": {
            "ai_model": tool_parameters.get("modelname", "dify_default_llm"),
            "app_name": tool_parameters.get("appname", "dify_app"),
            "app_user": tool_parameters.get("appuser", "dify_user1")
        },
        "contents": [contents],
        "ai_profile": {
            "profile_name": AIRS_PROFILENAME
        }
    }
    response = requests.post(AIRS_API_URL, headers=headers, json=data)
    response.raise_for_status()
    valuable_res = response.json()
    return {
        "action": valuable_res.get("action"),
        "full_response": valuable_res
    }

def create_starlette_app(mcp_server: Server, *, debug: bool = False) -> Starlette:
    """Create a Starlette application that serves the provided MCP server with SSE."""
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        # 从 URL 查询参数获取 key 和 profilename
        global AIRS_API_KEY, AIRS_PROFILENAME
        AIRS_API_KEY = request.query_params.get("key", "")
        AIRS_PROFILENAME = request.query_params.get("profilename", "")

        async with sse.connect_sse(
                request.scope,
                request.receive,
                request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )

if __name__ == "__main__":
    mcp_server = mcp._mcp_server  # 获取底层 MCP server

    import argparse

    parser = argparse.ArgumentParser(description="Run PANW AI Security MCP SSE server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=PORT, help="Port to listen on")
    args = parser.parse_args()

    starlette_app = create_starlette_app(mcp_server, debug=True)
    uvicorn.run(starlette_app, host=args.host, port=args.port)