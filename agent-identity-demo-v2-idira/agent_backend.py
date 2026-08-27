#!/usr/bin/env python3
"""
Agent Web Backend - IdP 用户身份 + Portkey LLM (Kimi K2)

身份流转：
Layer 1: IdP - 用户身份
Layer 2: Portkey Gateway - LLM 调用 + MCP 审计
Layer 3: MCP Server - 工具执行（Streamable HTTP）
Layer 4: Business API - JWT 验签 + 业务逻辑
"""

import asyncio
import json
import logging
import os
import secrets
import uuid
from datetime import datetime
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-backend")

import time

import httpx
from fastapi import FastAPI, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import idira_oauth

# ── 配置 ──────────────────────────────────────────────────────────────────────
PORTKEY_API_KEY = os.environ.get("PORTKEY_API_KEY", "")
PORTKEY_MCP_URL = os.environ.get("PORTKEY_MCP_URL", "")
PORTKEY_LLM_URL = os.environ.get("PORTKEY_LLM_URL", "")
PORTKEY_LLM_MODEL = os.environ.get("PORTKEY_LLM_MODEL", "@aws/moonshotai.kimi-k2.5")

# IDIRA 路径下的 MCP 端点（CyberArk AI Gateway），优先于 PORTKEY_MCP_URL
IDIRA_MCP_URL = os.environ.get("IDIRA_MCP_URL", "")

OIDC_DOMAIN = os.environ.get("OIDC_DOMAIN", "")
OIDC_CLIENT_ID = os.environ.get("OIDC_CLIENT_ID", "")
OIDC_CLIENT_SECRET = os.environ.get("OIDC_CLIENT_SECRET", "")
OIDC_AUDIENCE = os.environ.get("OIDC_AUDIENCE", "")
OIDC_CALLBACK_URL = os.environ.get("OIDC_CALLBACK_URL", "http://localhost:3000/callback")

def _base_url(domain: str) -> str:
    if domain.startswith("http://") or domain.startswith("https://"):
        return domain.rstrip("/")
    return f"https://{domain}"

OIDC_DISCOVERY_URL = os.environ.get(
    "OIDC_DISCOVERY_URL",
    f"{_base_url(OIDC_DOMAIN)}/.well-known/openid-configuration" if OIDC_DOMAIN else "",
)

_oidc_config: Optional[dict] = None
_oidc_ts: float = 0.0
_OIDC_TTL = 3600.0


async def get_oidc_config() -> dict:
    global _oidc_config, _oidc_ts
    if _oidc_config is not None and (time.time() - _oidc_ts) < _OIDC_TTL:
        return _oidc_config
    async with httpx.AsyncClient() as client:
        resp = await client.get(OIDC_DISCOVERY_URL, timeout=10)
        resp.raise_for_status()
        _oidc_config = resp.json()
        _oidc_ts = time.time()
        return _oidc_config

user_sessions: dict = {}

# ── Human-in-the-Loop Consent ────────────────────────────────────────────────

# 从 MCP annotations(destructiveHint) 动态填充，fetch_mcp_tools 时自动更新
SENSITIVE_TOOLS: set[str] = set()

# consent_token → pending tool call context（5 分钟有效）
_pending_consents: dict[str, dict] = {}


class ConsentRequiredError(Exception):
    """高危工具拦截：需要用户重新认证后才能继续执行。"""
    def __init__(self, consent_token: str, tool_name: str, tool_args: dict):
        self.consent_token = consent_token
        self.tool_name = tool_name
        self.tool_args = tool_args


app = FastAPI(title="Agent Identity Demo - IdP + Portkey")
templates = Jinja2Templates(directory="templates")

# MCP 工具 schema（用于 LLM function calling）
# ── MCP 工具发现（动态，带进程级缓存）────────────────────────────────────────

# sub → (tools, timestamp)，按用户隔离，确保 IDIRA 按用户权限过滤后的工具列表不串用
_mcp_tools_cache: dict[str, tuple[list[dict], float]] = {}
_MCP_TOOLS_TTL = 300.0  # 5 分钟刷新一次


def _mcp_tool_to_openai(tool) -> dict:
    """把 MCP Tool 对象转成 OpenAI function calling 格式。"""
    schema = tool.inputSchema or {"type": "object", "properties": {}}
    # OpenAI 不接受 additionalProperties 以外的顶层字段，保留 type/properties/required
    parameters = {
        "type": schema.get("type", "object"),
        "properties": schema.get("properties", {}),
    }
    if "required" in schema:
        parameters["required"] = schema["required"]
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": parameters,
        },
    }


async def fetch_mcp_tools(mcp_headers: dict, user_sub: str = "") -> list[dict]:
    """从 MCP server 动态获取工具列表，按用户缓存 5 分钟。失败时返回该用户上次缓存或空列表。"""
    cached_tools, cached_ts = _mcp_tools_cache.get(user_sub, ([], 0.0))
    if cached_tools and (time.time() - cached_ts) < _MCP_TOOLS_TTL:
        return cached_tools

    if idira_oauth.enabled():
        try:
            idira_token = idira_oauth.get_access_token(user_sub)
        except idira_oauth.NeedsAuthError:
            logger.warning(f"fetch_mcp_tools: IDIRA 未授权 (user={user_sub})，跳过发现，使用缓存")
            return cached_tools
        headers = {"Authorization": f"Bearer {idira_token}"}
        mcp_url = IDIRA_MCP_URL or PORTKEY_MCP_URL
        logger.info(f"🔍 fetch_mcp_tools IDIRA token: Bearer {idira_token}")
        logger.info(f"🔍 fetch_mcp_tools MCP URL: {mcp_url}")
    else:
        headers = mcp_headers
        mcp_url = PORTKEY_MCP_URL

    try:
        async with httpx.AsyncClient(headers=headers, timeout=httpx.Timeout(15, read=30)) as http_client:
            async with streamable_http_client(mcp_url, http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()

                    # 从 destructiveHint annotation 或 description "[sensitive]" 标记推导高危工具集
                    # IDIRA 代理会剥去 annotations，因此同时检查 description 中的 [sensitive] 标记
                    # 工具名可能带 __server-suffix 后缀（IDIRA 多服务命名），存储时去掉后缀
                    for t in result.tools:
                        logger.debug(f"🔍 工具 {t.name!r}: annotations={t.annotations}, desc={str(t.description)[:60]}")
                    discovered_sensitive = {
                        t.name.split("__")[0] for t in result.tools
                        if (t.annotations and t.annotations.destructiveHint)
                        or (t.description and "[sensitive]" in t.description)
                    }
                    logger.info(f"🔒 discovered_sensitive={discovered_sensitive}, current={SENSITIVE_TOOLS}")
                    if discovered_sensitive != SENSITIVE_TOOLS:
                        SENSITIVE_TOOLS.clear()
                        SENSITIVE_TOOLS.update(discovered_sensitive)
                        logger.info(f"🔒 SENSITIVE_TOOLS 自动更新: {SENSITIVE_TOOLS}")

                    tools = [_mcp_tool_to_openai(t) for t in result.tools]
                    _mcp_tools_cache[user_sub] = (tools, time.time())
                    logger.info(f"✅ MCP 工具发现 (user={user_sub}): {len(tools)} 个工具: {[t['function']['name'] for t in tools]}")
                    return tools
    except Exception as e:
        err_str = str(e)
        # 网关返回 401：token 已过期或被拒，清除本地缓存的 token 并触发重新授权
        if "401" in err_str and idira_oauth.enabled():
            logger.warning(f"⚠️  MCP 工具发现收到 401，IDIRA token 可能已过期，清除并触发重新授权")
            idira_oauth.clear_token(user_sub)
            raise idira_oauth.NeedsAuthError(idira_oauth.build_auth_url(user_sub))
        logger.warning(f"⚠️  MCP 工具发现失败: {e}，使用{'缓存' if cached_tools else '空列表'}")
        return cached_tools

SYSTEM_PROMPT = """你是一个身份验证演示助手，运行在一个 4 层身份验证架构中：
- Layer 1: SSO（用户身份 JWT）
- Layer 2: Portkey/IDIRA Gateway（审计 + LLM 路由）
- Layer 3: MCP Server（工具执行，Streamable HTTP）
- Layer 4: Business API（JWT 验签 + 授权）

工具使用原则：
- 只调用与用户请求直接相关的工具，不要主动调用其他工具
- 每次请求调用尽量少的工具，够用即可

工具说明：
- get_user_identity：获取身份链（sub、email、角色、各层验证状态）——用于"我是谁""查身份""验证状态"
- get_user_profile：获取用户详情（姓名、组织、角色权限）——用于"查我的资料""详细信息"
- list_accessible_resources：列出有权访问的资源——用于"我能访问什么""查权限""资源列表"
- update_username：修改用户显示名称（需要 can_write 权限）——用于"改名""修改用户名"；readonly/guest 角色会被拒绝，体现权限差异

请用中文回复，结合工具结果给出清晰的解释。"""


class ChatRequest(BaseModel):
    message: str
    session_id: str


# ── MCP 工具调用 ──────────────────────────────────────────────────────────────

async def call_mcp_tool(tool_name: str, tool_args: dict, mcp_headers: dict, user_sub: str = "") -> str:
    # IDIRA 路径：用 IDIRA access token，并透传用户标识供 IDIRA 审计溯源
    if idira_oauth.enabled():
        idira_token = idira_oauth.get_access_token(user_sub)  # NeedsAuthError 由上层捕获
        mcp_url = IDIRA_MCP_URL or PORTKEY_MCP_URL
        raw_user_auth = mcp_headers.get("Authorization", "")
        mcp_headers = {
            # Agent 向 IDIRA Broker 出示的身份凭证
            "Authorization": f"Bearer {idira_token}",
            # 用户的 Entra ID token，经 MCP 提取后以 X-Forwarded-Claims 传给 Business API
            "X-User-Token": raw_user_auth,
            # 审计溯源
            "x-portkey-user-id": mcp_headers.get("x-portkey-user-id", ""),
            "x-portkey-metadata": mcp_headers.get("x-portkey-metadata", ""),
        }
        logger.info(f"🔧 call_mcp_tool (IDIRA): {tool_name} → {mcp_url}")
        logger.info(f"   IDIRA token:       Bearer {idira_token[:20]}...")
        logger.info(f"   X-User-Token:      {'✅ ' + raw_user_auth[:30] + '...' if raw_user_auth else '❌ EMPTY — user token missing from session!'}")
        logger.info(f"   x-portkey-user-id: {mcp_headers.get('x-portkey-user-id', '❌ missing')}")
    else:
        mcp_url = PORTKEY_MCP_URL
        logger.info(f"🔧 call_mcp_tool (Portkey): {tool_name} → {mcp_url}")
        logger.info(f"   x-portkey-api-key:  {'✅ ' + mcp_headers.get('x-portkey-api-key','')[:12] + '...' if mcp_headers.get('x-portkey-api-key') else '❌ missing'}")
        logger.info(f"   Authorization:      {'✅ ' + mcp_headers.get('Authorization','')[:30] + '...' if mcp_headers.get('Authorization') else '❌ missing'}")
    try:
        async with httpx.AsyncClient(
            headers=mcp_headers,
            timeout=httpx.Timeout(30, read=60),
        ) as http_client:
            async with streamable_http_client(
                mcp_url, http_client=http_client
            ) as (read, write, _):
                async with ClientSession(read, write) as mcp_session:
                    await mcp_session.initialize()
                    result = await mcp_session.call_tool(tool_name, tool_args)
    except* Exception as eg:
        for exc in eg.exceptions:
            logger.error(f"MCP TaskGroup 子异常: {type(exc).__name__}: {exc}")
            if "401" in str(exc) and idira_oauth.enabled():
                logger.warning("⚠️  工具调用收到 401，清除 IDIRA token 并触发重新授权")
                idira_oauth.clear_token(user_sub)
                raise idira_oauth.NeedsAuthError(idira_oauth.build_auth_url(user_sub)) from exc
        raise

    output_parts = []
    for content in result.content:
        if content.type == "text":
            try:
                data = json.loads(content.text)
                output_parts.append(json.dumps(data, indent=2, ensure_ascii=False))
            except Exception:
                output_parts.append(content.text)
    return "\n".join(output_parts)


# ── LLM Agentic Loop ─────────────────────────────────────────────────────────

async def _agent_loop(
    messages: list,
    tools_schema: list,
    mcp_headers: dict,
    user_email: str,
    user_sub: str,
    max_iterations: int = 5,
) -> tuple[str, list[dict]]:
    """核心 LLM 循环。遇到高危工具时抛出 ConsentRequiredError。"""
    llm_headers = {
        "Content-Type": "application/json",
        "x-portkey-api-key": PORTKEY_API_KEY,
        "x-portkey-metadata": json.dumps({"_user": user_email, "_layer": "agent-llm"}),
    }
    tools_used: list[dict] = []

    async with httpx.AsyncClient(timeout=60) as client:
        for _ in range(max_iterations):
            payload = {
                "model": PORTKEY_LLM_MODEL,
                "messages": messages,
                "tool_choice": "auto",
                "max_tokens": 1024,
            }
            if tools_schema:
                payload["tools"] = tools_schema

            resp = await client.post(PORTKEY_LLM_URL, json=payload, headers=llm_headers)
            resp.raise_for_status()
            data = resp.json()

            choice = data["choices"][0]
            message = choice["message"]
            messages.append(message)

            if not message.get("tool_calls"):
                return message.get("content", ""), tools_used

            for tc in message["tool_calls"]:
                fn_name = tc["function"]["name"]
                try:
                    fn_args = json.loads(tc["function"]["arguments"] or "{}")
                except Exception:
                    fn_args = {}

                print(f"🔧 LLM 调用工具: {fn_name}({fn_args})")
                # IDIRA 代理工具名带 __server-suffix，去掉后缀再查 SENSITIVE_TOOLS
                fn_base = fn_name.split("__")[0]
                logger.debug(f"🔍 HIL 检查: fn={fn_name!r}, fn_base={fn_base!r}, SENSITIVE_TOOLS={SENSITIVE_TOOLS}")

                # ── 高危工具拦截 ──────────────────────────────────────────
                if fn_base in SENSITIVE_TOOLS:
                    token = secrets.token_urlsafe(16)
                    _pending_consents[token] = {
                        "tool_name":    fn_name,
                        "tool_args":    fn_args,
                        "tool_call_id": tc["id"],
                        "messages":     messages,
                        "tools_schema": tools_schema,
                        "mcp_headers":  mcp_headers,
                        "user_sub":     user_sub,
                        "user_email":   user_email,
                        "created_at":   time.time(),
                    }
                    logger.info(f"🔒 高危工具 {fn_name} 已拦截，等待用户认证 (token={token[:8]}...)")
                    raise ConsentRequiredError(token, fn_name, fn_args)

                try:
                    tool_result = await call_mcp_tool(fn_name, fn_args, mcp_headers, user_sub)
                    tools_used.append({"tool": fn_name, "args": fn_args, "output": tool_result})
                except (ConsentRequiredError, idira_oauth.NeedsAuthError):
                    raise
                except Exception as e:
                    tool_result = json.dumps({"error": str(e)}, ensure_ascii=False)
                    tools_used.append({"tool": fn_name, "args": fn_args, "error": str(e)})

                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": tool_result,
                })

    last = next(
        (m.get("content", "") for m in reversed(messages) if m.get("role") == "assistant"),
        "（Agent 达到最大迭代次数）",
    )
    return last, tools_used


async def run_agent(
    user_message: str,
    mcp_headers: dict,
    user_email: str,
    user_sub: str = "",
) -> tuple[str, list[dict]]:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]
    tools_schema = await fetch_mcp_tools(mcp_headers, user_sub)
    if not tools_schema:
        logger.warning("⚠️  未获取到任何 MCP 工具，LLM 将无工具可用")
    return await _agent_loop(messages, tools_schema, mcp_headers, user_email, user_sub)


# ── IdP 登录流程 ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/login")
async def login(request: Request, consent_token: Optional[str] = None):
    session_id = request.cookies.get("session_id")
    if consent_token and session_id and session_id in user_sessions:
        user_sessions[session_id]["pending_consent_token"] = consent_token
        logger.info(f"🔐 已存储 consent_token={consent_token[:8]}... 到 session={session_id[:8]}...")
    oidc = await get_oidc_config()
    auth_url = (
        f"{oidc['authorization_endpoint']}"
        f"?response_type=code"
        f"&client_id={OIDC_CLIENT_ID}"
        f"&redirect_uri={OIDC_CALLBACK_URL}"
        f"&scope=openid profile email"
        + (f"&audience={OIDC_AUDIENCE}" if OIDC_AUDIENCE else "")
    )
    if consent_token:
        auth_url += "&prompt=login&max_age=0"
    # consent_token 场景：SSO session 有效时静默完成，无需弹出登录窗
    # 若需要强制重新认证（step-up auth），可加回 &prompt=login&max_age=0
    return RedirectResponse(url=auth_url)


async def _run_resumed_consent(session_id: str, ctx: dict) -> None:
    """Consent 续办的后台异步任务：执行被拦截工具 → 继续 agent loop → 存结果。"""
    session = user_sessions.get(session_id)
    if not session:
        return
    ctx_sub      = ctx["user_sub"]
    ctx_email    = ctx["user_email"]
    ctx_hdrs     = ctx["mcp_headers"]
    messages     = ctx["messages"]
    tools_schema = ctx["tools_schema"]
    try:
        tool_result = await call_mcp_tool(ctx["tool_name"], ctx["tool_args"], ctx_hdrs, ctx_sub)
    except Exception as e:
        tool_result = json.dumps({"error": str(e)}, ensure_ascii=False)

    messages.append({
        "role": "tool",
        "tool_call_id": ctx["tool_call_id"],
        "content": tool_result,
    })
    try:
        final_reply, tools_used = await _agent_loop(messages, tools_schema, ctx_hdrs, ctx_email, ctx_sub)
    except ConsentRequiredError as nested:
        final_reply = f"⚠️ 执行 {nested.tool_name} 还需再次认证，请重试"
        tools_used = []
    except Exception as e:
        final_reply = f"❌ 执行失败: {e}"
        tools_used = []

    session["resumed_result"] = {
        "response": final_reply,
        "tools_used": tools_used,
        "identity": {"user": ctx_email, "user_sub": ctx_sub},
    }
    session["resumed_status"] = "done"
    logger.info(f"✅ Consent 续办完成 (tool={ctx['tool_name']}, user={ctx_sub})")


async def _handle_callback(code: str, session_id: Optional[str] = None) -> RedirectResponse:
    oidc = await get_oidc_config()
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            oidc["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "client_id": OIDC_CLIENT_ID,
                "client_secret": OIDC_CLIENT_SECRET,
                "code": code,
                "redirect_uri": OIDC_CALLBACK_URL,
            },
        )
        if resp.status_code != 200:
            logger.error(f"Token exchange failed: {resp.status_code} {resp.text}")
            raise HTTPException(status_code=400, detail=f"OIDC token exchange failed: {resp.text}")
        token_data = resp.json()
        access_token = token_data.get("access_token") or token_data.get("id_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="No access_token in OIDC response")

        user_resp = await client.get(
            oidc["userinfo_endpoint"],
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_info = user_resp.json()

    user_sub = user_info.get("sub", "")

    # ── DEBUG: 打印 access_token claims ──────────────────────────────────────
    try:
        import base64
        parts = access_token.split(".")
        if len(parts) == 3:
            padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
            claims = json.loads(base64.urlsafe_b64decode(padded))
            logger.info("🪪 [TOKEN DEBUG] access_token claims:")
            for k, v in claims.items():
                logger.info(f"   {k}: {v}")
        else:
            logger.info(f"🪪 [TOKEN DEBUG] opaque token（非 JWT），前80字符: {access_token[:80]}")
    except Exception as e:
        logger.warning(f"🪪 [TOKEN DEBUG] 解析失败: {e}")
    logger.info(f"🪪 [TOKEN DEBUG] userinfo 返回: {user_info}")
    # ─────────────────────────────────────────────────────────────────────────

    # ── Consent 续办流程：更新已有 session，而非创建新 session ─────────────────
    if session_id and session_id in user_sessions:
        existing = user_sessions[session_id]
        existing["access_token"] = access_token
        existing["user_info"] = user_info
        existing["login_time"] = datetime.utcnow().isoformat()

        consent_token = existing.pop("pending_consent_token", None)
        has_consent = consent_token and consent_token in _pending_consents
        if has_consent:
            ctx = _pending_consents.pop(consent_token)
            ctx_hdrs = ctx["mcp_headers"]
            ctx_hdrs["Authorization"] = f"Bearer {access_token}"
            existing["resumed_status"] = "pending"
            asyncio.create_task(_run_resumed_consent(session_id, ctx))
            logger.info(f"🔄 Consent 续办已启动后台任务 (tool={ctx['tool_name']}, user={ctx['user_sub']})")

        # 只有真正有 consent 续办任务时才带 ?resumed=1，普通重新登录直接回 /agent
        redirect_url = "/agent?resumed=1" if has_consent else "/agent"
        response = RedirectResponse(url=redirect_url)
        response.set_cookie(key="session_id", value=session_id, httponly=True, samesite="lax")
        return response

    # ── 普通首次登录流程 ──────────────────────────────────────────────────────
    new_session_id = str(uuid.uuid4())
    user_sessions[new_session_id] = {
        "user_info": user_info,
        "access_token": access_token,
        "login_time": datetime.utcnow().isoformat(),
    }

    # SSO 登录成功后，如果 IDIRA 已启用但该用户尚未授权，顺带触发 IDIRA OAuth
    if idira_oauth.enabled() and not idira_oauth.is_authorized(user_sub):
        logger.info(f"🔐 SSO 完成，自动触发 IDIRA OAuth（user={user_sub}）")
        idira_auth_url = idira_oauth.build_auth_url(user_sub)
        response = RedirectResponse(url=idira_auth_url)
    else:
        response = RedirectResponse(url="/agent")

    response.set_cookie(key="session_id", value=new_session_id, httponly=True, samesite="lax")
    return response


@app.get("/callback")
async def callback_get(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    """OIDC SSO 回调（Entra ID / CyberArk）。"""
    if error:
        logger.error(f"Callback error: {error} — {error_description}")
        raise HTTPException(status_code=400, detail=f"Auth error: {error}: {error_description}")
    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code in callback")
    return await _handle_callback(code, session_id=request.cookies.get("session_id"))


@app.get("/callback/idira")
async def callback_idira(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    """IDIRA MCP OAuth 专用回调，不与 SSO /callback 共用。"""
    if error:
        logger.error(f"IDIRA callback error: {error} — {error_description}")
        raise HTTPException(status_code=400, detail=f"IDIRA auth error: {error}: {error_description}")
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state in IDIRA callback")
    logger.info(f"✅ IDIRA OAuth callback (state={state[:8]}...)")
    try:
        user_sub = idira_oauth.exchange_code(state, code)
        logger.info(f"   IDIRA token 已保存 → user={user_sub}")
    except Exception as e:
        logger.error(f"IDIRA token exchange failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    return RedirectResponse(url="/agent")


@app.post("/callback")
async def callback_post(
    request: Request,
    code: Optional[str] = Form(default=None),
    error: Optional[str] = Form(default=None),
    error_description: Optional[str] = Form(default=None),
):
    if error:
        logger.error(f"OIDC callback error (POST): {error} — {error_description}")
        raise HTTPException(status_code=400, detail=f"OIDC error: {error}: {error_description}")
    if not code:
        body = await request.body()
        logger.error(f"OIDC callback POST: missing code. Body: {body}")
        raise HTTPException(status_code=400, detail="Missing authorization code in callback")
    return await _handle_callback(code, session_id=request.cookies.get("session_id"))


@app.get("/api/resumed-result")
async def resumed_result(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not logged in")
    session = user_sessions[session_id]
    status = session.get("resumed_status")
    if status == "pending":
        return {"status": "pending"}
    if status == "done":
        result = session.pop("resumed_result", {})
        session.pop("resumed_status", None)
        return {"status": "done", **result}
    raise HTTPException(status_code=404, detail="No resumed result")


@app.get("/idira/status")
async def idira_status():
    """查询 IDIRA 授权状态（供前端轮询）。"""
    if not idira_oauth.enabled():
        return {"enabled": False}
    # 状态查询不绑定具体用户，仅返回配置信息
    return {
        "enabled": True,
        "mcp_url": IDIRA_MCP_URL or PORTKEY_MCP_URL,
        "callback_url": idira_oauth.IDIRA_CALLBACK_URL,
        "note": "token 按用户隔离，请用 /api/chat 触发具体用户的授权检查",
    }


@app.get("/agent", response_class=HTMLResponse)
async def agent_page(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in user_sessions:
        return RedirectResponse(url="/login")
    session = user_sessions[session_id]
    return templates.TemplateResponse(request, "agent.html", {
        "user": session["user_info"],
        "session_id": session_id,
    })


@app.get("/api/identity")
async def get_full_identity(request: Request):
    session_id = request.cookies.get("session_id")
    if not session_id or session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not logged in")
    session = user_sessions[session_id]
    return {
        "layer_1_user": {
            "sub": session["user_info"].get("sub"),
            "email": session["user_info"].get("email"),
            "name": session["user_info"].get("name"),
        },
    }


@app.post("/api/chat")
async def chat(req: ChatRequest):
    session_id = req.session_id
    if session_id not in user_sessions:
        raise HTTPException(status_code=401, detail="Not logged in")

    session = user_sessions[session_id]
    user_token = session["access_token"]
    user_info = session["user_info"]
    user_email = user_info.get("email", "unknown")
    user_sub = user_info.get("sub", "unknown")

    print(f"\n🤖 Agent 处理: '{req.message}'")
    print(f"👤 用户: {user_email} ({user_sub})")

    mcp_headers = {
        "x-portkey-api-key": PORTKEY_API_KEY,
        "x-portkey-user-id": user_sub,
        "x-portkey-metadata": json.dumps({
            "_user": user_email,
            "_session": session_id[:8],
        }),
        "Authorization": f"Bearer {user_token}",
    }

    # IDIRA 已启用但该用户无有效 token（过期或容器重启后首次访问）
    # 正常情况下 SSO 登录时已链式完成授权；这里是 token 过期后的兜底
    if idira_oauth.enabled() and not idira_oauth.is_authorized(user_sub):
        auth_url = idira_oauth.build_auth_url(user_sub)
        logger.warning(f"⚠️  IDIRA token 已过期，需重新授权 (user={user_sub})")
        return {
            "response": None,
            "tools_used": [],
            "identity": {"user": user_email, "user_sub": user_sub},
            "idira_auth_required": True,
            "idira_auth_url": auth_url,
        }

    try:
        final_reply, tools_used = await run_agent(req.message, mcp_headers, user_email, user_sub)
    except ConsentRequiredError as e:
        return {
            "type": "consent_required",
            "consent_token": e.consent_token,
            "tool_name": e.tool_name,
            "tool_args": e.tool_args,
            "message": f"执行高危操作 [{e.tool_name}] 需要重新认证，请点击下方按钮完成身份确认后继续",
            "auth_url": f"/login?consent_token={e.consent_token}",
        }
    except idira_oauth.NeedsAuthError as e:
        # token 在 run_agent 中途过期的兜底
        return {
            "response": None,
            "tools_used": [],
            "identity": {"user": user_email, "user_sub": user_sub},
            "idira_auth_required": True,
            "idira_auth_url": e.auth_url,
        }
    except Exception as e:
        print(f"❌ Agent 失败: {e}")
        final_reply = f"Agent 调用失败: {str(e)}"
        tools_used = [{"error": str(e)}]

    return {
        "response": final_reply,
        "tools_used": tools_used,
        "identity": {"user": user_email, "user_sub": user_sub},
        "idira_authorized": idira_oauth.is_authorized() if idira_oauth.enabled() else None,
    }


@app.post("/api/logout")
async def logout(request: Request):
    session_id = request.cookies.get("session_id")
    if session_id and session_id in user_sessions:
        del user_sessions[session_id]
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie("session_id")
    return response


if __name__ == "__main__":
    import uvicorn
    print("🚀 启动 Agent (OIDC + Portkey/IDIRA)")
    print(f"   OIDC Domain:    {OIDC_DOMAIN or '❌ 未配置'}")
    print(f"   OIDC Discovery: {OIDC_DISCOVERY_URL or '❌ 未配置'}")
    print(f"   OIDC Callback:  {OIDC_CALLBACK_URL}")
    print(f"   MCP URL:        {PORTKEY_MCP_URL or '❌ 未配置'}")
    print(f"   LLM URL:        {PORTKEY_LLM_URL} ({PORTKEY_LLM_MODEL})")
    if idira_oauth.enabled():
        print(f"   IDIRA:          ✅ 已启用")
        print(f"   IDIRA Client:   {idira_oauth.IDIRA_CLIENT_ID[:8]}...")
        print(f"   IDIRA Authorize:{idira_oauth.IDIRA_AUTHORIZE_URL}")
        print(f"   IDIRA Token:    {idira_oauth.IDIRA_TOKEN_URL}")
        print(f"   IDIRA Callback: {idira_oauth.IDIRA_CALLBACK_URL}")
        print(f"   IDIRA MCP URL:  {IDIRA_MCP_URL or '(使用 PORTKEY_MCP_URL)'}")
        print(f"   IDIRA Token Dir: {idira_oauth._TOKEN_DIR}")
        print(f"   IDIRA Token:     per-user（每用户独立文件）")
    else:
        print(f"   IDIRA:          ⚠️  未启用（使用 Portkey headers）")
        print(f"   Portkey Key:    {'✅ 已配置' if PORTKEY_API_KEY else '❌ 未配置'}")
    uvicorn.run(app, host="0.0.0.0", port=3000)
