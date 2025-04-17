from fastmcp import FastMCP
import asyncio


class BaseMCPServer:
    """MCP服务器基类，可以被继承扩展"""
    
    def __init__(self, name: str = "基础MCP服务器"):
        self.mcp = FastMCP(name)
        self._register_tools()
        self._register_resources()
    
    def _register_tools(self):
        """注册工具，子类应该重写此方法"""
        pass
    
    def _register_resources(self):
        """注册资源，子类应该重写此方法"""
        pass
    
    async def run(self, transport: str = "sse", host: str = "127.0.0.1", port: int = 8001):
        """运行MCP服务器 (异步)"""
        print(f"运行MCP服务器，端口: {port}")
        if transport == "sse":
            await self.mcp.run_sse_async(host=host, port=port)
        elif transport == "stdio":
            # 如果需要支持stdio，可以添加 run_stdio_async
            await self.mcp.run_stdio_async()
        else:
            # 默认或未知传输，可以尝试通用运行或抛出错误
            print(f"警告: 不支持的传输类型 {transport}，尝试默认运行")
            # 注意：如果通用 run 有问题，这里可能仍然失败
            await self.mcp.run_async(transport=transport, host=host, port=port)
    
    @property
    def app(self) -> FastMCP:
        """获取FastMCP应用实例"""
        return self.mcp 