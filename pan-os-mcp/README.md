# PAN-OS MCP Server

基于 Model Context Protocol (MCP) 的 PAN-OS API 服务器，用于与 Palo Alto Networks 防火墙和 Panorama 设备进行交互。

## 功能特点

- 支持通过 XML API 与 PAN-OS 设备进行交互
- 提供丰富的工具集，覆盖 PAN-OS 的主要功能
- 支持同步和异步操作
- 支持 API 密钥和用户名/密码认证
- 符合 Model Context Protocol 规范

## 支持的操作

- 系统信息查询
- 配置管理（获取、修改、提交）
- 操作命令执行
- 安全策略和 NAT 规则管理
- 日志和报告获取
- User-ID 映射更新
- 导入/导出功能

## 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/pan-os-mcp.git
cd pan-os-mcp

# 安装依赖
pip install -r requirements.txt
```

## 配置

在 `config/devices.json` 中配置您的设备信息：

```json
{
  "devices": [
    {
      "name": "firewall-1",
      "ip": "10.29.9.3",
      "auth_method": "api_key",
      "api_key": "YOUR_API_KEY"
    }
  ],
  "default_device": "firewall-1"
}
```

## 使用方法

```bash
# 启动 MCP 服务器
python -m src.pan_os_mcp

# 或者使用提供的脚本
./run_server.sh
```

注意：MCP 服务器日志会输出到标准错误流（stderr），不会创建日志文件。

## MCP 工具

服务器提供以下 MCP 工具：

1. `get_system_info` - 获取系统基本信息
2. `op_command` - 执行操作命令
3. `config_action` - 执行配置操作
4. `commit_config` - 提交配置更改
5. `commit_all_shared_policy` - 提交 Panorama 共享策略
6. `get_security_rules` - 获取安全策略规则
7. `get_nat_rules` - 获取 NAT 规则
8. `get_interfaces` - 获取接口信息
9. `get_routes` - 获取路由表
10. `get_logs` - 获取各类日志
11. `get_reports` - 获取报告
12. `check_job_status` - 检查异步作业状态
13. `export_data` - 导出数据
14. `import_data` - 导入数据
15. `update_user_id` - 更新 User-ID 映射

## 开发

```bash
# 运行测试
pytest

# 代码格式化
black src tests
isort src tests
```

## 许可证

MIT
