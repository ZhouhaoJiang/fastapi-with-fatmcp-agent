from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from fastmcp import Client
import logging
import os
from ...llm.openai import OpenAILLM

# 配置日志
logger = logging.getLogger("mcp_tools")

# 创建路由器
router = APIRouter(prefix="/api/tools", tags=["MCP工具"])

# Pydantic模型
class ToolRequest(BaseModel):
    params: Dict[str, Any]
    use_llm: bool = False
    system_message: Optional[str] = None

class ToolListResponse(BaseModel):
    tools: List[Dict[str, Any]]

class ToolResponse(BaseModel):
    result: Any
    llm_response: Optional[str] = None

# 全局MCP客户端
mcp_client = None

# 获取项目根目录的绝对路径
# 客户端连接异常处理
async def get_mcp_client():
    """获取MCP客户端，如未连接则创建连接"""
    global mcp_client
    
    if mcp_client is None:
        mcp_server_url = "http://localhost:8001/sse" # 确保端口与单独运行的MCP服务器匹配
        logger.info(f"创建MCP客户端，连接到 SSE 服务器: {mcp_server_url}")
        # 恢复为连接 SSE 端点
        mcp_client = Client(transport=mcp_server_url)
        try:
            await mcp_client.__aenter__() # 异步进入
            logger.info("已创建并连接到MCP SSE服务器")
            # 可以在这里加一个快速的 list_tools 调用来验证连接
            await mcp_client.list_tools() 
            logger.info("MCP SSE服务器连接验证成功")
        except Exception as e:
            logger.exception(f"连接到MCP SSE服务器 {mcp_server_url} 时出错")
            mcp_client = None # 连接失败，重置客户端
            raise HTTPException(status_code=503, detail=f"无法连接到MCP SSE服务器: {e}")
    
    # 检查现有连接是否仍然有效
    if mcp_client:
        try:
            if not mcp_client.is_connected(): 
                logger.warning("MCP SSE 连接已断开，尝试重新连接...")
                await mcp_client.__aexit__(None, None, None) # 先清理旧连接
                mcp_client = Client(transport=mcp_server_url) 
                await mcp_client.__aenter__()
                logger.info("成功重新连接到MCP SSE服务器")
        except Exception as e:
            logger.exception("检查或重新连接MCP SSE服务器时出错")
            mcp_client = None # 连接失败，重置客户端
            raise HTTPException(status_code=503, detail=f"MCP SSE服务器连接丢失: {e}")
            
    if mcp_client is None:
         raise HTTPException(status_code=503, detail="无法获取有效的MCP客户端连接")

    return mcp_client

@router.get("/", response_model=ToolListResponse)
async def list_tools():
    """获取所有可用MCP工具"""
    try:
        client = await get_mcp_client()
        tools = await client.list_tools()
        logger.info(f"获取到的原始工具列表: {tools}")
        
        # 转换工具为适合输出的格式
        tool_list = []
        for tool in tools:
            logger.info(f"处理工具: {tool.name}, 类型: {type(tool)}")
            tool_dict = {
                "name": tool.name,
                "description": tool.description,
                "parameters": []
            }
            # 从 inputSchema 解析参数信息
            input_schema = getattr(tool, "inputSchema", None)
            logger.info(f"工具 {tool.name} 的 inputSchema: {input_schema}, 类型: {type(input_schema)}")
            
            if input_schema and isinstance(input_schema, dict) and "properties" in input_schema:
                properties = input_schema.get("properties", {})
                required_params = input_schema.get("required", [])
                
                for param_name, param_details in properties.items():
                    logger.info(f"  处理参数: {param_name}, 详情: {param_details}")
                    param_info = {
                        "name": param_name,
                        "type": param_details.get("type", "any"),
                        # 使用 title 作为描述，如果 description 存在则优先使用
                        "description": param_details.get("description", param_details.get("title", "")),
                        "required": param_name in required_params,
                        "default": param_details.get("default", None)
                    }
                    logger.info(f"  提取的参数信息: {param_info}")
                    tool_dict["parameters"].append(param_info)
            
            tool_list.append(tool_dict)
        return {"tools": tool_list}
    except Exception as e:
        logger.exception(f"获取工具列表时发生意外错误")
        raise HTTPException(status_code=500, detail=f"获取工具列表失败: {str(e)}")

@router.post("/{tool_name}", response_model=ToolResponse)
async def call_tool(tool_name: str, request: ToolRequest):
    """调用指定的MCP工具，可选择使用LLM"""
    try:
        client = await get_mcp_client()
        
        # --- 添加日志：检查传入的参数 --- 
        logger.info(f"准备调用工具: {tool_name}")
        logger.info(f"从请求接收到的参数 (request.params): {request.params}, 类型: {type(request.params)}")
        # ----------------------------------
        
        # 直接调用工具
        result = await client.call_tool(tool_name, request.params)
        
        # 如果请求中包含使用LLM标志，则使用LLM进行结果处理
        llm_response = None
        if request.use_llm:
            try:
                # 获取工具信息，用于LLM提示 (添加await)
                tools = await client.list_tools()
                tool_info = next((t for t in tools if t.name == tool_name), None)
                
                if tool_info:
                    # 创建LLM提示
                    prompt = f"""
                    您已调用了工具 '{tool_name}'。
                    工具描述: {tool_info.description if hasattr(tool_info, 'description') else '无描述'}
                    
                    调用参数: {request.params}
                    
                    调用结果: {result}
                    
                    请解释这个结果，并提供任何相关的分析或建议。
                    """
                    
                    # 初始化OpenAI LLM并生成响应
                    llm = OpenAILLM()
                    llm_response = await llm.generate(
                        prompt=prompt.strip(),
                        system_message=request.system_message,
                        temperature=0.7
                    )
            except Exception as llm_err:
                logger.error(f"使用LLM处理结果时出错: {str(llm_err)}")
                llm_response = f"LLM处理失败: {str(llm_err)}"
        
        return {"result": result, "llm_response": llm_response}
    except Exception as e:
        # --- 修改日志：更详细地记录工具调用错误 --- 
        logger.exception(f"调用工具 {tool_name} 时发生错误 (参数: {request.params})") 
        # -----------------------------------------
        raise HTTPException(status_code=500, detail=f"工具调用失败: {str(e)}")

@router.post("/llm/process")
async def process_with_llm(tools_list: List[Dict[str, Any]], prompt: str, system_message: Optional[str] = None):
    """使用工具列表和LLM处理请求"""
    try:
        llm = OpenAILLM()
        response = await llm.generate_with_tools(
            prompt=prompt,
            tools=tools_list,
            system_message=system_message
        )
        return response
    except Exception as e:
        logger.error(f"LLM处理请求时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"LLM处理失败: {str(e)}")

@router.get("/health")
async def health_check():
    """检查MCP客户端连接状态"""
    global mcp_client
    
    if mcp_client is None:
        return {"status": "未连接", "connected": False}
    
    try:
        is_connected = await mcp_client.is_connected()
        return {"status": "已连接" if is_connected else "连接已断开", "connected": is_connected}
    except Exception as e:
        logger.error(f"检查连接状态时出错: {str(e)}")
        return {"status": f"检查连接状态时出错: {str(e)}", "connected": False} 