from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
from .routers.mcp_tools import router as tools_router
from .routers.mcp_resources import router as resources_router
from .routers.agent import router as agent_router
from contextlib import asynccontextmanager

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("api")

# 定义生命周期管理
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 应用启动时的操作
    logger.info("API服务器启动")
    
    yield  # 应用运行期间
    
    # 应用关闭时的操作
    logger.info("API服务器关闭")
    
    # 清理任何全局资源
    from .routers.mcp_tools import mcp_client
    if mcp_client is not None:
        try:
            await mcp_client.__aexit__(None, None, None)
            logger.info("MCP客户端连接已关闭")
        except Exception as e:
            logger.error(f"关闭MCP客户端连接时出错: {str(e)}")

# 创建FastAPI应用
app = FastAPI(
    title="FastMCP API",
    description="用于与FastMCP服务交互的API",
    version="1.0.0",
    lifespan=lifespan
)

# 启用CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 在生产环境中应该限制为特定域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 包含路由器
app.include_router(tools_router)
app.include_router(resources_router)
app.include_router(agent_router)

# 健康检查端点
@app.get("/health")
async def health_check():
    """API服务器健康检查"""
    return {
        "status": "healthy",
        "version": "1.0.0"
    } 