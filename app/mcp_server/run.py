from app.mcp_server.simple import SimpleMCPServer

# 创建MCP服务器实例
mcp_server = SimpleMCPServer()

# 获取FastMCP应用实例 (供client连接使用)
mcp = mcp_server.app

# 直接运行此脚本时启动服务器
if __name__ == "__main__":
    # 运行MCP服务器
    mcp_server.run(port=8001, transport="sse") 