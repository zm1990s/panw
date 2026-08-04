# MCP Identity Security Demo (v1.x 稳定版)

通过 Portkey MCP Gateway + Auth0 IdP 实现身份转发和授权的完整 Demo。
**使用 MCP Python SDK v1.x 稳定版，兼容 Python 3.11+。**

## 四个演示场景

| 场景 | 身份来源 | Portkey 行为 | Server 验证方式 |
|------|----------|--------------|-----------------|
| 1. 直连本地 Server | 无 | 无 | 无 |
| 2. Portkey API Key → Claims 注入 | Portkey 根据 API Key 查用户信息 | 注入 `X-User-Claims` | 信任 `X-User-Claims` |
| 3. Portkey + Auth0 JWT | Auth0 Bearer Token | JWKS 验签 → 注入 `X-User-Claims` | 信任 `X-User-Claims` |
| 4. Portkey 验签 + Server 自主验签 | Auth0 Bearer Token（MCP-scoped） | JWKS 验签 → 透传 `Authorization` | 自主 JWKS 验签 |

## 架构

```
场景 1: 直连
  Client ──────────────────────────────────▶ MCP Server (localhost:8000)
                                              identity_verified=false

场景 2: API Key → Claims 注入
  Client ──[API Key]──▶ Portkey ──[X-User-Claims]──▶ MCP Server
                        查用户信息并注入                信任 header

场景 3: Auth0 JWT → Claims 注入
  Client ──[API Key + Bearer Token]──▶ Portkey ──[X-User-Claims]──▶ MCP Server
                                       JWKS 验签后注入               信任 header

场景 4: Auth0 JWT → Server 自主验签
  Client ──[API Key + Bearer Token]──▶ Portkey ──[Authorization]──▶ MCP Server
          (aud=MCP Server API)         JWKS 验签后原样透传            自主 JWKS 验签
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

```bash
cp .env.example .env
# 编辑 .env 填入配置
set -a && source .env && set +a
```

### 3. 启动 MCP Server

```bash
python server.py
```

Server 运行在 `http://localhost:8000`，健康检查：`http://localhost:8000/health`

### 4. 运行测试

```bash
python client.py
```

## 环境变量说明

### Client 使用

| 变量 | 说明 |
|------|------|
| `PORTKEY_API_KEY` | Portkey API 密钥，每个请求必须携带 |
| `PORTKEY_MCP_URL_CLAIMS` | 场景 2 的 Portkey 虚拟端点 URL |
| `PORTKEY_MCP_URL_AUTH0` | 场景 3 的 Portkey 虚拟端点 URL |
| `PORTKEY_MCP_URL_EXCHANGE` | 场景 4 的 Portkey 虚拟端点 URL |
| `AUTH0_DOMAIN` | Auth0 租户域名，用于调用 `/oauth/token` 获取 token |
| `AUTH0_CLIENT_ID` | M2M 应用 ID，向 Auth0 换 token 时使用 |
| `AUTH0_CLIENT_SECRET` | M2M 应用密钥，向 Auth0 换 token 时使用 |
| `AUTH0_AUDIENCE` | 场景 3 的 token 受众（Portkey API identifier） |
| `AUTH0_MCP_AUDIENCE` | 场景 4 的 token 受众（MCP Server API identifier） |
| `AUTH0_ACCESS_TOKEN` | 手动提供的 token，跳过场景 3 的自动获取步骤 |

### Server 使用

| 变量 | 说明 |
|------|------|
| `AUTH0_DOMAIN` | 拼接 JWKS URL：`https://{AUTH0_DOMAIN}/.well-known/jwks.json` |
| `AUTH0_AUDIENCE` | 场景 4 验签时校验 token 的 `aud` 字段，需与 `AUTH0_MCP_AUDIENCE` 一致 |

## 文件说明

| 文件 | 说明 |
|------|------|
| `server.py` | MCP Server（FastAPI + Streamable HTTP） |
| `client.py` | MCP Client，四场景测试 |
| `requirements.txt` | Python 依赖 |
| `Dockerfile` + `docker-compose.yml` | 容器化部署 |
| `examples/portkey_config_claims.json` | 场景 2 Portkey 配置 |
| `examples/portkey_config_jwt.json` | 场景 3 Portkey 配置 |
| `examples/portkey_config_exchange.json` | 场景 4 Portkey 配置 |
| `examples/auth0_action.js` | Auth0 Post-Login Action，注入自定义 claims |

## Portkey Dashboard 配置

为每个场景分别创建一个虚拟端点，挂载对应配置文件：

| 场景 | Slug 示例 | 配置文件 |
|------|-----------|----------|
| 2 | `identity-demo-mcp` | `portkey_config_claims.json` |
| 3 | `identity-demo-mcp-oauth` | `portkey_config_jwt.json` |
| 4 | `identity-demo-mcp-exchange` | `portkey_config_exchange.json` |

MCP Server URL 填本地地址（需 ngrok 暴露）或内网地址：`http://YOUR_SERVER:8000/mcp`

## Auth0 配置

1. 创建 **Machine to Machine Application**，获取 Client ID / Secret
2. 创建两个 **API**：
   - 场景 3 用：Identifier 填入 `AUTH0_AUDIENCE`，授权给 M2M App
   - 场景 4 用：Identifier 填入 `AUTH0_MCP_AUDIENCE`，授权给 M2M App
3. 将 `examples/auth0_action.js` 添加为 **Post-Login Action**，为 access_token 注入 `workspace_id`、`organisation_id` 等自定义 claims
4. 在 M2M App 的 **Application Metadata** 中配置：`workspace_id`、`organisation_id`（供 `client_credentials` 流程使用）

## 预期结果

| 场景 | `identity_verified` | `identity_source` |
|------|---------------------|-------------------|
| 1. 直连 | `false` | `none` |
| 2. API Key claims | `true` | `portkey_claims_header` |
| 3. Auth0 + Portkey 注入 | `true` | `portkey_claims_header` |
| 4. Auth0 + Server 验签 | `true` | `server_jwt_verification` |

## 故障排查

**Server 收不到 X-User-Claims**
- 确认 Portkey Config 中启用了 `user_identity_forwarding`
- 访问 `http://localhost:8000/logs` 查看请求 headers

**场景 4 identity_verified=false**
- 确认 Server 的 `AUTH0_AUDIENCE` 与 token 的 `aud` 一致（均为 `AUTH0_MCP_AUDIENCE` 的值）
- 查看 Server 日志中 `🔬` 开头的行，对比 token payload 与 Server 配置

**Token 过期（401 Unauthorized）**
- 场景 3：重新 `export AUTH0_ACCESS_TOKEN=<new_token>` 或配置 Auth0 client_credentials 自动获取
- 场景 4：由 `client_credentials` 自动获取，检查 `AUTH0_CLIENT_ID` / `AUTH0_CLIENT_SECRET` 是否正确

**ImportError: cannot import name 'MCPServer'**
- 安装的是 v2 API，请确保使用 v1.x：
```bash
pip install "mcp>=1.27,<2"
```
