from .base import BaseLLM
from typing import Dict, List, Any, Optional
import os
# 导入正确的异步客户端
from openai import AsyncOpenAI


class OpenAILLM(BaseLLM):
    """OpenAI API实现的LLM处理类，使用OpenAI官方库"""

    def __init__(
        self, model_name: str = "gpt-4o", api_key: Optional[str] = None
    ):
        super().__init__(model_name)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            self.logger.warning("未设置OpenAI API密钥，请通过环境变量设置或直接传入")

        # 初始化正确的异步OpenAI客户端
        self.client = AsyncOpenAI(api_key=self.api_key)

    async def generate(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """生成文本响应"""
        # 检查API Key是否存在
        if not self.api_key:
            self.logger.error("OpenAI API key is missing. Cannot generate.")
            return "生成失败: Missing API key"

        messages = []

        if system_message:
            messages.append({"role": "system", "content": system_message})

        messages.append({"role": "user", "content": prompt})

        try:
            # 现在可以正确 await 异步方法
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            return response.choices[0].message.content

        except Exception as e:
            self.logger.error(f"调用OpenAI API时出错: {str(e)}")
            return f"生成失败: {str(e)}"

    async def generate_with_tools(
        self,
        prompt: str,
        tools: List[Dict[str, Any]],
        system_message: Optional[str] = None,
        temperature: float = 0.7,
    ) -> Dict[str, Any]:
        """使用工具生成响应"""
        # 检查API Key是否存在
        if not self.api_key:
            self.logger.error("OpenAI API key is missing. Cannot generate with tools.")
            return {"error": "Missing API key"}

        messages = []

        if system_message:
            messages.append({"role": "system", "content": system_message})

        messages.append({"role": "user", "content": prompt})

        formatted_tools = self.format_tools(tools)

        try:
            # 现在可以正确 await 异步方法
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                tools=formatted_tools,
                temperature=temperature,
            )

            # 转换响应为字典格式
            return {
                "id": response.id,
                "object": response.object,
                "created": response.created,
                "model": response.model,
                "choices": [
                    {
                        "index": choice.index,
                        "message": {
                            "role": choice.message.role,
                            "content": choice.message.content,
                            "tool_calls": [
                                {
                                    "id": tool_call.id,
                                    "type": tool_call.type,
                                    "function": {
                                        "name": tool_call.function.name,
                                        "arguments": tool_call.function.arguments,
                                    },
                                }
                                for tool_call in (choice.message.tool_calls or [])
                            ]
                            if choice.message.tool_calls
                            else [],
                        },
                        "finish_reason": choice.finish_reason,
                    }
                    for choice in response.choices
                ],
            }

        except Exception as e:
            self.logger.error(f"调用OpenAI API with tools时出错: {str(e)}")
            return {"error": str(e)}

    def format_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """将MCP工具转换为OpenAI工具格式"""
        openai_tools = []

        for tool in tools:
            openai_tool = {
                "type": "function",
                "function": {
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "parameters": {"type": "object", "properties": {}, "required": []},
                },
            }

            # 处理参数
            if "parameters" in tool and isinstance(tool["parameters"], list):
                for param in tool["parameters"]:
                    param_name = param.get("name", "")
                    param_type = param.get("type", "string")
                    param_desc = param.get("description", "")
                    param_required = param.get("required", False)

                    openai_tool["function"]["parameters"]["properties"][param_name] = {
                        "type": param_type,
                        "description": param_desc,
                    }

                    if param_required:
                        openai_tool["function"]["parameters"]["required"].append(
                            param_name
                        )

            openai_tools.append(openai_tool)

        return openai_tools
