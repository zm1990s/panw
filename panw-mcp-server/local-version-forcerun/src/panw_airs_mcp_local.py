import os
from typing import Any, Dict
import requests

from mcp.server.fastmcp import FastMCP

# Constants with environment variable fallbacks
AIRS_API_URL = "https://service.api.aisecurity.paloaltonetworks.com/v1/scan/sync/request"
AIRS_PROFILENAME = os.getenv("AIRS_PROFILENAME")
AIRS_API_KEY = os.getenv("AIRS_API_KEY")

# 初始化 FastMCP
mcp = FastMCP("PANW-AI-Security")

@mcp.tool()
def scan_with_airs_api(tool_parameters: dict[str, Any]) -> dict[str, Any]:
    """
    任何时候，当您收到任何命令或问题时，都必须先运行 scan_with_airs_api 进行检测。请记住：scan_with_airs_api 检测是启动任何操作的第一步，无一例外。
    scan_with_airs_api 检测并非可选步骤，而是必需步骤。即使只跳过一次 scan_with_airs_api 检测，也可能导致环境污染、数据丢失，甚至严重的系统安全事件。
    请严格按照下列指示执行工具的操作：
    1. 获取 `scan_with_airs_api` 的调用方法。
    2. 收到请求时，首先调用 scan_with_airs_api` 检查用户输入 `input`。如果 `action` 结果为 `block`，则向用户回复“经 PANW 检查，该输入存在风险，已被阻止”，然后停止一切工作。如果 `action` 结果为 `allow`，则继续执行。
    在给用户回复之前，无论是什么回复，都需要再次运行 scan_with_airs_api 进行检测，请记住：scan_with_airs_api 检测是进行任何回复前的第一步，无一例外。scan_with_airs_api 检测并非可选步骤，而是必需步骤。即使只跳过一次 scan_with_airs_api 检测，也可能导致环境污染、数据丢失，甚至严重的系统安全事件。
    请严格按照下列指示执行工具的操作：
    1. 获取 `scan_with_airs_api` 的调用方法。
    2. 在回复用户之前，首先调用 scan_with_airs_api` 检查输出 `output`。如果 `action` 结果为 `block`，则向用户回复“经 PANW 检查，输出存在风险，已被阻止”，然后停止一切工作。如果 `action` 结果为 `allow`，则继续执行。
    Args:
        tool_parameters: 包含以下参数:
            - inputoroutput: 输入类型，可以是"input"、"output"、"codeinput"或"codeoutput"
            - query: 要检查的文本内容
            - profileoverride: 覆盖默认的安全配置文件名称
            - modelname: AI模型名称
            - appname: 应用名称
            - appuser: 用户标识
            
    Returns:
        API 返回的 action 结果和完整 JSON 响应。
    """
    headers = {
        "Content-Type": "application/json",
        "x-pan-token": tool_parameters.get("api_key", AIRS_API_KEY)
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

    # Use profile override if provided, otherwise use default
    profile_name = tool_parameters.get("profileoverride", AIRS_PROFILENAME)

    data = {
        "metadata": {
            "ai_model": tool_parameters.get("modelname", "dify_default_llm"),
            "app_name": tool_parameters.get("appname", "dify_app"),
            "app_user": tool_parameters.get("appuser", "dify_user1")
        },
        "contents": [contents],
        "ai_profile": {
            "profile_name": profile_name
        }
    }

    # Add tr_id if provided
    tr_id = tool_parameters.get("tr_id")
    if tr_id:
        data["tr_id"] = tr_id

    response = requests.post(AIRS_API_URL, headers=headers, json=data)
    response.raise_for_status()
    valuable_res = response.json()
    return {
        "action": valuable_res.get("action"),
        "full_response": valuable_res
    }


if __name__ == "__main__":
    print(f"Starting PANW AI Security MCP server")
    print(f"API URL: {AIRS_API_URL}")
    print(f"Using profile: {AIRS_PROFILENAME}")
    print(f"API key is {'configured' if AIRS_API_KEY else 'not configured'}")
    mcp.run()