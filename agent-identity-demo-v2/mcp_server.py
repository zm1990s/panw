#!/usr/bin/env python3
"""
MCP Server - Streamable HTTP 传输

职责：
1. 验证请求来源
   - 检查 X-User-Claims 是否存在（Portkey 注入，证明请求经过了 Gateway 认证）
2. 读取 Portkey 转发的 X-User-Claims（用户身份）
3. 将用户身份转发给 Business API
"""

import contextlib
import contextvars
import json
import logging
import os
from datetime import datetime

import httpx
from fastapi import FastAPI

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool, Resource

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mcp-server")

# ── 配置 ──────────────────────────────────────────────────────────────────────
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8080")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

# ── Headers ContextVar（每个 server.run 协程独立，无竞态）──────────────────────
request_headers_var: contextvars.ContextVar[dict] = contextvars.ContextVar(
    "request_headers", default={}
)

request_log: list[dict] = []

# ── MCP Server ────────────────────────────────────────────────────────────────
mcp_server = Server("mcp-server")


@mcp_server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_user_identity",
            description="获取用户身份",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="echo_with_auth",
            description="回显",
            inputSchema={
                "type": "object",
                "properties": {"message": {"type": "string"}},
                "required": ["message"],
            },
        ),
        Tool(
            name="list_accessible_resources",
            description="资源列表",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="get_user_profile",
            description="用户 Profile",
            inputSchema={"type": "object", "properties": {}},
        ),
    ]


def verify_client(headers: dict) -> dict:
    """
    验证请求来自 Portkey Gateway：
    Portkey 在转发前会解析 JWT 并注入 X-User-Claims，
    没有该 header 说明请求绕过了 Portkey，直接拒绝。
    """
    result = {"verified": True, "warnings": []}
    user_claims = headers.get("x-user-claims", "") or headers.get("X-User-Claims", "")
    result["portkey_user"] = headers.get("x-portkey-user-id", "")
    if not user_claims:
        result["warnings"].append("X-User-Claims missing — request did not come through Portkey Gateway")
        result["verified"] = False
    return result


@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    headers = request_headers_var.get()
    verification = verify_client(headers)

    logger.info(f"🔧 工具调用: {name}")
    if not verification["verified"]:
        logger.warning("   ❌ 客户端验证失败")
        return [TextContent(type="text", text=json.dumps({
            "error": "Client verification failed",
            "detail": verification["warnings"],
        }, ensure_ascii=False))]

    user_claims_raw = headers.get("x-user-claims", "") or headers.get("X-User-Claims", "")
    user_jwt = headers.get("authorization", "") or headers.get("Authorization", "")
    portkey_user = headers.get("x-portkey-user-id", "")

    logger.info(f"   X-User-Claims: {user_claims_raw if user_claims_raw else '❌ missing'}")
    logger.info(f"   Authorization: {'✅ Bearer ' + user_jwt[7:27] + '...' if user_jwt else '❌ missing — Portkey 未透传'}")

    claims = {}
    if user_claims_raw:
        try:
            claims = json.loads(user_claims_raw)
        except Exception:
            pass

    api_headers = {
        "Content-Type": "application/json",
        "X-Internal-Auth": INTERNAL_API_KEY,
        "Authorization": user_jwt or "",
        "X-Forwarded-Claims": json.dumps(claims) if claims else "",
        "X-Forwarded-User": portkey_user,
    }
    api_payload = {
        "arguments": arguments,
        "forwarded_claims": claims,
        "client_verification": verification,
    }

    try:
        async with httpx.AsyncClient() as client:
            api_url = f"{API_BASE_URL}/api/tools/{name}"
            logger.info(f"   转发到 API: {api_url}")
            resp = await client.post(api_url, json=api_payload, headers=api_headers, timeout=30)
            if resp.status_code == 401:
                return [TextContent(type="text", text=json.dumps({"error": "Unauthorized", "detail": "API rejected JWT"}, ensure_ascii=False))]
            if resp.status_code == 403:
                return [TextContent(type="text", text=json.dumps({"error": "Forbidden", "detail": "Insufficient permissions"}, ensure_ascii=False))]
            resp.raise_for_status()
            result = resp.json()
            result["_mcp_meta"] = {
                "server": "mcp-server",
                "transport": "streamable-http",
                "timestamp": datetime.utcnow().isoformat(),
                "claims_source": "Portkey X-User-Claims" if user_claims_raw else "none",
            }
            return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]
    except Exception as e:
        logger.error(f"   转发失败: {e}")
        return [TextContent(type="text", text=json.dumps({"error": "Failed to forward to API", "detail": str(e)}, ensure_ascii=False))]


@mcp_server.list_resources()
async def handle_list_resources() -> list[Resource]:
    return [Resource(uri="identity://current", name="Current User Identity", description="当前认证用户", mimeType="application/json")]


@mcp_server.read_resource()
async def handle_read_resource(uri: str) -> str:
    headers = request_headers_var.get()
    user_claims_raw = headers.get("x-user-claims", "") or headers.get("X-User-Claims", "")
    user_jwt = headers.get("authorization", "") or headers.get("Authorization", "")

    if uri == "identity://current":
        if not user_claims_raw:
            return json.dumps({"status": "anonymous"}, ensure_ascii=False)
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{API_BASE_URL}/api/user/me",
                    headers={"X-Internal-Auth": INTERNAL_API_KEY, "Authorization": user_jwt},
                    timeout=10,
                )
                if resp.status_code == 200:
                    return json.dumps({"status": "authenticated", "user": resp.json()}, ensure_ascii=False)
        except Exception:
            pass
        try:
            claims = json.loads(user_claims_raw)
            return json.dumps({"status": "authenticated", "user": claims}, ensure_ascii=False)
        except Exception:
            return json.dumps({"status": "error"}, ensure_ascii=False)
    raise ValueError(f"Unknown resource: {uri}")


# ── Session Manager ───────────────────────────────────────────────────────────
session_manager = StreamableHTTPSessionManager(
    app=mcp_server,
    json_response=False,
    stateless=False,
)


async def _mcp_asgi(scope, receive, send):
    from starlette.requests import Request as StarletteRequest
    request = StarletteRequest(scope, receive)
    headers = dict(request.headers)

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "method": request.method,
        "client_ip": request.client.host if request.client else "unknown",
        "headers": {k: v for k, v in headers.items() if k.lower() in [
            "x-user-claims", "authorization",
            "x-portkey-api-key", "x-portkey-user-id",
            "user-agent", "mcp-session-id",
        ]},
    }
    request_log.append(log_entry)
    logger.info(f"📥 MCP {request.method} 来自 {log_entry['client_ip']}")

    token = request_headers_var.set(headers)
    try:
        await session_manager.handle_request(scope, receive, send)
    finally:
        request_headers_var.reset(token)


# ── FastAPI app ───────────────────────────────────────────────────────────────
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with session_manager.run():
        logger.info("✅ StreamableHTTP session manager 已启动")
        yield
    logger.info("🛑 StreamableHTTP session manager 已停止")


_fastapi_app = FastAPI(title="MCP Server (Streamable HTTP)", lifespan=lifespan)


@_fastapi_app.get("/health")
async def health():
    return {
        "status": "ok",
        "server": "mcp-server",
        "transport": "streamable-http",
        "api_base_url": API_BASE_URL,
    }


@_fastapi_app.get("/logs")
async def logs():
    return {"total_requests": len(request_log), "logs": request_log[-20:]}


class _MCPRouter:
    """在 FastAPI 路由层之前拦截 /mcp，避免 Starlette mount 触发 307 重定向。"""

    def __init__(self, fastapi_app, mcp_handler):
        self._app = fastapi_app
        self._mcp = mcp_handler

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and scope.get("path", "").rstrip("/") == "/mcp":
            await self._mcp(scope, receive, send)
        else:
            await self._app(scope, receive, send)


app = _MCPRouter(_fastapi_app, _mcp_asgi)


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 启动 MCP Server (Streamable HTTP) on http://localhost:8000")
    logger.info(f"   上游 API: {API_BASE_URL}")
    logger.info("   MCP 端点: http://localhost:8000/mcp")
    uvicorn.run(app, host="0.0.0.0", port=8000)
