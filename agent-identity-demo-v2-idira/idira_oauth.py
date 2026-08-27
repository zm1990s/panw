"""
IDIRA Identity Broker OAuth 2.1 客户端

IDIRA 约束（同参考项目实测）：
  - 只支持 authorization_code + PKCE (S256)，不支持 client_credentials
  - 每个 MCP 的 OAuth 端点由 broker URL 派生：<broker_url>/OAuth2/Authorize|Token
  - scope = "openid full"
  - redirect_uri 须与 IDIRA 控制台 Register AI Agent 填写的值精确一致

环境变量：
  IDIRA_CLIENT_ID       Register AI Agent 颁发的 client_id
  IDIRA_CLIENT_SECRET   可选（无需填可留空）
  IDIRA_AUTHORIZE_URL   IDIRA OAuth Authorize 端点
  IDIRA_TOKEN_URL       IDIRA OAuth Token 端点
  IDIRA_CALLBACK_URL    OAuth 回调地址，建议使用专用路径 /callback/idira
  IDIRA_OAUTH_SCOPE     默认 "openid full"
  IDIRA_TOKEN_DIR       token 落盘目录，默认 /tmp（每用户一个文件）
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx


# ── 配置 ──────────────────────────────────────────────────────────────────────
IDIRA_CLIENT_ID     = os.environ.get("IDIRA_CLIENT_ID", "")
IDIRA_CLIENT_SECRET = os.environ.get("IDIRA_CLIENT_SECRET", "")
IDIRA_AUTHORIZE_URL = os.environ.get("IDIRA_AUTHORIZE_URL", "")
IDIRA_TOKEN_URL     = os.environ.get("IDIRA_TOKEN_URL", "")
IDIRA_CALLBACK_URL  = os.environ.get("IDIRA_CALLBACK_URL", "http://localhost:3000/callback/idira")
IDIRA_SCOPE         = os.environ.get("IDIRA_OAUTH_SCOPE", "openid full")
_TOKEN_DIR          = Path(os.environ.get("IDIRA_TOKEN_DIR", "/tmp"))

# pending 授权状态：state -> {code_verifier, user_sub, created_at}（内存，重启丢失）
# 使用独立 /callback/idira 路由后，不再依赖此字典做路由分发，
# 但仍需它来关联 state → (verifier, user_sub) 完成 PKCE 校验。
_PENDING: dict[str, dict] = {}
PENDING_TTL = 600  # 秒


# ── 异常 ──────────────────────────────────────────────────────────────────────
class NeedsAuthError(RuntimeError):
    """没有有效 token 时抛出，携带授权 URL 供前端跳转。"""
    def __init__(self, auth_url: str) -> None:
        self.auth_url = auth_url
        super().__init__(f"IDIRA 未授权，请先完成登录：{auth_url}")


# ── PKCE ──────────────────────────────────────────────────────────────────────
def _make_pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=").decode()
    )
    return verifier, challenge


# ── per-user token 文件 ───────────────────────────────────────────────────────
def _token_file(user_sub: str) -> Path:
    """返回用户专属的 token 文件路径。"""
    if not user_sub:
        return _TOKEN_DIR / "idira_token_default.json"
    safe = user_sub.replace("@", "_at_").replace("/", "_").replace(":", "_").replace("|", "_")
    return _TOKEN_DIR / f"idira_token_{safe}.json"


def _save_token(payload: dict, user_sub: str) -> None:
    data = dict(payload)
    if "expires_in" in data and "expires_at" not in data:
        data["expires_at"] = time.time() + int(data["expires_in"]) - 60
    data["user_sub"] = user_sub
    _token_file(user_sub).write_text(json.dumps(data))


def _load_token(user_sub: str) -> dict | None:
    f = _token_file(user_sub)
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except Exception:
        return None


def clear_token(user_sub: str) -> None:
    _token_file(user_sub).unlink(missing_ok=True)


def _refresh(refresh_token: str, user_sub: str) -> dict | None:
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": IDIRA_CLIENT_ID,
    }
    if IDIRA_CLIENT_SECRET:
        data["client_secret"] = IDIRA_CLIENT_SECRET
    try:
        resp = httpx.post(IDIRA_TOKEN_URL, data=data, timeout=15)
        if resp.status_code == 200:
            return resp.json()
        print(f"[idira] refresh 失败 {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"[idira] refresh 异常: {e}")
    return None


# ── 对外 API ──────────────────────────────────────────────────────────────────
def build_auth_url(user_sub: str = "") -> str:
    """生成 IDIRA 授权 URL，暂存 PKCE state + user_sub（用于回调时关联用户）。"""
    verifier, challenge = _make_pkce()
    state = secrets.token_urlsafe(32)
    _PENDING[state] = {
        "code_verifier": verifier,
        "user_sub": user_sub,
        "created_at": time.time(),
    }
    params = {
        "response_type": "code",
        "client_id": IDIRA_CLIENT_ID,
        "redirect_uri": IDIRA_CALLBACK_URL,
        "scope": IDIRA_SCOPE,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"{IDIRA_AUTHORIZE_URL}?{urlencode(params)}"


def exchange_code(state: str, code: str) -> str:
    """OAuth 回调：用 code + code_verifier 换 token 并按用户落盘。返回 user_sub。"""
    pending = _PENDING.pop(state, None)
    if not pending:
        raise RuntimeError(f"未找到 state={state}（已过期或伪造）")
    if time.time() - pending["created_at"] > PENDING_TTL:
        raise RuntimeError("IDIRA 授权超时，请重新发起")

    user_sub = pending.get("user_sub", "")

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": IDIRA_CALLBACK_URL,
        "client_id": IDIRA_CLIENT_ID,
        "code_verifier": pending["code_verifier"],
    }
    if IDIRA_CLIENT_SECRET:
        data["client_secret"] = IDIRA_CLIENT_SECRET

    resp = httpx.post(IDIRA_TOKEN_URL, data=data, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"IDIRA token 交换失败 {resp.status_code}: {resp.text[:300]}")

    token_data = resp.json()
    # 优先从 token 本身取 sub（IDIRA 签发时会包含）
    resolved_sub = token_data.get("sub") or user_sub
    _save_token(token_data, resolved_sub)
    print(f"[idira] token 已保存 → user={resolved_sub}")
    return resolved_sub


def get_access_token(user_sub: str) -> str:
    """取有效 access_token；无或过期不可刷新时抛 NeedsAuthError。"""
    data = _load_token(user_sub)
    if data:
        expires_at = data.get("expires_at", 0)
        if expires_at and time.time() < expires_at:
            return data["access_token"]
        refresh_token = data.get("refresh_token")
        if refresh_token:
            new = _refresh(refresh_token, user_sub)
            if new:
                _save_token(new, user_sub)
                return new["access_token"]
        clear_token(user_sub)
    raise NeedsAuthError(build_auth_url(user_sub))


def is_pending_state(state: str) -> bool:
    """判断某个 state 是否属于待处理的 IDIRA 授权（兼容旧版共享 /callback）。"""
    return state in _PENDING


def is_authorized(user_sub: str = "") -> bool:
    """是否持有有效（或可刷新）的 IDIRA token。"""
    data = _load_token(user_sub)
    if not data:
        return False
    expires_at = data.get("expires_at", 0)
    if expires_at and time.time() < expires_at:
        return True
    return bool(data.get("refresh_token"))


def enabled() -> bool:
    """IDIRA 是否已配置（判断是否走 broker 路径）。"""
    return bool(IDIRA_CLIENT_ID and IDIRA_AUTHORIZE_URL and IDIRA_TOKEN_URL)
