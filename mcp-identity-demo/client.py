#!/usr/bin/env python3
"""
MCP Client Demo - 四场景身份转发测试

场景 1: 直连本地 Streamable HTTP Server（无身份）
场景 2: 通过 Portkey Gateway，手动注入 X-User-Claims（claims 配置）
场景 3: 通过 Portkey Gateway + Auth0 IdP，发送 Bearer Token（JWT 验证配置）
         - 优先使用 AUTH0_ACCESS_TOKEN 环境变量
         - 未设置则自动通过 client_credentials 向 Auth0 获取 token
场景 4: Portkey 验签 + 透传 Authorization + MCP Server 自主验签
         - 客户端携带 Auth0 Bearer Token（audience=MCP Server API）
         - Portkey 验证 JWT 合法性，验证通过后原样转发 Authorization header
         - MCP Server 用 Auth0 JWKS 自主验签，提取 claims，不依赖 Portkey 注入
"""

import asyncio
import json
import os

import httpx
import requests
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

# Portkey
PORTKEY_API_KEY = os.environ.get("PORTKEY_API_KEY", "YOUR_PORTKEY_API_KEY")

# 场景 2: 对应 portkey_config_claims.json（仅 claims 转发，无 JWT 验证）
PORTKEY_MCP_URL_CLAIMS = os.environ.get(
    "PORTKEY_MCP_URL_CLAIMS",""
)

# 场景 3: 对应 portkey_config_jwt.json（Auth0 JWT 验证 + claims 注入）
PORTKEY_MCP_URL_AUTH0 = os.environ.get(
    "PORTKEY_MCP_URL_AUTH0",""
)

# 直连本地 Server
LOCAL_MCP_URL = "http://localhost:8000/mcp"

# Auth0（场景 3/4 用）
AUTH0_DOMAIN = os.environ.get("AUTH0_DOMAIN", "YOUR_TENANT.auth0.com")
AUTH0_CLIENT_ID = os.environ.get("AUTH0_CLIENT_ID", "")
AUTH0_CLIENT_SECRET = os.environ.get("AUTH0_CLIENT_SECRET", "")
AUTH0_AUDIENCE = os.environ.get("AUTH0_AUDIENCE", "")
AUTH0_ACCESS_TOKEN = os.environ.get("AUTH0_ACCESS_TOKEN", "")

# 场景 4: Token Exchange 目标受众（MCP Server 自身的 API identifier）
# 与场景 3 的 AUTH0_AUDIENCE 不同：这里是 MCP Server 注册的 API，
# 让 exchange 后的 token 专门针对 MCP Server，Server 可验 audience
AUTH0_MCP_AUDIENCE = os.environ.get("AUTH0_MCP_AUDIENCE", "")

# 场景 4: Portkey 虚拟端点（只做透传，不验 JWT、不注入 claims）
PORTKEY_MCP_URL_EXCHANGE = os.environ.get(
    "PORTKEY_MCP_URL_EXCHANGE",""
)


def get_auth0_token() -> str:
    """通过 client_credentials grant 向 Auth0 获取 Access Token。"""
    if not all([AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET, AUTH0_AUDIENCE]):
        print("⚠️  缺少 Auth0 配置 (CLIENT_ID / CLIENT_SECRET / AUDIENCE)，无法自动获取 token")
        return ""

    url = f"https://{AUTH0_DOMAIN}/oauth/token"
    payload = {
        "client_id": AUTH0_CLIENT_ID,
        "client_secret": AUTH0_CLIENT_SECRET,
        "audience": AUTH0_AUDIENCE,
        "grant_type": "client_credentials",
    }
    try:
        resp = requests.post(url, json=payload, headers={"content-type": "application/json"}, timeout=30)
        resp.raise_for_status()
        token = resp.json()["access_token"]
        print(f"✅ Auth0 Token 获取成功: {token[:40]}...")
        return token
    except Exception as e:
        print(f"❌ Auth0 Token 获取失败: {e}")
        return ""


def exchange_token(subject_token: str) -> str:
    """
    场景 4: OAuth 2.0 Token Exchange（RFC 8693）
    用现有 token 换取受众为 MCP Server 的新 token。

    Auth0 使用 client_credentials + audience 参数模拟 token exchange：
    新 token 的 audience 指向 MCP Server 的 API identifier，
    MCP Server 可用该 audience 验证 token 是否专门颁发给自己。
    """
    if not AUTH0_MCP_AUDIENCE:
        print("⚠️  未设置 AUTH0_MCP_AUDIENCE，无法执行 token exchange")
        return ""
    if not all([AUTH0_CLIENT_ID, AUTH0_CLIENT_SECRET]):
        print("⚠️  缺少 AUTH0_CLIENT_ID / AUTH0_CLIENT_SECRET，无法执行 token exchange")
        return ""

    url = f"https://{AUTH0_DOMAIN}/oauth/token"
    payload = {
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": subject_token,
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "audience": AUTH0_MCP_AUDIENCE,
        "client_id": AUTH0_CLIENT_ID,
        "client_secret": AUTH0_CLIENT_SECRET,
    }
    try:
        resp = requests.post(url, json=payload, headers={"content-type": "application/json"}, timeout=30)
        if not resp.ok:
            # Auth0 不支持标准 token exchange grant 时，回退到 client_credentials + 新 audience
            print(f"   ℹ️  Token exchange grant 不支持（{resp.status_code}），回退到 client_credentials...")
            fallback = {
                "grant_type": "client_credentials",
                "client_id": AUTH0_CLIENT_ID,
                "client_secret": AUTH0_CLIENT_SECRET,
                "audience": AUTH0_MCP_AUDIENCE,
            }
            resp = requests.post(url, json=fallback, headers={"content-type": "application/json"}, timeout=30)
            resp.raise_for_status()
        token = resp.json()["access_token"]
        print(f"✅ Exchange Token 获取成功 (audience={AUTH0_MCP_AUDIENCE}): {token[:40]}...")
        return token
    except Exception as e:
        print(f"❌ Token Exchange 失败: {e}")
        return ""


async def test_local() -> bool:
    """场景 1: 直连本地 Streamable HTTP Server（无身份转发）"""
    print("\n" + "=" * 70)
    print("📍 场景 1: 直连本地 Streamable HTTP Server（无身份转发）")
    print(f"   URL: {LOCAL_MCP_URL}")
    print("=" * 70)

    http_client = httpx.AsyncClient()
    try:
        async with streamable_http_client(
            LOCAL_MCP_URL, http_client=http_client
        ) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                print(f"\n📋 工具列表 ({len(tools.tools)} 个):")
                for tool in tools.tools:
                    print(f"   - {tool.name}: {tool.description}")

                print("\n🔍 get_user_identity（预期: identity_verified=false）...")
                result = await session.call_tool("get_user_identity", {})
                for content in result.content:
                    if content.type == "text":
                        data = json.loads(content.text)
                        verified = data.get("identity_verified", False)
                        print(f"{'✅' if not verified else '❌'} identity_verified: {verified}（预期 false）")
                        print(json.dumps(data, indent=2, ensure_ascii=False))

                print("\n🔍 echo_with_auth（预期: Unauthorized）...")
                result = await session.call_tool("echo_with_auth", {"message": "test"})
                for content in result.content:
                    if content.type == "text":
                        data = json.loads(content.text)
                        print(json.dumps(data, indent=2, ensure_ascii=False))

                return True

    except Exception as e:
        print(f"\n❌ 错误: {e}")
        print("💡 请先启动本地 Server: python server.py")
        return False


async def test_portkey_claims() -> bool:
    """场景 2: 通过 Portkey Gateway，由 Portkey 根据 API Key 注入 X-User-Claims

    对应 portkey_config_claims.json:
    - 客户端只发送 API Key，不携带任何 X-User-Claims
    - Portkey 验证 API Key，查找对应用户信息，注入 X-User-Claims 转发给 MCP Server
    - 客户端即使自己发了 X-User-Claims，Portkey 也会丢弃（防止伪造）
    """
    print("\n" + "=" * 70)
    print("📍 场景 2: Portkey Gateway API Key → X-User-Claims 注入")
    print(f"   URL: {PORTKEY_MCP_URL_CLAIMS}")
    print("   Portkey 配置: portkey_config_claims.json")
    print("=" * 70)

    if not PORTKEY_API_KEY or PORTKEY_API_KEY == "YOUR_PORTKEY_API_KEY":
        print("⚠️  未设置 PORTKEY_API_KEY，跳过")
        return False

    headers = {
        "x-portkey-api-key": PORTKEY_API_KEY,
    }
    print("\n📤 只发送 API Key，X-User-Claims 由 Portkey 注入")

    http_client = httpx.AsyncClient(headers=headers)
    try:
        async with streamable_http_client(
            PORTKEY_MCP_URL_CLAIMS, http_client=http_client
        ) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                print(f"\n📋 工具列表 ({len(tools.tools)} 个):")
                for tool in tools.tools:
                    print(f"   - {tool.name}")

                verified = False
                for tool_name, args in [
                    ("get_user_identity", {}),
                    ("echo_with_auth", {"message": "Hello Portkey Claims!"}),
                    ("list_accessible_resources", {}),
                ]:
                    print(f"\n🔍 {tool_name}...")
                    result = await session.call_tool(tool_name, args)
                    for content in result.content:
                        if content.type == "text":
                            try:
                                data = json.loads(content.text)
                                if tool_name == "get_user_identity":
                                    verified = data.get("identity_verified", False)
                                    print(f"{'✅' if verified else '❌'} identity_verified: {verified}")
                                print(json.dumps(data, indent=2, ensure_ascii=False))
                            except Exception:
                                print(content.text)

                return verified
    except BaseException as e:
        _print_exception_chain(e)
        print("💡 请检查 PORTKEY_MCP_URL_CLAIMS 及 Portkey claims 配置")
        return False


async def test_portkey_auth0() -> bool:
    """场景 3: Portkey Gateway + Auth0 IdP（完整链路）

    对应 portkey_config_jwt.json:
    - 客户端携带 Auth0 颁发的 Bearer Token
    - Portkey 向 Auth0 JWKS 端点验证 JWT 签名与有效期
    - 验证通过后 Portkey 从 JWT claims 中提取字段，注入 X-User-Claims 转发给 MCP Server
    """
    print("\n" + "=" * 70)
    print("📍 场景 3: Portkey Gateway + Auth0 IdP（完整链路）")
    print(f"   URL: {PORTKEY_MCP_URL_AUTH0}")
    print("   Portkey 配置: portkey_config_jwt.json")
    print("=" * 70)

    if not PORTKEY_API_KEY or PORTKEY_API_KEY == "YOUR_PORTKEY_API_KEY":
        print("⚠️  未设置 PORTKEY_API_KEY，跳过")
        return False

    # 优先使用环境变量中的 token，否则自动获取
    token = AUTH0_ACCESS_TOKEN
    if token:
        print(f"\n🔐 使用 AUTH0_ACCESS_TOKEN: {token[:30]}...")
    else:
        print("\n🔐 AUTH0_ACCESS_TOKEN 未设置，尝试自动获取...")
        token = get_auth0_token()

    if not token:
        print("⚠️  无法获取 Auth0 Token，跳过场景 3")
        print("   设置方法: export AUTH0_ACCESS_TOKEN=<token>")
        print("   或配置 AUTH0_DOMAIN / AUTH0_CLIENT_ID / AUTH0_CLIENT_SECRET / AUTH0_AUDIENCE")
        return False

    headers = {
        "x-portkey-api-key": PORTKEY_API_KEY,
        "Authorization": f"Bearer {token}",
    }

    # ── 预检：直接 HTTP GET，看 Portkey 返回什么（早于 MCP 握手）──
    print("\n🔎 预检: 直接 HTTP GET 探测 Portkey 端点...")
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10) as probe:
            resp = await probe.get(PORTKEY_MCP_URL_AUTH0)
            print(f"   HTTP {resp.status_code}  {resp.reason_phrase}")
            print(f"   响应头: { {k: v for k, v in resp.headers.items() if k.lower() in ('content-type', 'x-portkey-error', 'x-error', 'www-authenticate')} }")
            body_preview = resp.text[:500].strip()
            if body_preview:
                print(f"   响应体 (前500字符):\n   {body_preview}")

            if resp.status_code == 401 and "expired" in resp.text.lower():
                print("\n🔄 Token 已过期，尝试自动刷新...")
                token = get_auth0_token()
                if not token:
                    print("❌ 刷新失败，请手动更新 AUTH0_ACCESS_TOKEN")
                    return False
                print(f"✅ 新 Token: {token[:30]}...")
                headers["Authorization"] = f"Bearer {token}"
    except Exception as probe_err:
        print(f"   预检失败: {probe_err}")

    http_client = httpx.AsyncClient(headers=headers)
    try:
        async with streamable_http_client(
            PORTKEY_MCP_URL_AUTH0, http_client=http_client
        ) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                print(f"\n📋 工具列表 ({len(tools.tools)} 个):")
                for tool in tools.tools:
                    print(f"   - {tool.name}")

                verified = False
                for tool_name, args in [
                    ("get_user_identity", {}),
                    ("echo_with_auth", {"message": "Hello Portkey + Auth0!"}),
                    ("list_accessible_resources", {}),
                ]:
                    print(f"\n🔍 {tool_name}（预期: Portkey 注入 Auth0 claims）...")
                    result = await session.call_tool(tool_name, args)
                    for content in result.content:
                        if content.type == "text":
                            try:
                                data = json.loads(content.text)
                                if tool_name == "get_user_identity":
                                    verified = data.get("identity_verified", False)
                                    print(f"{'✅' if verified else '❌'} identity_verified: {verified}")
                                print(json.dumps(data, indent=2, ensure_ascii=False))
                            except Exception:
                                print(content.text)


                return verified
    except BaseException as e:
        _print_exception_chain(e)
        return False


async def test_token_exchange() -> bool:
    """场景 4: Portkey 验签 + 透传 Authorization + MCP Server 自主验签

    流程：
      Client ──(Bearer Token, aud=MCP Server API)──▶ Portkey
             Portkey: 验证 JWT 合法性（JWKS）
             Portkey: 原样转发 Authorization header（不注入 X-User-Claims）
             MCP Server: 用 Auth0 JWKS 自主验签，提取 claims

    与场景 3 的区别：
      - 场景 3: Portkey 验签后提取 claims 注入 X-User-Claims，Server 信任 Portkey
      - 场景 4: Portkey 只做验签+透传，Server 自己验签，信任链直达 Auth0
    """
    print("\n" + "=" * 70)
    print("📍 场景 4: Portkey 验签 + 透传 Authorization + Server 自主验签")
    print(f"   URL: {PORTKEY_MCP_URL_EXCHANGE}")
    print("   Portkey 配置: portkey_config_exchange.json")
    print("=" * 70)

    print(f"\n🔧 前置检查:")
    print(f"   PORTKEY_API_KEY:       {'✅ 已设置' if PORTKEY_API_KEY and PORTKEY_API_KEY != 'YOUR_PORTKEY_API_KEY' else '❌ 未设置'}")
    print(f"   PORTKEY_MCP_URL_EXCHANGE: {'✅ ' + PORTKEY_MCP_URL_EXCHANGE if PORTKEY_MCP_URL_EXCHANGE else '❌ 未设置（需要配置此环境变量）'}")
    print(f"   AUTH0_MCP_AUDIENCE:    {'✅ ' + AUTH0_MCP_AUDIENCE if AUTH0_MCP_AUDIENCE else '❌ 未设置（token exchange 将失败）'}")
    print(f"   AUTH0_ACCESS_TOKEN:    {'✅ 已提供' if AUTH0_ACCESS_TOKEN else '⚠️  未提供（将尝试 client_credentials 获取）'}")

    if not PORTKEY_API_KEY or PORTKEY_API_KEY == "YOUR_PORTKEY_API_KEY":
        print("❌ 未设置 PORTKEY_API_KEY，跳过")
        return False

    if not PORTKEY_MCP_URL_EXCHANGE:
        print("❌ 未设置 PORTKEY_MCP_URL_EXCHANGE，跳过")
        print("   设置方法: export PORTKEY_MCP_URL_EXCHANGE=http://<portkey-host>/<slug>/mcp")
        return False

    if not AUTH0_MCP_AUDIENCE:
        print("❌ 未设置 AUTH0_MCP_AUDIENCE，跳过")
        print("   设置方法: export AUTH0_MCP_AUDIENCE=<在 Auth0 为 MCP Server 注册的 API identifier>")
        return False

    # 步骤 1：始终重新获取 audience=AUTH0_MCP_AUDIENCE 的 token
    # 不复用 AUTH0_ACCESS_TOKEN —— 那个 token 的 aud 是场景 3 的 Portkey API，
    # 场景 4 需要 aud=AUTH0_MCP_AUDIENCE 才能通过 Server 侧的 audience 验证
    print(f"\n🔐 步骤 1: 获取 Auth0 Token (audience={AUTH0_MCP_AUDIENCE})...")
    mcp_token = exchange_token("")
    if not mcp_token:
        print("❌ 无法获取 Token，跳过场景 4")
        return False

    # debug: 打印 token header（不解码签名，只看 claims 元数据）
    try:
        import base64
        parts = mcp_token.split(".")
        if len(parts) == 3:
            padded = parts[1] + "=" * (-len(parts[1]) % 4)
            decoded = json.loads(base64.urlsafe_b64decode(padded))
            print(f"\n🔬 MCP Token 解码 (payload):")
            print(f"   sub:  {decoded.get('sub', '(无)')}")
            print(f"   aud:  {decoded.get('aud', '(无)')}")
            print(f"   iss:  {decoded.get('iss', '(无)')}")
            import time
            exp = decoded.get("exp")
            if exp:
                remaining = exp - int(time.time())
                print(f"   exp:  {exp} (还剩 {remaining}s {'✅' if remaining > 0 else '❌ 已过期'})")
    except Exception as dbg_err:
        print(f"   Token 解码失败: {dbg_err}")

    # 步骤 3：携带 MCP token 发给 Portkey（Portkey 验签后原样转发 Authorization header）
    headers = {
        "x-portkey-api-key": PORTKEY_API_KEY,
        "Authorization": f"Bearer {mcp_token}",
    }

    print(f"\n🔎 步骤 3: 预检 Portkey 端点 ({PORTKEY_MCP_URL_EXCHANGE})...")
    try:
        async with httpx.AsyncClient(headers=headers, timeout=10) as probe:
            resp = await probe.get(PORTKEY_MCP_URL_EXCHANGE)
            print(f"   HTTP {resp.status_code}  {resp.reason_phrase}")
            debug_headers = {k: v for k, v in resp.headers.items()
                             if k.lower() in ("content-type", "x-portkey-error", "x-error", "www-authenticate")}
            if debug_headers:
                print(f"   响应头: {debug_headers}")
            body = resp.text[:300].strip()
            if body:
                print(f"   响应体: {body}")
            if resp.status_code in (401, 403, 404):
                print(f"   ❌ 认证或路由失败（{resp.status_code}），终止场景 4")
                return False
            # 406 = Portkey JWT 验证通过但 GET 缺少 Accept: text/event-stream，端点实际可达
            print("   ✅ Portkey JWT 验证通过，端点可达，继续 MCP 连接...")
    except Exception as e:
        print(f"   预检请求异常: {e}")

    print("\n🔐 步骤 4: MCP 连接（Server 将自主验签 Authorization header 中的 JWT）...")
    http_client = httpx.AsyncClient(headers=headers)
    try:
        async with streamable_http_client(
            PORTKEY_MCP_URL_EXCHANGE, http_client=http_client
        ) as (read, write, _get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()

                tools = await session.list_tools()
                print(f"\n📋 工具列表 ({len(tools.tools)} 个):")
                for tool in tools.tools:
                    print(f"   - {tool.name}")

                verified = False
                for tool_name, args in [
                    ("get_user_identity", {}),
                    ("echo_with_auth", {"message": "Hello from Token Exchange!"}),
                    ("list_accessible_resources", {}),
                ]:
                    print(f"\n🔍 {tool_name}（预期: identity_source=server_jwt_verification）...")
                    result = await session.call_tool(tool_name, args)
                    for content in result.content:
                        if content.type == "text":
                            try:
                                data = json.loads(content.text)
                                if tool_name == "get_user_identity":
                                    verified = data.get("identity_verified", False)
                                    source = data.get("identity_source", "unknown")
                                    print(f"{'✅' if verified else '❌'} identity_verified: {verified}  source: {source}")
                                print(json.dumps(data, indent=2, ensure_ascii=False))
                            except Exception:
                                print(content.text)

                print("\n⏭️  跳过 read_resource（Portkey 不代理 MCP 资源请求）")
                return verified
    except BaseException as e:
        _print_exception_chain(e)
        print("💡 请检查 PORTKEY_MCP_URL_EXCHANGE 及 Server 的 AUTH0_DOMAIN / AUTH0_AUDIENCE 配置")
        return False


def _print_exception_chain(exc: BaseException, indent: int = 0) -> None:
    """递归展开 ExceptionGroup / TaskGroup 子异常，打印完整错误链。"""
    prefix = "   " * indent
    if hasattr(exc, "exceptions"):  # ExceptionGroup / BaseExceptionGroup
        print(f"{prefix}❌ {type(exc).__name__}: {exc}")
        for i, sub in enumerate(exc.exceptions):
            print(f"{prefix}   └─ 子异常 [{i}]:")
            _print_exception_chain(sub, indent + 2)
    else:
        import traceback
        print(f"{prefix}❌ {type(exc).__name__}: {exc}")
        tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        # 只打印最后几帧，避免 MCP 内部栈帧噪音
        relevant = [l for l in "".join(tb_lines).splitlines()
                    if "mcp-identity-demo" in l or "client.py" in l or "Error" in l or "error" in l]
        for line in relevant:
            print(f"{prefix}   {line}")


async def main():
    print("🚀 MCP Identity Security Demo Client")
    print(f"   Portkey API Key:       {PORTKEY_API_KEY[:10]}...")
    print(f"   场景2 URL (claims):    {PORTKEY_MCP_URL_CLAIMS}")
    print(f"   场景3 URL (auth0):     {PORTKEY_MCP_URL_AUTH0}")
    print(f"   场景4 URL (exchange):  {PORTKEY_MCP_URL_EXCHANGE}")
    print(f"   Auth0 Domain:          {AUTH0_DOMAIN}")
    print(f"   Auth0 MCP Audience:    {AUTH0_MCP_AUDIENCE or '未设置（场景4将跳过）'}")
    print(f"   Auth0 Token:           {'已提供' if AUTH0_ACCESS_TOKEN else '未提供（将自动获取或跳过）'}")

    results = {
        "场景1 直连无身份":            await test_local(),
        "场景2 Portkey claims":        await test_portkey_claims(),
        "场景3 Portkey + Auth0":       await test_portkey_auth0(),
        "场景4 Token Exchange + 验签": await test_token_exchange(),
    }

    print("\n" + "=" * 70)
    print("📊 测试结果汇总")
    print("=" * 70)
    for scenario, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL/Skip"
        print(f"   {scenario:30s} {status}")

    print("\n💡 预期结果:")
    print("   - 场景1 直连无身份:         identity_verified = false")
    print("   - 场景2 Portkey claims:       identity_verified = true, source=portkey_claims_header")
    print("   - 场景3 Portkey + Auth0:      identity_verified = true, source=portkey_claims_header")
    print("   - 场景4 Token Exchange + 验签: identity_verified = true, source=server_jwt_verification")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
