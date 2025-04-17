from datetime import datetime
from app.mcp_server.base import BaseMCPServer


class SimpleMCPServer(BaseMCPServer):
    """简单MCP服务器示例，提供基本工具和资源"""
    
    def __init__(self):
        super().__init__(name="简单示例 🚀")
    
    def _register_tools(self):
        """注册工具"""
        
        @self.mcp.tool()
        def add(a: int, b: int) -> int:
            """将两个数字相加"""
            return a + b
        
        @self.mcp.tool()
        def greet(name: str, language: str = "中文") -> str:
            """根据指定语言问候用户"""
            greetings = {
                "中文": f"你好，{name}！",
                "英文": f"Hello, {name}!",
                "日文": f"こんにちは、{name}さん！",
            }
            return greetings.get(language, greetings["中文"])

        @self.mcp.tool()
        def get_time() -> str:
            """获取当前时间"""
            return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        @self.mcp.tool()
        def get_time_zone() -> str:
            """获取当前时区"""
            return datetime.now().strftime("%Z")

        @self.mcp.tool()
        def duck_duck_go(query: str) -> str:
            """使用duckduckgo搜索"""
            return f"使用duckduckgo搜索: {query}"
        
        @self.mcp.tool()
        def get_cat_image() -> str:
            """获取随机图片"""
            return "https://picsum.photos/200"
        
        
    def _register_resources(self):
        """注册资源"""
        
        @self.mcp.resource("data://example/greeting")
        def get_greeting_resource():
            """返回一个问候语资源"""
            return {
                "message": "欢迎使用FastMCP！",
                "version": "2.2.0",
            } 
        
        @self.mcp.resource("data://example/high_temperature_prompt")
        def get_high_temperature_prompt():
            """返回一个高级提示词资源"""
            return "我是高级提示词"
