from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
import logging

from ...llm.openai import OpenAILLM
from .mcp_tools import get_mcp_client

# 配置日志
logger = logging.getLogger("agent")

# 创建路由器
router = APIRouter(prefix="/api/agent", tags=["Agent模式"])

# Pydantic模型
class AgentRequest(BaseModel):
    prompt: str
    system_message: Optional[str] = None
    max_iterations: int = 3  # 限制工具调用循环次数，防止无限循环

class AgentResponse(BaseModel):
    final_response: str
    tool_calls_executed: List[Dict[str, Any]] = [] # 记录实际执行的工具调用
    iterations: int

@router.post("/process", response_model=AgentResponse)
async def agent_process(request: AgentRequest):
    """使用Agent模式处理用户请求，LLM自主选择并调用工具"""
    
    llm = OpenAILLM() # 初始化LLM
    mcp_client = await get_mcp_client() # 获取MCP客户端
    
    # 1. 获取可用工具列表并格式化
    try:
        available_tools_raw = await mcp_client.list_tools()
        # 需要将原始工具列表转换为字典格式，以便传递给LLM
        available_tools_dict = []
        for tool in available_tools_raw:
            tool_dict = {
                "name": tool.name,
                "description": tool.description,
                "parameters": []
            }
            input_schema = getattr(tool, "inputSchema", None)
            if input_schema and isinstance(input_schema, dict) and "properties" in input_schema:
                properties = input_schema.get("properties", {})
                required_params = input_schema.get("required", [])
                for param_name, param_details in properties.items():
                    param_info = {
                        "name": param_name,
                        "type": param_details.get("type", "any"),
                        "description": param_details.get("description", param_details.get("title", "")),
                        "required": param_name in required_params,
                        "default": param_details.get("default", None)
                    }
                    tool_dict["parameters"].append(param_info)
            available_tools_dict.append(tool_dict)
        
        formatted_tools_for_llm = llm.format_tools(available_tools_dict)
        logger.info(f"传递给LLM的工具: {formatted_tools_for_llm}")
    except Exception as e:
        logger.error(f"获取或格式化工具时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取工具失败: {str(e)}")

    # 初始化消息历史
    messages = []
    if request.system_message:
        messages.append({"role": "system", "content": request.system_message})
    messages.append({"role": "user", "content": request.prompt})
    
    tool_calls_executed = []
    iterations = 0

    # 2. Agent循环：LLM思考 -> 工具调用 -> LLM处理结果
    while iterations < request.max_iterations:
        iterations += 1
        logger.info(f"Agent 迭代 {iterations} - 当前消息: {messages}")
        
        try:
            # 3. 调用LLM（可能请求工具调用）
            llm_response = await llm.client.chat.completions.create(
                model=llm.model_name,
                messages=messages,
                tools=formatted_tools_for_llm,
                tool_choice="auto" # 让LLM自主决定是否调用工具
            )
            
            response_message = llm_response.choices[0].message
            messages.append(response_message) # 将LLM的回复添加到历史记录
            
            # 4. 检查是否有工具调用请求
            if response_message.tool_calls:
                logger.info(f"LLM请求调用工具: {response_message.tool_calls}")
                # 5. 执行工具调用
                for tool_call in response_message.tool_calls:
                    function_name = tool_call.function.name
                    try:
                        # 解析参数
                        function_args = json.loads(tool_call.function.arguments)
                        logger.info(f"调用MCP工具: {function_name}，参数: {function_args}")
                        
                        # 调用实际的MCP工具
                        tool_result = await mcp_client.call_tool(function_name, function_args)
                        logger.info(f"工具 {function_name} 返回结果: {tool_result}")
                        
                        # 记录执行的调用
                        tool_calls_executed.append({"tool_name": function_name, "arguments": function_args, "result": tool_result})
                        
                        # --- 修复：将工具结果转换为JSON可序列化格式 --- 
                        serializable_result = str(tool_result) # 通用方法，转换为字符串
                        # 也可以根据需要做更复杂的转换，例如：
                        # if isinstance(tool_result, list) and len(tool_result) > 0 and hasattr(tool_result[0], 'text'):
                        #     serializable_result = tool_result[0].text
                        # else:
                        #     serializable_result = str(tool_result)
                        logger.info(f"序列化后的结果: {serializable_result}")
                        # ---------------------------------------------
                        
                        # 6. 将工具结果添加到消息历史，以便LLM处理
                        messages.append(
                            {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                # 使用转换后的结果
                                "content": json.dumps(serializable_result), 
                            }
                        )
                        
                    except json.JSONDecodeError as json_err:
                        logger.error(f"解析工具参数失败 ({function_name}): {json_err}")
                        messages.append(
                            {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": json.dumps({"error": "解析参数失败", "details": str(json_err)}),
                            }
                        )
                    except Exception as tool_err:
                        logger.error(f"调用工具 {function_name} 时出错: {tool_err}")
                        messages.append(
                            {
                                "tool_call_id": tool_call.id,
                                "role": "tool",
                                "name": function_name,
                                "content": json.dumps({"error": f"工具执行失败", "details": str(tool_err)}),
                            }
                        )
            else:
                # 7. 如果没有工具调用，表示LLM已生成最终回复
                logger.info("LLM未请求工具调用，生成最终回复")
                final_response = response_message.content
                return AgentResponse(
                    final_response=final_response,
                    tool_calls_executed=tool_calls_executed,
                    iterations=iterations
                )

        except Exception as llm_err:
            logger.exception("Agent处理过程中调用LLM时出错")
            raise HTTPException(status_code=500, detail=f"LLM处理失败: {str(llm_err)}")

    # 如果达到最大迭代次数仍未获得最终回复
    logger.warning("达到最大迭代次数")
    # 尝试获取最后一条assistant消息作为回复
    final_response = "Agent达到最大迭代次数，未能完全处理请求。" 
    for msg in reversed(messages):
        if msg.role == "assistant" and msg.content:
            final_response = msg.content
            break
            
    return AgentResponse(
        final_response=final_response,
        tool_calls_executed=tool_calls_executed,
        iterations=iterations
    ) 