# PANW AI Runtime Security MCP 服务器

PANW AI Runtime Security MCP 服务器允许您将 Palo Alto Networks AI 安全分析能力直接集成到任何支持[Model Context Protocol (MCP)](https://modelcontextprotocol.io/introduction)的客户端中，如 Claude Desktop、Visual Studio Code 或 Cursor IDE。

通过此服务器，您可以在使用大型语言模型时实时评估内容安全风险，确保人工智能交互的安全合规。

---

## 🚀 功能特点

- 实时内容风险分析
- 与任何 MCP 兼容客户端的无缝集成
- 支持多种输入类型（文本输入、输出、代码输入、代码输出）
- 基于 Palo Alto Networks AI 安全 API 的内容检测
- 提供本地版本和 SSE 服务器版本，适应不同使用场景

---

## 💠 版本说明

本项目提供两个版本，分别适用于不同场景：

### 本地版本 (Local Version)

- 作为本地 MCP 服务进程运行，无需 HTTP 服务器
- 适合与支持直接启动 MCP 服务器进程的客户端集成（如 VS Code、Cursor IDE）
- 轻量级，资源占用少，配置简单

### SSE 版本 (Server-Sent Events Version)

- 作为 HTTP 服务器运行，支持 SSE 协议
- 可以远程访问，支持多客户端连接
- 适合部署为服务或容器
- 可通过 Docker 简便部署

---

## 🔑 准备工作

在开始使用前，您需要：

1. Palo Alto Networks AI Security API 密钥
2. 配置 AI Security  profile name（安全配置文件名称）


---

## 📋 安装指南

### 下载项目文件

https://github.com/zm1990s/panw/tree/main/panw-mcp-server


---

## ⚙️ 使用方法

### 在 Visual Studio Code 中使用本地版本

1. 安装 VS Code MCP 插件
2. 切换到 Agent 模式，点击配置按钮，选择 `Add More Tool` 添加 PANW AIRS MCP Server
3. 根据向导设置启动命令，设置完成后



```json
{
    "mcp": {
        "servers": {
            "PANW-AI-Security": {
                "type": "stdio",
                "command": "uv",
                "args": [
                    "run",
                    "src/panw_airs_mcp_local.py"
                ],
                "env": {
                    "AIRS_PROFILENAME": "PROFILENAME",
                    "AIRS_API_KEY": "APIKEY"

                },
            }
        }
    }
}
```

4. 保存设置后，VS Code 会自动启动 MCP Server，确保没有报错
5. 现在您可以在 VS Code 中访问 `scan_with_airs_api` 工具

![alt text](img/1.png)

在 VS Code 上的测试截图：

<img src="img/3.jpg" alt="alt text" style="zoom:50%;" />

## 

### 在 Cursor IDE 中使用本地版本

1. 打开 **Settings** → **MCP** 标签页
2. 点击 **"Add new global MCP server"**
3. 在 `mcp.json` 文件中粘贴以下配置：

```json
{
    "mcpServers": {
      "PANW-AI-Security": {
        "command": "python",
        "args": [
          "~/ai/cursor/panw-mcp-server/local-version/src/panw_airs_mcp_local.py"
        ],
        "env": {
          "AIRS_API_KEY": "APIKEY",
          "AIRS_PROFILENAME": "PROFILENAME"
        }
      }
    }
  }
```

![alt text](img/2.png)

### 本地启动 SSE 版本

目前有两个版本的 python 文件，如果使用 v2，则会从 http 请求中直接获取 key，无需设置环境变量，详见在 Dify 中调用 3。

1. 设置环境变量

```bash
export AIRS_API_KEY="您的API密钥"
export AIRS_PROFILENAME="您的配置文件名"
```

2. 运行服务器：

```bash
python sse-version/src/panw_airs_mcp_sse.py --host 0.0.0.0 --port 8080
```

3. 服务器将在 http://localhost:8080 上启动
4. 配置您的 MCP 客户端连接到此 URL

### 使用 Docker 启动 SSE 版本



1. 构建 Docker 镜像：

```bash
cd sse-version
docker build -t panw-airs-mcp-sse .
```

2. 创建环境变量文件

```shell
cat >.env <<EOF
AIRS_PROFILENAME=PROFILENAME
AIRS_API_KEY=KEY
EOF
```
3. 运行容器：

```bash
docker run --env-file .env  -p 8080:8080 panw-airs-mcp-sse
```

或者用我已经打包好的 image：
```bash
docker run --env-file .env  -p 8080:8080 dyadin/panw-airs-mcp
```

4. 服务将在 http://YOURIPADD:8080 上可用

### 在 Dify 中调用 1

Dify 1.x 中，可以通过插件的方式来对接 MCP SSE：

示例的配置文件如下：

```json
{
    "PANW-AI-Security": {
        "url": "http://10.10.50.144:8080/sse",
        "env": {
            "airs_api_key": "XXXX",
            "airs_ai_profile_name": "XXXX"
        }
    }
}
```



<img src="img/4.png" alt="alt text" style="zoom:50%;" />

在配置完成后确保状态为“已授权”。

通常，SSE 服务侧会有下列日志：

```
INFO:     172.17.0.1:55850 - "GET /sse HTTP/1.1" 200 OK
INFO:     172.17.0.1:55864 - "POST /messages/?session_id=58971fab220142dd825004ce292124a9 HTTP/1.1" 202 Accepted
INFO:     172.17.0.1:55864 - "POST /messages/?session_id=58971fab220142dd825004ce292124a9 HTTP/1.1" 202 Accepted
INFO:     172.17.0.1:55864 - "POST /messages/?session_id=58971fab220142dd825004ce292124a9 HTTP/1.1" 202 Accepted
Processing request of type ListToolsRequest
```



在 Agent 中使用示例：

<img src="img/5.png" alt="alt text" style="zoom:50%;" />

同样，SSE 服务侧会有类似下面的日志：

```
INFO:     172.17.0.1:52272 - "POST /messages/?session_id=54cddea100c946859c4c908e2ff3b87f HTTP/1.1" 202 Accepted
Processing request of type CallToolRequest
```



### 在 Dify 中调用 2



Dify 1.x 中，也可以在工作流的 Agent 中调用：

<img src="img/7.jpg" alt="alt text" style="zoom:50%;" />

示例的配置文件如下：

```json
{
    "PANW-AI-Security": {
        "url": "http://10.10.50.144:8080/sse",
        "env": {
            "airs_api_key": "XXXX",
            "airs_ai_profile_name": "XXXX"
        }
    }
}
```

使用效果：

<img src="img/6.png" alt="alt text" style="zoom:50%;" />

<img src="img/8.png" alt="alt text" style="zoom:50%;" />

### 在 Dify 中调用 3

如果使用 v2-url 的 SSE，可以通过下列方式访问，SSE 服务启动时不在需要环境变量：

```json
{
    "PANW-AI-Security": {
        "url": "http://10.10.50.144:8080/sse?key=CyGQbXXXX&profilename=XXXX"
    }
}
```

如果使用 v2-header 的 SSE，可以通过下列方式访问，SSE 服务启动时不在需要环境变量：

```json
{
    "PANW-AI-Security": {
        "url": "http://10.10.50.144:8080/sse",
        "headers": {
            "airs_api_key": "CyGQXXXX",
            "airs_ai_profile_name": "XXXX"
        }
    }
}
```





## 🛠 工具功能

### scan_with_airs_api

此工具调用 Palo Alto Networks AI Security API 进行内容检测。

**参数:**
- `inputoroutput`: 输入类型，可以是 "input"、"output"、"codeinput" 或 "codeoutput"
- `query`: 要检查的文本内容
- `profileoverride`: (仅本地版本) 覆盖默认的安全配置文件名称
- `modelname`: AI模型名称
- `appname`: 应用名称
- `appuser`: 用户标识

**返回:**
- API 返回的 action 结果和完整 JSON 响应



## 📝 注意事项

1. 确保 API 密钥和配置文件名正确设置
2. SSE 版本默认在 0.0.0.0:8080 上监听，可以通过参数修改
3. 在生产环境中使用时，建议为 SSE 版本设置 HTTPS 和适当的认证

---

## 🔄 故障排除

如遇问题，请检查：
1. API 密钥和配置文件名是否正确设置
2. 网络连接是否正常
3. 客户端是否正确配置 MCP 连接