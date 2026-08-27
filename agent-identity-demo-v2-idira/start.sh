#!/bin/bash
# 一键启动 3 层架构

echo "🚀 启动 Agent + MCP Identity Demo (分层架构)"
echo "==========================================="

if [ ! -f .env ]; then
    echo "⚠️  .env 文件不存在"
    exit 1
fi

export $(grep -v '^#' .env | xargs)

# Layer 4: Business API
echo ""
echo "🔧 [Layer 4] 启动 Business API (端口 8080)..."
python api_service.py &
API_PID=$!
sleep 3

curl -s http://localhost:8080/health > /dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ Business API 运行中 (自己验证 JWT)"
else
    echo "   ❌ Business API 启动失败"
    exit 1
fi

# Layer 3: MCP Server
echo ""
echo "📡 [Layer 3] 启动 MCP Server (端口 8000)..."
python mcp_server.py &
MCP_PID=$!
sleep 2

curl -s http://localhost:8000/health > /dev/null
if [ $? -eq 0 ]; then
    echo "   ✅ MCP Server 运行中 (客户端验证 + 纯转发)"
else
    echo "   ❌ MCP Server 启动失败"
    kill $API_PID
    exit 1
fi

# Layer 1: Agent Web
echo ""
echo "🤖 [Layer 1] 启动 Agent Web (端口 3000)..."
python agent_backend.py &
AGENT_PID=$!
sleep 2

echo ""
echo "==========================================="
echo "✅ 所有服务已启动！"
echo ""
echo "🌐 访问 http://localhost:3000"
echo ""
echo "📋 分层架构："
echo "   Layer 1 (端口 3000): Agent Web - 用户界面 + Auth0 登录"
echo "   Layer 2 (云端):      Portkey Gateway - 审计 + 身份转发"
echo "   Layer 3 (端口 8000): MCP Server - 客户端验证 + 协议适配"
echo "   Layer 4 (端口 8080): Business API - JWT 验签 + 业务逻辑"
echo ""
echo "按 Ctrl+C 停止"
echo ""

trap "kill $API_PID $MCP_PID $AGENT_PID; exit" INT
wait
