#!/usr/bin/env python3
"""
MCP Server - Streamable HTTP 传输

职责：
1. OAuth 令牌验证（JWKS）：验证 Authorization Bearer token 合法性
2. 验证请求来源（X-User-Claims / Portkey）
3. 将用户身份转发给 Business API
"""

import base64
import contextlib
import contextvars
import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

import httpx
import jwt
from fastapi import FastAPI, HTTPException, Response

from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool, ToolAnnotations, Resource

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("mcp-server")

# ── 配置 ──────────────────────────────────────────────────────────────────────
API_BASE_URL  = os.environ.get("API_BASE_URL", "http://localhost:8080")
MCP_BASE_URL  = os.environ.get("MCP_BASE_URL", "http://localhost:8000")  # 对外暴露的 MCP Server 公网/内网地址
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")
# 设为 "false" / "0" / "no" 可跳过 X-User-Claims 来源校验（直连调试用）
REQUIRE_PORTKEY_CLAIMS = os.environ.get("REQUIRE_PORTKEY_CLAIMS", "true").lower() not in ("false", "0", "no")

# ── OAuth 令牌验证配置 ─────────────────────────────────────────────────────────
# OIDC Discovery URL，用于获取 JWKS（验证 Authorization 中的 Bearer token）
MCP_OAUTH_DISCOVERY_URL = os.environ.get("MCP_OAUTH_DISCOVERY_URL", "")
MCP_OAUTH_AUDIENCE      = os.environ.get("MCP_OAUTH_AUDIENCE", "")
# 设为 "false" / "0" / "no" 可跳过 OAuth 验证（本地调试用）
REQUIRE_OAUTH = os.environ.get("REQUIRE_OAUTH", "true").lower() not in ("false", "0", "no")

_oauth_oidc_cache: Optional[dict] = None
_oauth_oidc_ts: float = 0.0
_oauth_jwks_cache: Optional[dict] = None
_oauth_jwks_ts: float = 0.0
_OAUTH_TTL = 3600.0


async def _get_oauth_oidc() -> dict:
    global _oauth_oidc_cache, _oauth_oidc_ts
    if _oauth_oidc_cache and (time.time() - _oauth_oidc_ts) < _OAUTH_TTL:
        return _oauth_oidc_cache
    async with httpx.AsyncClient() as c:
        r = await c.get(MCP_OAUTH_DISCOVERY_URL, timeout=10)
        r.raise_for_status()
        _oauth_oidc_cache = r.json()
        _oauth_oidc_ts = time.time()
        return _oauth_oidc_cache


async def _get_oauth_jwks() -> dict:
    global _oauth_jwks_cache, _oauth_jwks_ts
    if _oauth_jwks_cache and (time.time() - _oauth_jwks_ts) < _OAUTH_TTL:
        return _oauth_jwks_cache
    oidc = await _get_oauth_oidc()
    async with httpx.AsyncClient() as c:
        r = await c.get(oidc["jwks_uri"], timeout=10)
        r.raise_for_status()
        _oauth_jwks_cache = r.json()
        _oauth_jwks_ts = time.time()
        return _oauth_jwks_cache


async def verify_oauth_token(token: str) -> dict:
    """验证 Bearer token 签名与 issuer；失败抛 ValueError。"""
    oidc = await _get_oauth_oidc()
    jwks = await _get_oauth_jwks()
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except Exception as e:
        raise ValueError(f"无法解析 token header: {e}")

    rsa_key = None
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            rsa_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
            break
    if not rsa_key:
        available = [k.get("kid") for k in jwks.get("keys", [])]
        raise ValueError(f"kid={kid} 不在 JWKS 中，可用 kids: {available}")

    decode_opts: dict = {"verify_aud": bool(MCP_OAUTH_AUDIENCE)}
    payload = jwt.decode(
        token,
        rsa_key,
        algorithms=["RS256"],
        issuer=oidc["issuer"],
        audience=MCP_OAUTH_AUDIENCE or None,
        options=decode_opts,
    )
    logger.info(f"   ✅ OAuth 验证通过: sub={payload.get('sub')} iss={payload.get('iss')}")
    return payload

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
            name="update_username",
            description="[sensitive] 修改用户显示名称（需要写权限，readonly/guest 角色会被拒绝）",
            annotations=ToolAnnotations(destructiveHint=True),
            inputSchema={
                "type": "object",
                "properties": {
                    "new_name": {
                        "type": "string",
                        "description": "新的显示名称",
                    }
                },
                "required": ["new_name"],
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
    没有该 header 说明请求绕过了 Portkey。
    REQUIRE_PORTKEY_CLAIMS=false 时降级为警告，不拦截请求。
    """
    result = {"verified": True, "warnings": []}
    user_claims = headers.get("x-user-claims", "") or headers.get("X-User-Claims", "")
    result["portkey_user"] = headers.get("x-portkey-user-id", "")
    if not user_claims:
        result["warnings"].append("X-User-Claims missing — request did not come through Portkey Gateway")
        if REQUIRE_PORTKEY_CLAIMS:
            result["verified"] = False
    return result


@mcp_server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    headers = request_headers_var.get()
    logger.info(f"🔧 工具调用: {name}")

    # ── OAuth Bearer token 验证 ───────────────────────────────────────────────
    if MCP_OAUTH_DISCOVERY_URL:
        raw_auth = headers.get("authorization", "")
        bearer = raw_auth.removeprefix("Bearer ").strip() if raw_auth.lower().startswith("bearer ") else ""
        if not bearer:
            if REQUIRE_OAUTH:
                logger.warning("   ❌ OAuth: Authorization header 缺失或非 Bearer")
                return [TextContent(type="text", text=json.dumps(
                    {"error": "Unauthorized", "detail": "Missing Bearer token"}, ensure_ascii=False))]
            logger.warning("   ⚠️  OAuth: 跳过验证（REQUIRE_OAUTH=false）")
        else:
            try:
                await verify_oauth_token(bearer)
            except Exception as e:
                logger.warning(f"   ❌ OAuth 验证失败: {e}")
                if REQUIRE_OAUTH:
                    return [TextContent(type="text", text=json.dumps(
                        {"error": "Unauthorized", "detail": str(e)}, ensure_ascii=False))]
    else:
        logger.debug("   ⚠️  OAuth: MCP_OAUTH_DISCOVERY_URL 未配置，跳过验证")

    verification = verify_client(headers)
    if not verification["verified"]:
        logger.warning("   ❌ 客户端验证失败")
        return [TextContent(type="text", text=json.dumps({
            "error": "Client verification failed",
            "detail": verification["warnings"],
        }, ensure_ascii=False))]

    user_claims_raw = headers.get("x-user-claims", "") or headers.get("X-User-Claims", "")
    # IDIRA 路径：Agent 用 IDIRA token 调 MCP，用户的 Entra ID token 放在 X-User-Token
    # Portkey 路径：Authorization 直接就是用户 Entra ID token
    user_token = headers.get("x-user-token", "") or headers.get("X-User-Token", "")
    user_jwt = user_token or headers.get("authorization", "") or headers.get("Authorization", "")
    portkey_user = headers.get("x-portkey-user-id", "")

    logger.info(f"   X-User-Claims:  {user_claims_raw if user_claims_raw else '❌ missing'}")
    logger.info(f"   X-User-Token:   {'✅ present (IDIRA path)' if user_token else '❌ missing (Portkey path)'}")
    logger.info(f"   user_jwt used:  {'✅ Bearer ' + user_jwt[7:27] + '...' if user_jwt else '❌ missing'}")

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
            claims_source = (
                "Portkey X-User-Claims" if user_claims_raw
                else "IDIRA X-User-Token" if user_token
                else "none"
            )
            result["_mcp_meta"] = {
                "server": "mcp-server",
                "transport": "streamable-http",
                "timestamp": datetime.utcnow().isoformat(),
                "claims_source": claims_source,
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

    logger.debug(f"📋 [HEADERS DEBUG] 收到全部请求头 ({len(headers)} 项):")
    for k, v in sorted(headers.items()):
        logger.debug(f"   {k}: {v}")

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
        "oauth_discovery": bool(MCP_OAUTH_DISCOVERY_URL),
    }


@_fastapi_app.get("/logs")
async def logs():
    return {"total_requests": len(request_log), "logs": request_log[-20:]}


# ── MCP OAuth 2.1 Well-Known Discovery（RFC 8414）─────────────────────────────
# IDIRA 注册自定义 MCP Server 时会 GET /.well-known/oauth-authorization-server
# 来自动发现认证方式（OAuth 2.1 / None）。必须暴露此端点，否则注册会被阻断。

@_fastapi_app.get("/.well-known/oauth-authorization-server")
async def well_known_oauth_authorization_server():
    if not MCP_OAUTH_DISCOVERY_URL:
        # 未配置 OAuth：告知 IDIRA 此 MCP Server 不要求认证
        return {"auth_method": "none"}
    try:
        oidc = await _get_oauth_oidc()
    except Exception as e:
        logger.error(f"well-known: 无法获取上游 OIDC 配置: {e}")
        raise HTTPException(status_code=503, detail=f"OAuth discovery upstream error: {e}")

    # RFC 8414 格式，从上游 OIDC Discovery 代理关键字段
    metadata: dict = {
        "issuer":                                oidc["issuer"],
        "authorization_endpoint":                oidc["authorization_endpoint"],
        "token_endpoint":                        oidc["token_endpoint"],
        "jwks_uri":                              oidc["jwks_uri"],
        "response_types_supported":              ["code"],
        "grant_types_supported":                 ["authorization_code"],
        "code_challenge_methods_supported":      ["S256"],
    }
    # 可选字段，按上游是否提供透传
    for opt in ("scopes_supported", "token_endpoint_auth_methods_supported",
                "introspection_endpoint", "revocation_endpoint"):
        if opt in oidc:
            metadata[opt] = oidc[opt]

    logger.info("📋 well-known/oauth-authorization-server 已返回")
    return metadata


# RFC 8414 同时要求支持路径变体；部分客户端用 /openid-configuration
@_fastapi_app.get("/.well-known/openid-configuration")
async def well_known_openid_configuration():
    return await well_known_oauth_authorization_server()


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
    logger.info(f"   X-User-Claims 校验: {'开启' if REQUIRE_PORTKEY_CLAIMS else '⚠️  已关闭 (REQUIRE_PORTKEY_CLAIMS=false)'}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
