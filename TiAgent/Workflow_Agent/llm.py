import os
# 关键修改：从 typing 导入 List, Union, Optional
from typing import TYPE_CHECKING, Literal, Optional, Union, List 

from langchain_core.language_models.chat_models import BaseChatModel

# 导入必要的 LangChain 组件
try:
    from langchain_openai import ChatOpenAI
except ImportError:
    # 强制要求安装 langchain-openai，因为您的自定义服务兼容 OpenAI 接口
    raise ImportError(  
        "langchain-openai package is required for custom OpenAI-compatible models. Install with: pip install langchain-openai"
    )

# 定义您的固定配置
CUSTOM_MODEL = "gpt-4o"
CUSTOM_BASE_URL = "https://api.bianxie.ai/v1"
# ⚠️ 用户提供的配置，覆盖环境变量，用于知识块生成和向量化
BIANXIE_AI_API_KEY = 'sk-GBBQQWHSKHU76HFS5tsHmmffzbQi1dnLy5VdnPU6Kp9gtm3n'


SourceType = Literal["Custom"]


def get_llm(
    # 使用 Union[Type, None] 或 Optional[Type] 格式
    model: Union[str, None] = None,
    temperature: Union[float, None] = None,
    # 关键修改：使用 List[str] 而非 list[str]
    stop_sequences: Optional[List[str]] = None, 
    
    source: Union[SourceType, None] = None,
    base_url: Union[str, None] = None,
    api_key: Union[str, None] = None,
    
    config: Optional["BiomniConfig"] = None,
) -> BaseChatModel:
    """
    Get a language model instance configured for the custom 'https://api.bianxie.ai/v1' service
    running the 'gpt-4o' model.

    Args:
        model (str): The model name to use (defaults to 'gpt-4o').
        temperature (float): Temperature setting for generation.
        stop_sequences (list): Sequences that will stop generation.
        api_key (str): The API key for the custom service (REQUIRED).
    """

    # --- 1. 参数设置与默认值 ---
    
    model = model if model else CUSTOM_MODEL
    base_url = base_url if base_url else CUSTOM_BASE_URL
    
    # 检查 API 密钥是否提供
    if not api_key:
        api_key = os.getenv("BIANXIE_AI_API_KEY") 
        if not api_key:
            raise ValueError(
                f"API Key for the custom service (BIANXIE_AI_API_KEY or 'api_key' argument) is required."
            )

    if temperature is None:
        temperature = 0.7
    
    # --- 2. 创建 ChatOpenAI 实例 ---
    
    llm = ChatOpenAI(
        model=model,
        temperature=temperature,
        stop_sequences=stop_sequences,
        base_url=base_url,
        api_key=api_key,
    )
    
    return llm