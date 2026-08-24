# Agent + MCP Identity Demo

4 层端到端身份验证架构：AI Agent 以用户身份调用工具时，用户身份贯穿每一层服务。

```
┌─────────────────────────────────────────────────────┐
│ Layer 1: SSO (用户身份)                              │
│ - 用户通过 Authorization Code Flow 登录              │
│ - 颁发 RS256 Access Token                           │
│ - Token 包含: sub, email, role (通过 Action 注入)   │
└─────────────────────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────────────┐
│ Layer 2: Portkey Gateway (统一入口 + 审计)           │
│ - 验证 x-portkey-api-key（Agent 合法性）            │
│ - 用 SSO JWKS 验签 JWT（iss, aud, exp）             │
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
  x-portkey-user-id: user|xxx
  Authorization: Bearer <Access Token>

Portkey → MCP Server:
  X-User-Claims: {"sub":"user|xxx","email":"...","role":["admin"]}
  Authorization: Bearer <Access Token>

MCP Server → Business API:
  X-Internal-Auth: <shared secret>
  X-Forwarded-Claims: {"sub":"user|xxx","email":"...","role":["admin"]}
  Authorization: Bearer <Access Token>
```

## 服务端口

| 服务 | 端口 | 说明 |
|---|---|---|
| Agent Web | 3000 | 用户界面 + SSO 登录 |
| MCP Server | 8000 | MCP 工具执行（`/mcp`） |
| Business API | 8080 | JWT 验签 + 权限控制 |

---

## 部署方式

### 方式一：单机部署（全部服务在同一台机器）

#### 前置条件

- Docker & Docker Compose
- SSO 账号（Auth0 / Okta / CyberArk 等，配置见下方）
- Portkey 账号（配置见下方）

#### 1. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入以下配置：

```env
# SSO / OIDC Provider
OIDC_DOMAIN=your-tenant.auth0.com
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
OIDC_AUDIENCE=https://identity-demo-api
OIDC_CALLBACK_URL=http://localhost:3000/callback
# CyberArk / Okta 等非 Auth0 Provider 需手动指定：
# OIDC_DISCOVERY_URL=https://{tenant}.id.cyberark.cloud/oidc/.well-known/openid-configuration

# Portkey
PORTKEY_API_KEY=your-portkey-api-key
PORTKEY_MCP_URL=https://mcp.portkey.ai/identity-demo/mcp
PORTKEY_LLM_URL=https://api.portkey.ai/v1/chat/completions
PORTKEY_LLM_MODEL=gpt-4o

# Internal
INTERNAL_API_KEY=change-this-to-a-random-secret
```

生成 `INTERNAL_API_KEY`：

```bash
openssl rand -hex 32
```

#### 2. Docker 部署（推荐）

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

#### 3. 本地直接运行

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

### 方式二：前后端分离部署

前端（`agent-web`）与后端（`mcp-server` + `api-service`）可部署在不同机器。两侧通过 Portkey 云端中转通信，无需直接网络互通。

```
[前端机器]              [Portkey 云端]           [后端机器]
agent-web :3000  ──►  mcp.portkey.ai  ──►  mcp-server :8000
                                                    │
                                              api-service :8080
```

#### 后端机器

```bash
# 配置后端环境变量
cp .env.backend.example .env.backend
# 编辑 .env.backend 填入 OIDC_DOMAIN、OIDC_AUDIENCE、INTERNAL_API_KEY

# 启动后端服务
docker compose -f docker-compose.backend.yml up -d --build
```

`.env.backend` 所需变量：

```env
OIDC_DOMAIN=your-tenant.auth0.com
OIDC_AUDIENCE=https://identity-demo-api
INTERNAL_API_KEY=your-shared-secret
```

#### 前端机器

```bash
# 配置前端环境变量
cp .env.frontend.example .env.frontend
# 编辑 .env.frontend，重点填写 OIDC_CALLBACK_URL 和 PORTKEY_MCP_URL

# 启动前端服务
docker compose -f docker-compose.frontend.yml up -d --build
```

`.env.frontend` 所需变量：

```env
OIDC_DOMAIN=your-tenant.auth0.com
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
OIDC_AUDIENCE=https://identity-demo-api
OIDC_CALLBACK_URL=https://your-frontend-domain.com/callback  # 改为前端公网地址

PORTKEY_API_KEY=pk-your-portkey-api-key
PORTKEY_MCP_URL=https://mcp.portkey.ai/identity-demo/mcp     # Portkey 控制台配置的 MCP 地址
PORTKEY_LLM_URL=https://api.portkey.ai/v1/chat/completions
PORTKEY_LLM_MODEL=gpt-4o
```

#### 分离部署注意事项

1. **Portkey 控制台**：将 MCP 地址指向后端机器的公网 IP:8000
2. **SSO 控制台**：将 `OIDC_CALLBACK_URL` 加入回调地址白名单
3. **后端防火墙**（可选加固）：8000 端口只允许 Portkey IP 段访问

---

## SSO 配置（以 Auth0 为例）

1. 创建 **Regular Web Application**，记录 Domain / Client ID / Client Secret
2. **Allowed Callback URLs** 添加回调地址（单机：`http://localhost:3000/callback`；分离部署：前端公网地址）
3. 创建 **API**，Identifier 填 `https://identity-demo-api`，算法选 RS256
4. 创建 **Login Action**，将 email 和 role 注入 Access Token：

```javascript
exports.onExecutePostLogin = async (event, api) => {
  const namespace = 'https://identity-demo-api';
  api.accessToken.setCustomClaim(`${namespace}/email`, event.user.email);
  api.accessToken.setCustomClaim(`${namespace}/role`, event.authorization?.roles ?? []);
};
```

使用其他 OIDC Provider（Okta、CyberArk 等）时，在 `.env` 中额外指定 Discovery URL：

```env
OIDC_DISCOVERY_URL=https://{tenant}.id.cyberark.cloud/oidc/.well-known/openid-configuration
```

## Portkey 配置

1. 创建 MCP Gateway，配置 JWT 验证（SSO JWKS URL、aud、iss）
2. 配置 `X-User-Claims` 注入，提取 `sub`、`email`、`role` 字段
3. 记录 API Key 填入 `PORTKEY_API_KEY`，MCP URL 填入 `PORTKEY_MCP_URL`

## Role 权限说明

| Role | 可读 | 可写 | 可删 | 可见资源 |
|---|---|---|---|---|
| admin | ✅ | ✅ | ✅ | 全部（含机密文档）|
| member | ✅ | ✅ | ❌ | 内部文档 |
| readonly | ✅ | ❌ | ❌ | OKR + 公开指南 |
| guest | ❌ | ❌ | ❌ | 无 |
