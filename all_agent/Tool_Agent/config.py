class default_config:
    """
    Agent 默认配置类，用于代替缺失的 config.py。
    请根据您的 LLM 服务供应商和模型名称进行修改。
    """
    llm: str = "gpt-4o"  # 假设使用的主模型
    cheap_llm: str = "gpt-4o" # 假设使用的廉价模型
    temperature: float = 0.7