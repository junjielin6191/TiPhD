class default_config:
    """
    Agent 核心配置类，作为所有模块的单一事实来源。
    """
    # 核心模型：用于规划、路由和语义标准化
    llm: str = "gpt-4" 
    
    # 廉价/快速模型：用于简单的检索任务
    cheap_llm: str = "gpt-4" 
    
    # 检索专用模型配置
    retrieval_model: str = "gpt-4"
    planner_model: str = "gpt-4"
    
    temperature: float = 0.0
    planner_temperature: float = 0.0