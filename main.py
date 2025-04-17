import uvicorn
import argparse
import logging
import sys
import os
import asyncio

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("main")

def run_api_server(host: str = "0.0.0.0", port: int = 8080, reload: bool = False):
    """运行FastAPI服务器"""
    logger.info(f"启动API服务器 - 地址: {host}, 端口: {port}")
    uvicorn.run("app.api:app", host=host, port=port, reload=reload)

async def run_mcp_server(transport: str = "sse", host: str = "127.0.0.1", port: int = 8001):
    """直接运行MCP服务器 (异步)"""
    logger.info(f"启动MCP服务器 (模式: {transport}, 端口: {port})")
    # 导入并运行MCP服务器
    from app.mcp_server.simple import SimpleMCPServer
    server = SimpleMCPServer()
    await server.run(transport=transport, host=host, port=port)

def main():
    """解析命令行参数并运行相应的服务器"""
    parser = argparse.ArgumentParser(description="FastMCP集成应用")
    parser.add_argument("--mode", type=str, default="api", choices=["api", "mcp"], 
                        help="运行模式: api (API服务器), mcp (MCP服务器)")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="API服务器主机地址")
    parser.add_argument("--port", type=int, default=8080, help="API服务器端口")
    parser.add_argument("--mcp-host", type=str, default="127.0.0.1", help="MCP服务器主机地址 (仅mcp模式)")
    parser.add_argument("--mcp-port", type=int, default=8001, help="MCP服务器端口 (仅mcp模式)")
    parser.add_argument("--mcp-transport", type=str, default="sse", choices=["sse", "stdio"], help="MCP服务器传输模式 (仅mcp模式)")
    parser.add_argument("--reload", action="store_true", help="是否启用热重载 (仅对API服务器有效)")
    
    args = parser.parse_args()
    
    # 根据模式运行相应的服务器
    if args.mode == "api":
        run_api_server(args.host, args.port, args.reload)
    elif args.mode == "mcp":
        try:
            asyncio.run(run_mcp_server(transport=args.mcp_transport, host=args.mcp_host, port=args.mcp_port))
        except KeyboardInterrupt:
            logger.info("MCP服务器已停止")
    else:
        logger.error(f"不支持的模式: {args.mode}")
        sys.exit(1)

if __name__ == "__main__":
    main() 