from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("llm")


class BaseLLM(ABC):
    """LLM处理的基类，定义了LLM交互的通用接口"""
    
    def __init__(self, model_name: str):
        self.model_name = model_name
        self.logger = logger
    
    @abstractmethod
    async def generate(self, 
                       prompt: str, 
                       system_message: Optional[str] = None,
                       temperature: float = 0.7, 
                       max_tokens: int = 1000) -> str:
        """生成文本响应"""
        pass
    
    @abstractmethod
    async def generate_with_tools(self, 
                                 prompt: str, 
                                 tools: List[Dict[str, Any]],
                                 system_message: Optional[str] = None,
                                 temperature: float = 0.7) -> Dict[str, Any]:
        """使用工具生成响应"""
        pass
    
    def format_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """格式化工具列表以符合LLM的输入格式"""
        return tools 