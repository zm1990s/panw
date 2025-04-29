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
    调用 Palo Alto Networks AI Security API 进行内容检测。
    
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