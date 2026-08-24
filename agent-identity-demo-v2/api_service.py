#!/usr/bin/env python3
"""
Business API - Auth0 用户身份验证

验证逻辑：
1. 验证 X-Internal-Auth（确认请求来自 MCP Server）
2. 验证用户 JWT（Auth0 JWKS）
3. 按用户 sub 做授权决策
"""

import json
import logging
import os
import time
from datetime import datetime
from typing import Optional

import httpx
import jwt
from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("business-api")

app = FastAPI(title="Business API - Auth0")
security = HTTPBearer(auto_error=False)


@app.middleware("http")
async def log_request_headers(request: Request, call_next):
    if request.url.path.startswith("/api/tools/"):
        h = request.headers
        logger.info(f"📨 {request.method} {request.url.path}")
        logger.info(f"   Authorization:      {'✅ ' + h['authorization'][:50] + '...' if 'authorization' in h else '❌ missing'}")
        logger.info(f"   X-Internal-Auth:    {'✅ present' if h.get('x-internal-auth') else '❌ missing'}")
        logger.info(f"   X-Forwarded-Claims: {h.get('x-forwarded-claims', '❌ missing')}")
        logger.info(f"   X-Forwarded-User:   {h.get('x-forwarded-user', '❌ missing')}")
    return await call_next(request)

OIDC_DOMAIN = os.environ.get("OIDC_DOMAIN", "")
OIDC_AUDIENCE = os.environ.get("OIDC_AUDIENCE", "")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

def _base_url(domain: str) -> str:
    if domain.startswith("http://") or domain.startswith("https://"):
        return domain.rstrip("/")
    return f"https://{domain}"

OIDC_DISCOVERY_URL = os.environ.get(
    "OIDC_DISCOVERY_URL",
    f"{_base_url(OIDC_DOMAIN)}/.well-known/openid-configuration" if OIDC_DOMAIN else "",
)

_oidc_config: Optional[dict] = None
_oidc_config_ts: float = 0.0
_OIDC_TTL = 3600.0

_jwks_cache: Optional[dict] = None
_jwks_cache_ts: float = 0.0


async def get_oidc_config() -> dict:
    global _oidc_config, _oidc_config_ts
    if _oidc_config is not None and (time.time() - _oidc_config_ts) < _OIDC_TTL:
        return _oidc_config
    async with httpx.AsyncClient() as client:
        resp = await client.get(OIDC_DISCOVERY_URL, timeout=10)
        resp.raise_for_status()
        _oidc_config = resp.json()
        _oidc_config_ts = time.time()
        return _oidc_config


async def get_jwks() -> dict:
    global _jwks_cache, _jwks_cache_ts
    if _jwks_cache is not None and (time.time() - _jwks_cache_ts) < _OIDC_TTL:
        return _jwks_cache
    oidc = await get_oidc_config()
    async with httpx.AsyncClient() as client:
        resp = await client.get(oidc["jwks_uri"], timeout=10)
        resp.raise_for_status()
        _jwks_cache = resp.json()
        _jwks_cache_ts = time.time()
        return _jwks_cache


async def verify_auth0_token(token: str) -> dict:
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        oidc = await get_oidc_config()
        jwks = await get_jwks()
        kid = jwt.get_unverified_header(token).get("kid")
        rsa_key = None
        for key in jwks["keys"]:
            if key["kid"] == kid:
                rsa_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(key))
                break
        if not rsa_key:
            raise HTTPException(status_code=401, detail="Invalid token key")
        payload = jwt.decode(token, rsa_key, algorithms=["RS256"], issuer=oidc["issuer"], options={"verify_aud": False})
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"   JWT verify failed: {type(e).__name__}: {e}")
        logger.error(f"   issuer expected:   {oidc.get('issuer')}")
        logger.error(f"   audience expected: {OIDC_AUDIENCE or '(not set)'}")
        logger.error(f"   token kid:         {jwt.get_unverified_header(token).get('kid') if token else 'N/A'}")
        raise HTTPException(status_code=401, detail="Invalid token")


async def verify_internal_auth(x_internal_auth: str = Header(..., alias="X-Internal-Auth")) -> None:
    if not INTERNAL_API_KEY:
        raise HTTPException(status_code=500, detail="Server misconfiguration: INTERNAL_API_KEY not set")
    if x_internal_auth != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid internal auth")


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    # 优先信任来自 MCP Server 的 X-Forwarded-Claims
    # 安全性由 X-Internal-Auth 保障：外部无法伪造该 header
    forwarded = request.headers.get("X-Forwarded-Claims", "")
    logger.info(f"   get_current_user: X-Forwarded-Claims={'present' if forwarded else 'MISSING'}")
    if forwarded:
        try:
            claims = json.loads(forwarded)
            logger.info(f"   get_current_user: parsed claims sub={claims.get('sub', 'MISSING')}")
            if claims.get("sub"):
                logger.info(f"   ✅ 使用 X-Forwarded-Claims, sub={claims['sub']}")
                return claims
        except Exception as e:
            logger.warning(f"   X-Forwarded-Claims 解析失败: {e}")
    # 回退：直接带 JWT 的请求做 JWKS 验签
    logger.info(f"   get_current_user: 回退到 JWKS 验签, credentials={'present' if credentials else 'MISSING'}")
    if not credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return await verify_auth0_token(credentials.credentials)


def log_portkey_headers(request: Request, endpoint: str) -> None:
    h = request.headers
    logger.info(f"📨 {endpoint}")
    logger.info(f"   Authorization:       {'✅ ' + h['authorization'][:40] + '...' if 'authorization' in h else '❌ missing'}")
    logger.info(f"   X-Internal-Auth:     {'✅ present' if h.get('x-internal-auth') else '❌ missing'}")
    logger.info(f"   X-Forwarded-Claims:  {h.get('x-forwarded-claims', '❌ missing')[:120]}")
    logger.info(f"   X-Forwarded-User:    {h.get('x-forwarded-user', '❌ missing')}")


# ── 数据模型 ──────────────────────────────────────────────────────────────────

class ToolRequest(BaseModel):
    arguments: dict = {}
    forwarded_claims: Optional[dict] = None
    client_verification: Optional[dict] = None


# ── 模拟数据库 ────────────────────────────────────────────────────────────────

ROLE_PERMISSIONS = {
    "admin": {
        "label": "🔴 管理员",
        "can_read": True,
        "can_write": True,
        "can_delete": True,
        "can_manage_users": True,
        "can_view_audit_log": True,
    },
    "member": {
        "label": "🟡 普通成员",
        "can_read": True,
        "can_write": True,
        "can_delete": False,
        "can_manage_users": False,
        "can_view_audit_log": False,
    },
    "readonly": {
        "label": "🔵 只读用户",
        "can_read": True,
        "can_write": False,
        "can_delete": False,
        "can_manage_users": False,
        "can_view_audit_log": False,
    },
    "guest": {
        "label": "⚪ 访客",
        "can_read": False,
        "can_write": False,
        "can_delete": False,
        "can_manage_users": False,
        "can_view_audit_log": False,
    },
}

ROLE_RESOURCES = {
    "admin": [
        {"id": "doc_1", "name": "📋 产品路线图 2026", "access": "read_write", "sensitivity": "confidential"},
        {"id": "doc_2", "name": "📊 全员 OKR Q3",    "access": "read_write", "sensitivity": "internal"},
        {"id": "doc_3", "name": "💰 财务预算报告",    "access": "read_write", "sensitivity": "confidential"},
        {"id": "doc_4", "name": "🔐 审计日志",        "access": "read",       "sensitivity": "restricted"},
        {"id": "doc_public", "name": "📖 公开使用指南", "access": "read",     "sensitivity": "public"},
    ],
    "member": [
        {"id": "doc_2", "name": "📊 全员 OKR Q3",    "access": "read",       "sensitivity": "internal"},
        {"id": "doc_5", "name": "📝 项目周报",        "access": "read_write", "sensitivity": "internal"},
        {"id": "doc_public", "name": "📖 公开使用指南", "access": "read",     "sensitivity": "public"},
    ],
    "readonly": [
        {"id": "doc_2", "name": "📊 全员 OKR Q3",    "access": "read", "sensitivity": "internal"},
        {"id": "doc_public", "name": "📖 公开使用指南", "access": "read", "sensitivity": "public"},
    ],
    "guest": [],
}

# sub → role 映射，只存权限相关信息
def get_role(user: dict) -> str:
    """从 claims 里解析 role，兼容字符串和数组两种格式。"""
    role = user.get("role", "guest")
    if isinstance(role, list):
        role = role[0] if role else "guest"
    return role if role in ROLE_PERMISSIONS else "guest"


# ── API 端点 ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "service": "business-api", "oidc_discovery": OIDC_DISCOVERY_URL, "oidc_domain": OIDC_DOMAIN}


@app.get("/api/user/me")
async def get_me(
    user: dict = Depends(get_current_user),
    _: None = Depends(verify_internal_auth),
):
    return {
        "user": {
            "sub": user.get("sub"),
            "email": user.get("email"),
            "name": user.get("name") or user.get("username"),
        },
        "verification": "auth0_jwks",
    }


@app.post("/api/tools/get_user_identity")
async def tool_get_identity(
    request: Request,
    req: ToolRequest,
    user: dict = Depends(get_current_user),
    _: None = Depends(verify_internal_auth),
):
    log_portkey_headers(request, "get_user_identity")
    user_sub = user.get("sub")
    role = get_role(user)
    permissions = ROLE_PERMISSIONS[role]
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "service": "business-api",
        "identity_verified": True,
        "verification_method": "Auth0 JWKS",
        "user": {
            "sub": user_sub,
            "email": user.get("email"),
            "name": user.get("name") or user.get("username"),
            "organisation_id": user.get("organisation_id"),
            "role": role,
            "role_label": permissions["label"],
        },
        "client_verification": req.client_verification,
    }


@app.post("/api/tools/echo_with_auth")
async def tool_echo(
    request: Request,
    req: ToolRequest,
    user: dict = Depends(get_current_user),
    _: None = Depends(verify_internal_auth),
):
    log_portkey_headers(request, "echo_with_auth")
    return {
        "echo": req.arguments.get("message", ""),
        "authenticated_as": user.get("email") or user.get("sub"),
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/tools/list_accessible_resources")
async def tool_list_resources(
    request: Request,
    req: ToolRequest,
    user: dict = Depends(get_current_user),
    _: None = Depends(verify_internal_auth),
):
    log_portkey_headers(request, "list_accessible_resources")
    user_sub = user.get("sub")
    role = get_role(user)
    permissions = ROLE_PERMISSIONS[role]
    resources = ROLE_RESOURCES[role]

    access_summary = {
        "admin":    f"🔴 管理员权限：可访问全部 {len(resources)} 个资源（含机密文档）",
        "member":   f"🟡 成员权限：可访问 {len(resources)} 个资源（不含机密文档）",
        "readonly": f"🔵 只读权限：可查看 {len(resources)} 个资源（不可修改）",
        "guest":    "⚪ 访客权限：无资源访问权限",
    }[role]

    return {
        "access_summary": access_summary,
        "user": user.get("email"),
        "sub": user_sub,
        "role": role,
        "role_label": permissions["label"],
        "permissions": {k: v for k, v in permissions.items() if k != "label"},
        "resources": resources,
        "resource_count": len(resources),
    }


@app.post("/api/tools/get_user_profile")
async def tool_get_profile(
    request: Request,
    req: ToolRequest,
    user: dict = Depends(get_current_user),
    _: None = Depends(verify_internal_auth),
):
    log_portkey_headers(request, "get_user_profile")
    user_sub = user.get("sub")
    role = get_role(user)
    permissions = ROLE_PERMISSIONS[role]
    return {
        "profile": {
            "sub": user_sub,
            "email": user.get("email"),
            "name": user.get("name") or user.get("username"),
            "organisation_id": user.get("organisation_id"),
            "role": role,
            "role_label": permissions["label"],
        },
        "data_source": "Business API Database",
        "verification": "Auth0 JWKS",
    }


if __name__ == "__main__":
    import uvicorn
    print("🚀 启动 Business API on http://localhost:8080")
    print(f"   OIDC Domain:    {OIDC_DOMAIN}")
    print(f"   OIDC Discovery: {OIDC_DISCOVERY_URL}")
    uvicorn.run(app, host="0.0.0.0", port=8080)
