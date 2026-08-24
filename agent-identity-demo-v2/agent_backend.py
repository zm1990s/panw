#!/usr/bin/env python3
"""
Agent Web Backend - Auth0 用户身份 + Portkey LLM (Kimi K2)

身份流转：
Layer 1: Auth0 - 用户身份
Layer 2: Portkey Gateway - LLM 调用 + MCP 审计
Layer 3: MCP Server - 工具执行（Streamable HTTP）
Layer 4: Business API - JWT 验签 + 业务逻辑
"""

import json
import logging
import os
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

# ── 配置 ──────────────────────────────────────────────────────────────────────
PORTKEY_API_KEY = os.environ.get("PORTKEY_API_KEY", "")
PORTKEY_MCP_URL = os.environ.get("PORTKEY_MCP_URL", "")
PORTKEY_LLM_URL = os.environ.get("PORTKEY_LLM_URL", "")
PORTKEY_LLM_MODEL = os.environ.get("PORTKEY_LLM_MODEL", "@aws/moonshotai.kimi-k2.5")

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

app = FastAPI(title="Agent Identity Demo - Auth0 + Portkey")
templates = Jinja2Templates(directory="templates")

# MCP 工具 schema（用于 LLM function calling）
MCP_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_user_identity",
            "description": "获取当前登录用户的完整身份信息，包括 Auth0 sub、email 和各层验证状态",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "echo_with_auth",
            "description": "将用户消息回显，同时附带认证信息（authenticated_as）",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "要回显的消息内容"}
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_accessible_resources",
            "description": "列出当前用户有权访问的资源列表，基于用户 sub 从数据库查询",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_user_profile",
            "description": "获取用户的详细 Profile，包括姓名、组织、工作区、角色等",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]

SYSTEM_PROMPT = """你是一个身份验证演示助手，运行在一个 4 层身份验证架构中：
- Layer 1: Auth0（用户身份 JWT）
- Layer 2: Portkey Gateway（审计 + LLM 路由）
- Layer 3: MCP Server（工具执行，Streamable HTTP）
- Layer 4: Business API（JWT 验签 + 授权）

你可以调用以下工具来展示身份流转：
- get_user_identity：查看完整身份链
- list_accessible_resources：查看用户权限和资源
- get_user_profile：查看用户详情
- echo_with_auth：认证回显

请用中文回复，结合工具结果给出清晰的解释。"""


class ChatRequest(BaseModel):
    message: str
    session_id: str


# ── MCP 工具调用 ──────────────────────────────────────────────────────────────

async def call_mcp_tool(tool_name: str, tool_args: dict, mcp_headers: dict) -> str:
    logger.info(f"🔧 call_mcp_tool: {tool_name} → {PORTKEY_MCP_URL}")
    logger.info(f"   x-portkey-api-key:  {'✅ ' + mcp_headers.get('x-portkey-api-key','')[:12] + '...' if mcp_headers.get('x-portkey-api-key') else '❌ missing'}")
    logger.info(f"   x-portkey-user-id:  {mcp_headers.get('x-portkey-user-id', '❌ missing')}")
    logger.info(f"   Authorization:       {'✅ Bearer ' + mcp_headers.get('Authorization','')[7:27] + '...' if mcp_headers.get('Authorization') else '❌ missing'}")
    logger.info(f"   x-portkey-metadata: {mcp_headers.get('x-portkey-metadata', '❌ missing')}")
    try:
        async with httpx.AsyncClient(
            headers=mcp_headers,
            timeout=httpx.Timeout(30, read=60),
        ) as http_client:
            async with streamable_http_client(
                PORTKEY_MCP_URL, http_client=http_client
            ) as (read, write, _):
                async with ClientSession(read, write) as mcp_session:
                    await mcp_session.initialize()
                    result = await mcp_session.call_tool(tool_name, tool_args)
    except* Exception as eg:
        for exc in eg.exceptions:
            logger.error(f"MCP TaskGroup 子异常: {type(exc).__name__}: {exc}")
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

async def run_agent(
    user_message: str,
    mcp_headers: dict,
    user_email: str,
) -> tuple[str, list[dict]]:
    llm_headers = {
        "Content-Type": "application/json",
        "x-portkey-api-key": PORTKEY_API_KEY,
        "x-portkey-metadata": json.dumps({"_user": user_email, "_layer": "agent-llm"}),
    }

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    tools_used = []
    max_iterations = 5

    async with httpx.AsyncClient(timeout=60) as client:
        for _ in range(max_iterations):
            payload = {
                "model": PORTKEY_LLM_MODEL,
                "messages": messages,
                "tools": MCP_TOOLS_SCHEMA,
                "tool_choice": "auto",
                "max_tokens": 1024,
            }

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

                try:
                    tool_result = await call_mcp_tool(fn_name, fn_args, mcp_headers)
                    tools_used.append({"tool": fn_name, "args": fn_args, "output": tool_result})
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


# ── Auth0 登录流程 ─────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


@app.get("/login")
async def login():
    oidc = await get_oidc_config()
    auth_url = (
        f"{oidc['authorization_endpoint']}"
        f"?response_type=code"
        f"&client_id={OIDC_CLIENT_ID}"
        f"&redirect_uri={OIDC_CALLBACK_URL}"
        f"&scope=openid profile email"
        + (f"&audience={OIDC_AUDIENCE}" if OIDC_AUDIENCE else "")
    )
    return RedirectResponse(url=auth_url)


async def _handle_callback(code: str) -> RedirectResponse:
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

    session_id = str(uuid.uuid4())
    user_sessions[session_id] = {
        "user_info": user_info,
        "access_token": access_token,
        "login_time": datetime.utcnow().isoformat(),
    }

    response = RedirectResponse(url="/agent")
    response.set_cookie(key="session_id", value=session_id, httponly=True, samesite="lax")
    return response


@app.get("/callback")
async def callback_get(
    request: Request,
    code: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
):
    if error:
        logger.error(f"OIDC callback error: {error} — {error_description}")
        raise HTTPException(status_code=400, detail=f"OIDC error: {error}: {error_description}")
    if not code:
        logger.error(f"OIDC callback: missing code. Params: {dict(request.query_params)}")
        raise HTTPException(status_code=400, detail="Missing authorization code in callback")
    return await _handle_callback(code)


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
    return await _handle_callback(code)


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

    try:
        final_reply, tools_used = await run_agent(req.message, mcp_headers, user_email)
    except Exception as e:
        print(f"❌ Agent 失败: {e}")
        final_reply = f"Agent 调用失败: {str(e)}"
        tools_used = [{"error": str(e)}]

    return {
        "response": final_reply,
        "tools_used": tools_used,
        "identity": {"user": user_email, "user_sub": user_sub},
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
    print("🚀 启动 Agent (OIDC + Portkey)")
    print(f"   OIDC Domain:    {OIDC_DOMAIN}")
    print(f"   OIDC Discovery: {OIDC_DISCOVERY_URL}")
    print(f"   Portkey MCP: {PORTKEY_MCP_URL}")
    print(f"   Portkey LLM: {PORTKEY_LLM_URL} ({PORTKEY_LLM_MODEL})")
    uvicorn.run(app, host="0.0.0.0", port=3000)
