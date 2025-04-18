from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
import logging
import re # Import regex

from ...llm.openai import OpenAILLM
from .mcp_tools import get_mcp_client

# 配置日志
logger = logging.getLogger("agent")

# 创建路由器
router = APIRouter(prefix="/api/agent", tags=["Agent模式"])

# --- Constants for Resource Reading --- 
RESOURCE_READ_PREFIX = "READ_RESOURCE:"
# Regex to find the instruction and capture the URI
RESOURCE_READ_PATTERN = re.compile(rf"^{RESOURCE_READ_PREFIX}\s*(\S+)", re.MULTILINE)
# ------------------------------------

# Pydantic模型
class AgentRequest(BaseModel):
    prompt: str
    system_message: Optional[str] = None
    max_iterations: int = 5 # Increase max iterations slightly for resource reads

class AgentResponse(BaseModel):
    final_response: str
    tool_calls_executed: List[Dict[str, Any]] = [] # 记录实际执行的工具调用
    resources_read: List[Dict[str, Any]] = [] # 记录读取的资源
    iterations: int

@router.post("/process", response_model=AgentResponse)
async def agent_process(request: AgentRequest):
    """使用Agent模式处理用户请求，LLM自主选择、调用工具或读取资源"""
    
    llm = OpenAILLM() # 初始化LLM
    mcp_client = await get_mcp_client() # 获取MCP客户端
    
    # 1. 获取可用工具和资源列表
    try:
        # Tools
        available_tools_raw = await mcp_client.list_tools()
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
        
        # Resources
        available_resources_raw = await mcp_client.list_resources()
        available_resources_info = [ # Create a simple list of resource URIs and types
            {"uri": res.uri, "type": getattr(res, 'mimeType', 'unknown')}
            for res in available_resources_raw
        ]
        logger.info(f"可用的资源: {available_resources_info}")
        
    except Exception as e:
        logger.error(f"获取或格式化工具/资源时出错: {str(e)}")
        raise HTTPException(status_code=500, detail=f"获取工具/资源失败: {str(e)}")

    # 2. 构建初始消息，包含资源信息和读取指令
    initial_system_message = request.system_message or "You are a helpful assistant."
    # Append resource info and instructions to the system message
    resource_prompt_part = "\n\nAvailable Resources (you can request to read them using 'READ_RESOURCE: <uri>'):\n" + "\n".join([f"- {res['uri']} ({res['type']})" for res in available_resources_info])
    instruction_prompt_part = f"\n\nIf you need information from a resource to answer the user, output *only* '{RESOURCE_READ_PREFIX} <uri>' on a line by itself. Otherwise, respond to the user or call a tool if necessary."
    
    enhanced_system_message = initial_system_message + resource_prompt_part + instruction_prompt_part

    messages = [
        {"role": "system", "content": enhanced_system_message},
        {"role": "user", "content": request.prompt}
    ]
    
    tool_calls_executed = []
    resources_read = []
    iterations = 0

    # 3. Agent循环
    while iterations < request.max_iterations:
        iterations += 1
        logger.info(f"Agent 迭代 {iterations} - 当前消息: {messages}")
        
        try:
            # 4. 调用LLM
            llm_response = await llm.client.chat.completions.create(
                model=llm.model_name,
                messages=messages,
                tools=formatted_tools_for_llm,
                tool_choice="auto"
            )
            
            response_message = llm_response.choices[0].message
            response_content = response_message.content or "" # Ensure content is not None
            messages.append(response_message) # 添加LLM回复 (可能是文本、工具调用或资源读取请求)
            
            # 5. 检查是否请求读取资源
            resource_match = RESOURCE_READ_PATTERN.search(response_content)
            if resource_match:
                resource_uri = resource_match.group(1).strip()
                logger.info(f"LLM请求读取资源: {resource_uri}")
                try:
                    # 6. 读取资源
                    resource_content = await mcp_client.get_resource(resource_uri)
                    logger.info(f"资源 {resource_uri} 内容: {resource_content}")
                    resources_read.append({"uri": resource_uri, "content": resource_content})

                    # --- 修复：将资源结果作为用户消息添加到历史 --- 
                    resource_feedback_content = f"Content of resource '{resource_uri}':\n\n{str(resource_content)}"
                    messages.append(
                        {
                            "role": "user",
                            "content": resource_feedback_content,
                        }
                    )
                    # -------------------------------------------------

                    # 继续循环，让LLM处理资源内容
                    continue

                except Exception as res_err:
                    logger.error(f"读取资源 {resource_uri} 时出错: {res_err}")
                    # --- 修复：将错误信息作为用户消息添加 --- 
                    error_feedback_content = f"Attempted to read resource '{resource_uri}' but failed: {str(res_err)}"
                    messages.append(
                        {
                            "role": "user",
                            "content": error_feedback_content,
                        }
                    )
                    # -----------------------------------------
                    # 继续循环，让LLM知道读取失败
                    continue
            
            # 8. 检查是否有实际的工具调用请求
            elif response_message.tool_calls:
                logger.info(f"LLM请求调用工具: {response_message.tool_calls}")
                # 9. 执行工具调用
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
                        
                        # 10. 将工具结果添加到消息历史，以便LLM处理
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
                # 处理完工具调用后，继续循环让LLM处理结果
                continue
            
            else:
                # 11. 如果既没读资源也没调用工具，返回最终回复
                logger.info("LLM未请求资源或工具，生成最终回复")
                final_response = response_content
                return AgentResponse(
                    final_response=final_response,
                    tool_calls_executed=tool_calls_executed,
                    resources_read=resources_read,
                    iterations=iterations
                )

        except Exception as llm_err:
            logger.exception("Agent处理过程中调用LLM时出错")
            raise HTTPException(status_code=500, detail=f"LLM处理失败: {str(llm_err)}")

    # 12. 达到最大迭代次数
    logger.warning("达到最大迭代次数")
    final_response = "Agent达到最大迭代次数，未能完全处理请求。"
    # 尝试获取最后一条assistant消息作为回复
    for msg in reversed(messages):
        if msg.role == "assistant" and msg.content:
            final_response = msg.content
            break
            
    return AgentResponse(
        final_response=final_response,
        tool_calls_executed=tool_calls_executed,
        resources_read=resources_read,
        iterations=iterations
    ) 