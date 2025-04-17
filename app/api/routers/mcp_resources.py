from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
from pydantic import BaseModel
import logging
from .mcp_tools import get_mcp_client

# 配置日志
logger = logging.getLogger("mcp_resources")

# 创建路由器
router = APIRouter(prefix="/api/resources", tags=["MCP资源"])

# Pydantic模型
class ResourceListResponse(BaseModel):
    resources: List[Dict[str, Any]]

class ResourceResponse(BaseModel):
    resource: Any
    uri: str

@router.get("/", response_model=ResourceListResponse)
async def list_resources():
    """获取所有可用MCP资源"""
    try:
        client = await get_mcp_client()
        resources = await client.list_resources()
        logger.info(f"获取到的原始资源列表: {resources}")
        
        # 转换资源为适合输出的格式
        resource_list = []
        for resource in resources:
            resource_dict = {
                "uri": resource.uri,
                # 使用日志中发现的 mimeType 属性
                "type": getattr(resource, 'mimeType', 'unknown')
            }
            resource_list.append(resource_dict)
        
        return {"resources": resource_list}
    except Exception as e:
        logger.exception(f"获取资源列表时发生意外错误")
        raise HTTPException(status_code=500, detail=f"获取资源列表失败: {str(e)}")

@router.get("/{resource_path:path}", response_model=ResourceResponse)
async def get_resource(resource_path: str):
    """获取指定的MCP资源"""
    try:
        client = await get_mcp_client()
        
        # 将路径格式化为data://格式
        full_path = f"data://{resource_path}" if not resource_path.startswith("data://") else resource_path
        
        # 获取资源
        resource = await client.read_resource(full_path)
        
        return {"resource": resource, "uri": full_path}
    except Exception as e:
        logger.error(f"获取资源 {resource_path} 时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取资源失败: {str(e)}") 