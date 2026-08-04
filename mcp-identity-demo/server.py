#!/usr/bin/env python3
"""
MCP Server Demo - 使用 Streamable HTTP Transport
接收 Portkey 转发的身份头，支持 SSE/JSON 自动协商

场景 1-3: 信任 Portkey 注入的 X-User-Claims
场景 4:   自主验证 Authorization header 中的 JWT，不依赖 Portkey 注入
"""

import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import jwt
import requests
from fastapi import FastAPI, Request
from mcp.server import Server
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
from mcp.types import TextContent, Tool
from starlette.responses import Response

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("identity-mcp-server")

# 全局存储当前请求的 headers 与传输信息（用于在 tool handler 中访问）
_current_request_headers: dict = {}
_current_request_info: dict = {}

# ============ JWT 验证配置（场景 4）============

AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "")
AUTH0_AUDIENCE = os.environ.get("AUTH0_AUDIENCE", "")

_jwks_cache: dict = {}


def _get_jwks() -> dict:
    """从 Auth0 获取 JWKS，带简单内存缓存。"""
    if _jwks_cache:
        return _jwks_cache
    if not AUTH0_DOMAIN:
        return {}
    url = f"https://{AUTH0_DOMAIN}/.well-known/jwks.json"
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        _jwks_cache.update(resp.json())
        logger.info(f"✅ JWKS 加载成功: {url}")
        return _jwks_cache
    except Exception as e:
        logger.warning(f"⚠️ JWKS 加载失败: {e}")
        return {}


def verify_jwt(token: str) -> dict | None:
    """
    验证 JWT 签名、过期时间、issuer、audience。
    成功返回 claims dict，失败返回 None。
    """
    if not AUTH0_DOMAIN or not AUTH0_AUDIENCE:
        logger.warning("⚠️ 未配置 AUTH0_DOMAIN / AUTH0_AUDIENCE，跳过 JWT 验证")
        return None

    jwks = _get_jwks()
    if not jwks:
        return None

    try:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")

        # 打印未验签的 payload，用于 debug audience/issuer 不匹配
        import base64 as _b64
        raw_parts = token.split(".")
        if len(raw_parts) == 3:
            padded = raw_parts[1] + "=" * (-len(raw_parts[1]) % 4)
            unverified = json.loads(_b64.urlsafe_b64decode(padded))
            logger.info(f"🔬 JWT payload (unverified): aud={unverified.get('aud')}  iss={unverified.get('iss')}  sub={unverified.get('sub')}")

        logger.info(f"🔬 Server 配置: AUTH0_AUDIENCE={AUTH0_AUDIENCE!r}  AUTH0_DOMAIN={AUTH0_DOMAIN!r}")

        key = None
        for jwk in jwks.get("keys", []):
            if jwk.get("kid") == kid:
                key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
                break
        if key is None:
            logger.warning(f"⚠️ 未找到匹配 kid={kid} 的公钥，JWKS 共 {len(jwks.get('keys', []))} 个 key")
            return None

        claims = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=AUTH0_AUDIENCE,
            issuer=f"https://{AUTH0_DOMAIN}/",
        )
        logger.info(f"✅ JWT 验证通过: sub={claims.get('sub')}")
        return claims
    except jwt.ExpiredSignatureError:
        logger.warning("⚠️ JWT 已过期")
    except jwt.InvalidAudienceError:
        logger.warning(f"⚠️ JWT audience 不匹配: token aud={unverified.get('aud') if 'unverified' in dir() else '?'}  server expects={AUTH0_AUDIENCE!r}")
    except jwt.InvalidIssuerError:
        logger.warning(f"⚠️ JWT issuer 不匹配: token iss={unverified.get('iss') if 'unverified' in dir() else '?'}  server expects=https://{AUTH0_DOMAIN}/")
    except Exception as e:
        logger.warning(f"⚠️ JWT 验证失败: {type(e).__name__}: {e}")
    return None


# ============ MCP Server (低级别 API) ============
server = Server("identity-demo-server")


@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(
            name="get_user_identity",
            description="获取用户身份信息（场景1-3 读 X-User-Claims，场景4 自主验证 JWT）",
            inputSchema={"type": "object", "properties": {}}
        ),
        Tool(
            name="echo_with_auth",
            description="带身份验证的回显工具",
            inputSchema={
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "要回显的消息"}
                },
                "required": ["message"]
            }
        ),
        Tool(
            name="list_accessible_resources",
            description="根据用户身份返回可访问资源",
            inputSchema={"type": "object", "properties": {}}
        ),
    ]


def _extract_claims(headers: dict) -> tuple[dict | None, str]:
    """
    按优先级提取身份 claims：
    1. X-User-Claims（Portkey 注入，场景 2/3）
    2. Authorization JWT（场景 4，Server 自主验签，兼容有无 Bearer 前缀）
    """
    # 场景 2/3：Portkey 注入的 X-User-Claims
    user_claims_raw = headers.get("x-user-claims", "")
    if user_claims_raw:
        try:
            return json.loads(user_claims_raw), "portkey_claims_header"
        except json.JSONDecodeError:
            return None, "portkey_claims_header(invalid_json)"

    # 场景 4：Authorization header，Server 自主验签
    auth_header = headers.get("authorization", "")
    if not auth_header:
        logger.info(f"🔬 无身份 header，keys: {list(headers.keys())}")
        return None, "none"

    logger.info(f"🔬 Authorization header 值: {auth_header[:60]!r}")
    token = auth_header.split(" ", 1)[1] if auth_header.lower().startswith("bearer ") else auth_header
    logger.info(f"🔬 提取 token 前40字符: {token[:40]}...")
    claims = verify_jwt(token)
    if claims:
        return claims, "server_jwt_verification"
    logger.warning("⚠️ JWT 验签失败，详见上方日志")
    return None, "server_jwt_verification(failed)"


@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[TextContent]:
    headers = _current_request_headers
    claims, identity_source = _extract_claims(headers)

    logger.info(f"🔧 调用工具: {name}, identity_source={identity_source}, claims_present={bool(claims)}")

    if name == "get_user_identity":
        req_info = _current_request_info or {}
        result = {
            "timestamp": datetime.utcnow().isoformat(),
            "server_name": "identity-demo-server",
            "transport": req_info.get("transport", "unknown"),
            "sdk_version": "mcp v1.x (low-level Server API)",
            "identity_source": identity_source,
            "identity_verified": bool(claims),
            "parsed_claims": claims,
        }
        if claims:
            logger.info(f"✅ 身份确认: sub={claims.get('sub')}, email={claims.get('email')}")
        else:
            logger.warning(f"⚠️ 未能提取身份，source={identity_source}")
        return [TextContent(type="text", text=json.dumps(result, ensure_ascii=False))]

    elif name == "echo_with_auth":
        if not claims:
            return [TextContent(type="text", text=json.dumps({
                "error": "Unauthorized",
                "detail": f"未能验证身份（source={identity_source}）"
            }, ensure_ascii=False))]
        return [TextContent(type="text", text=json.dumps({
            "echo": arguments.get("message", ""),
            "authenticated_as": claims.get("email") or claims.get("sub"),
            "workspace_id": claims.get("workspace_id"),
            "identity_source": identity_source,
            "timestamp": datetime.utcnow().isoformat()
        }, ensure_ascii=False))]

    elif name == "list_accessible_resources":
        if not claims:
            return [TextContent(type="text", text=json.dumps({
                "error": "未认证",
                "identity_source": identity_source
            }, ensure_ascii=False))]

        org_id = claims.get("organisation_id", "default")
        resources_db = {
            "org_demo": [
                {"id": "doc_1", "name": "Demo Project Plan", "access": "read"},
                {"id": "doc_2", "name": "Team OKRs Q3", "access": "read"},
            ],
            "org_admin": [
                {"id": "doc_1", "name": "Demo Project Plan", "access": "read_write"},
                {"id": "doc_3", "name": "Financial Report", "access": "admin"},
            ],
            "default": [
                {"id": "doc_public", "name": "Public Guide", "access": "read"}
            ]
        }
        return [TextContent(type="text", text=json.dumps({
            "user": claims.get("email") or claims.get("sub"),
            "organisation_id": org_id,
            "identity_source": identity_source,
            "resources": resources_db.get(org_id, resources_db["default"])
        }, ensure_ascii=False))]

    return [TextContent(type="text", text=json.dumps({"error": "Unknown tool"}, ensure_ascii=False))]


# ============ StreamableHTTP Session Manager ============
streamable_manager = StreamableHTTPSessionManager(
    app=server,
    session_idle_timeout=1800,
)


@asynccontextmanager
async def lifespan(app: Any):
    # 预加载 JWKS（场景 4）
    if AUTH0_DOMAIN:
        _get_jwks()
    async with streamable_manager.run():
        yield


# ============ FastAPI App ============
app = FastAPI(title="Identity MCP Server", lifespan=lifespan)


class AlreadyHandledResponse(Response):
    """占位 Response：handle_request 已直接发送 ASGI 响应，FastAPI 无需再发送。"""
    async def __call__(self, scope, receive, send):
        pass


request_log: list[dict] = []


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "server": "identity-demo-server",
        "sdk_version": "v1.x",
        "jwt_verification": "enabled" if AUTH0_DOMAIN else "disabled (AUTH0_DOMAIN not set)",
    }


@app.api_route("/mcp", methods=["GET", "POST", "DELETE"])
async def mcp_endpoint(request: Request):
    # GET 请求不带 Accept: text/event-stream 时视为健康探测，直接返回 200
    if request.method == "GET" and "text/event-stream" not in request.headers.get("accept", ""):
        return Response(content='{"status":"ok","endpoint":"mcp"}', media_type="application/json")

    global _current_request_headers, _current_request_info
    headers = dict(request.headers)
    _current_request_headers = headers
    _current_request_info = {
        "method": request.method,
        "path": request.url.path,
        "transport": "streamable_http",
    }

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "client_ip": request.client.host if request.client else "unknown",
        "method": request.method,
        "headers": {k: v for k, v in headers.items() if k.lower() in [
            "x-user-claims", "authorization", "x-portkey-api-key", "user-agent", "mcp-session-id"
        ]}
    }
    request_log.append(log_entry)
    logger.info(f"📥 MCP {request.method} 来自 {log_entry['client_ip']}")
    logger.info(f"   Headers: {json.dumps(log_entry['headers'], indent=2)}")

    await streamable_manager.handle_request(request.scope, request.receive, request._send)
    return AlreadyHandledResponse()


@app.get("/logs")
async def get_logs():
    return {"total_requests": len(request_log), "logs": request_log[-20:]}


if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 启动 Identity MCP Server (Streamable HTTP) on http://localhost:8000")
    logger.info("   MCP 端点: http://localhost:8000/mcp")
    logger.info("   健康检查: http://localhost:8000/health")
    logger.info("   请求日志: http://localhost:8000/logs")
    uvicorn.run(app, host="0.0.0.0", port=8000)
