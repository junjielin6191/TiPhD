import json
from typing import Any, List, Tuple, Optional, Type
from abc import ABC, abstractmethod

# 导入 LangChain 和 Pydantic 组件 (基于其他文件中的使用)
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel

# 尝试从项目结构中导入配置和 LLM 函数
try:
    # 假设这里的导入路径需要根据您的实际结构进行调整
    # 例如：from config import default_config, from llm import get_llm
    # 这里保持原有结构，但需要注意实际运行时路径可能需要调整
    from Workflow_Agent.config import default_config
    from Workflow_Agent.llm import get_llm 
except ImportError:
    # 如果无法导入，则使用最小化的虚拟对象进行回退，以确保代码块可运行
    class DummyConfig:
        llm: str = "claude-sonnet-4-5"
        cheap_llm: str = "claude-haiku-3-5"
        temperature: float = 0.7
    default_config = DummyConfig()

    def get_llm(model: str, temperature: float, **kwargs):
        # ⚠️ 注意：这个 DummyLLM 忽略了 api_key，实际项目中必须确保 get_llm 导入成功
        class DummyLLM:
            def with_structured_output(self, output_class: Type[BaseModel]):
                return self
            def invoke(self, input: Any):
                class DummyResponse:
                    content = "Mock LLM Response"
                    def dict(self):
                        return {"result": "Mock Structured Output"}
                return DummyResponse()
        return DummyLLM()


class BaseAgent(ABC):
    """
    所有 TiAgent Agent 的抽象基类。
    它定义了 Agent 的核心接口：初始化 LLM、配置 Agent 行为、以及执行主要任务 ('go')。
    """

    def __init__(
        self,
        llm: Optional[str] = None,
        cheap_llm: Optional[str] = None,
        tools: Optional[List[Any]] = None,
        temperature: Optional[float] = None,
        config: Optional[Any] = None,
        # 🔑 关键修改：新增 api_key 参数，用于自定义服务
        api_key: Optional[str] = None, 
    ):
        """
        初始化 Agent。

        Args:
            llm (str, optional): 用于主要推理任务的 LLM 模型名称。
            cheap_llm (str, optional): 用于次要/格式化任务的廉价 LLM 模型名称。
            tools (list, optional): Agent 可使用的工具列表。
            temperature (float, optional): LLM 的温度参数。
            config (Any, optional): 全局配置对象 (通常是 BiomniConfig)。
            api_key (str, optional): 用于自定义 OpenAI 兼容服务的 API Key。
        """
        # 1. 加载配置
        if config is None:
            config = default_config

        # 2. LLM 参数设置
        self.llm_model_name = llm if llm is not None else config.llm
        # 如果未指定 cheap_llm，则默认为 primary llm
        self.cheap_llm_model_name = cheap_llm if cheap_llm is not None else self.llm_model_name 
        self.temperature = temperature if temperature is not None else config.temperature

        # 3. 初始化 LLM 实例
        # Primary LLM instance (用于主要推理，如 ReAct 或 Planner)
        self.llm = get_llm(
            model=self.llm_model_name,
            temperature=self.temperature,
            # 🔑 关键修改：将 api_key 传递给 get_llm
            api_key=api_key 
        )
        
        # Secondary LLM instance (用于简单任务，如 result_formatting 或摘要，可选)
        if self.cheap_llm_model_name != self.llm_model_name:
             self.cheap_llm = get_llm(
                model=self.cheap_llm_model_name,
                temperature=0.0, # 格式化通常需要低温度
                # 🔑 关键修改：将 api_key 传递给 get_llm
                api_key=api_key 
            )
        else:
            self.cheap_llm = self.llm # 廉价模型与主模型相同时，指向同一个实例

        # 4. Agent 状态和上下文
        self.tools = tools
        # log 存储对话历史和中间步骤，格式为 (角色, 内容)
        self.log: List[Tuple[str, str]] = [] 

        # 5. 调用抽象配置方法
        self.configure()

    @abstractmethod
    def configure(self) -> None:
        """
        【抽象方法】配置 Agent 的系统提示 (System Prompt)、内部状态或工具调用逻辑。
        所有继承类必须实现此方法。
        """
        pass

    @abstractmethod
    def go(self, input: Any) -> Tuple[List[Any], Any]:
        """
        【抽象方法】Agent 的主要执行入口。根据输入执行任务并返回结果。
        所有继承类必须实现此方法。

        Args:
            input (Any): 用户的查询或任务输入。

        Returns:
            Tuple[List[Any], Any]: (logs, final_result)
        """
        pass
    
    def result_formatting(self, output_class: Type[BaseModel], task_intention: str) -> dict:
        """
        通用的结果格式化方法。
        使用 LLM 的结构化输出功能，根据指定的 Pydantic 模型，将 Agent 的历史记录 (self.log) 
        格式化为结构化结果。这个模式在 PaperTaskExtractor 和 ReAct Agent 中通用。

        Args:
            output_class (Type[BaseModel]): 目标 Pydantic 模型类（必须继承自 pydantic.BaseModel）。
            task_intention (str): 描述任务意图的文本，用于系统提示，指导 LLM 的格式化。

        Returns:
            dict: 格式化后的结果字典。
        """
        # 使用便宜或主 LLM 进行格式化（这里选用主 LLM 以保持一致性，但可以使用 self.cheap_llm）
        llm_for_formatting = self.llm 

        format_check_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system",
                    (
                        "You are evaluateGPT, tasked with extract and parse the task output based on the history of an agent. "
                        "Review the entire history of messages provided. "
                        "Here is the task output requirement: \n"
                        f"'{task_intention.replace('{', '{{').replace('}', '}}')}'.\n"
                    ),
                ),
                # LangChain 中的特殊占位符，用于插入消息历史列表
                ("placeholder", "{messages}"), 
            ]
        )

        checker_llm = format_check_prompt | llm_for_formatting.with_structured_output(output_class)
        
        try:
            # 传入 Agent 的内部日志作为消息历史
            # ⚠️ 注意：Pydantic V2 应该使用 .model_dump() 或 .model_dump_json()
            # 这里的 .dict() 在某些 LangChain 版本中可能仍然有效，但更安全的是在调用处处理
            result = checker_llm.invoke({"messages": self.log}).dict() 
            return result
        except Exception as e:
            print(f"Error during structured result formatting: {e}")
            # 格式化失败时，返回一个包含错误信息的字典
            return {"error": f"Structured formatting failed: {str(e)}", "log_preview": str(self.log[-5:])}


# 为了保持与项目中其他文件 (如 env_collection.py) 的导入兼容性，
# 使用别名 base_agent 指向 BaseAgent 类
base_agent = BaseAgent