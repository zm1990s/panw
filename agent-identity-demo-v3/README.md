# Agent + MCP Identity Demo

4 层端到端身份验证架构：AI Agent 以用户身份调用工具时，用户身份贯穿每一层服务。

```
┌─────────────────────────────────────────────────────┐
│ Layer 1: Auth0 (用户身份)                            │
│ - 用户通过 Authorization Code Flow 登录              │
│ - 颁发 RS256 Access Token                           │
│ - Token 包含: sub, email, role (通过 Action 注入)   │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Layer 2: Portkey Gateway (统一入口 + 审计)           │
│ - 验证 x-portkey-api-key（Agent 合法性）            │
│ - 用 Auth0 JWKS 验签 JWT（iss, aud, exp）           │
│ - 注入 X-User-Claims: {sub, email, role}            │
│ - 路由 LLM 请求 + 记录审计日志                      │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Layer 3: MCP Server (协议适配，Streamable HTTP)      │
│ - 验证 X-User-Claims 存在（证明经过 Portkey）       │
│ - 转发 X-Forwarded-Claims + X-Internal-Auth 给 API  │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Layer 4: Business API (业务逻辑 + 权限控制)          │
│ - 验证 X-Internal-Auth（确认来自 MCP Server）       │
│ - 从 X-Forwarded-Claims 读取 role                   │
│ - 按 role 分配资源（admin / member / readonly / guest）│
└─────────────────────────────────────────────────────┘
```

## Header 流转

```
Agent → Portkey:
  x-portkey-api-key: pk-xxx
  x-portkey-user-id: auth0|xxx
  Authorization: Bearer <Access Token>

Portkey → MCP Server:
  X-User-Claims: {"sub":"auth0|xxx","email":"...","role":["admin"]}
  Authorization: Bearer <Access Token>

MCP Server → Business API:
  X-Internal-Auth: <shared secret>
  X-Forwarded-Claims: {"sub":"auth0|xxx","email":"...","role":["admin"]}
  Authorization: Bearer <Access Token>
```

## 服务端口

| 服务 | 端口 | 说明 |
|---|---|---|
| Agent Web | 3000 | 用户界面 + Auth0 登录 |
| MCP Server | 8000 | MCP 工具执行（`/mcp`） |
| Business API | 8080 | JWT 验签 + 权限控制 |

---

## 部署

### 前置条件

- Docker & Docker Compose
- Auth0 账号（配置见下方）
- Portkey 账号（配置见下方）

### 1. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入以下配置：

```env
# Auth0
AUTH0_DOMAIN=your-tenant.us.auth0.com
AUTH0_CLIENT_ID=your-client-id
AUTH0_CLIENT_SECRET=your-client-secret
AUTH0_AUDIENCE=https://your-api-identifier
AUTH0_CALLBACK_URL=http://localhost:3000/callback

# Portkey
PORTKEY_API_KEY=your-portkey-api-key
PORTKEY_MCP_URL=http://your-portkey-host/your-mcp-path
PORTKEY_LLM_URL=http://your-portkey-host/v1/chat/completions
PORTKEY_LLM_MODEL=@aws/moonshotai.kimi-k2.5

# Internal
INTERNAL_API_KEY=change-this-to-a-random-secret
```

生成 `INTERNAL_API_KEY`：

```bash
openssl rand -hex 32
```

### 2. Docker 部署（推荐）

```bash
# 首次构建并启动
docker compose up --build

# 后台运行
docker compose up -d --build

# 查看日志
docker compose logs -f

# 停止
docker compose down
```

服务启动顺序由 healthcheck 保障：`api-service` → `mcp-server` → `agent-web`。

访问 http://localhost:3000

### 3. 本地直接运行

```bash
pip install -r requirements.txt

# 三个终端分别运行，或使用 start.sh
python api_service.py     # 端口 8080
python mcp_server.py      # 端口 8000
python agent_backend.py   # 端口 3000
```

或一键启动：

```bash
chmod +x start.sh
./start.sh
```

---

## Auth0 配置

1. 创建 **Regular Web Application**，记录 Domain / Client ID / Client Secret
2. **Allowed Callback URLs** 添加 `http://localhost:3000/callback`
3. 创建 **API**，Identifier 填 `https://identity-demo-api`，算法选 RS256
4. 创建 **Login Action**，将 email 和 role 注入 Access Token：

```javascript
exports.onExecutePostLogin = async (event, api) => {
  const namespace = 'https://identity-demo-api';
  api.accessToken.setCustomClaim(`${namespace}/email`, event.user.email);
  api.accessToken.setCustomClaim(`${namespace}/role`, event.authorization?.roles ?? []);
};
```

## Portkey 配置

1. 创建 MCP Gateway，配置 JWT 验证（Auth0 JWKS URL、aud、iss）
2. 配置 `X-User-Claims` 注入，提取 `sub`、`email`、`role` 字段
3. 记录 API Key 填入 `PORTKEY_API_KEY`，MCP URL 填入 `PORTKEY_MCP_URL`

## Role 权限说明

| Role | 可读 | 可写 | 可删 | 可见资源 |
|---|---|---|---|---|
| admin | ✅ | ✅ | ✅ | 全部（含机密文档）|
| member | ✅ | ✅ | ❌ | 内部文档 |
| readonly | ✅ | ❌ | ❌ | OKR + 公开指南 |
| guest | ❌ | ❌ | ❌ | 无 |
