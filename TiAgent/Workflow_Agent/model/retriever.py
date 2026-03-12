import contextlib
from typing import Any, Dict, List, Union
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.language_models.chat_models import BaseChatModel # 引入通用模型类型

# 假设导入路径与您的项目结构一致
# 确保可以导入我们新增的 SelectedResources 模型
try:
    from Workflow_Agent.model.structured_output import SelectedResources
except ImportError:
    # 如果路径导入失败，使用一个 Dummy 类来保证代码块可运行
    class SelectedResources:
        def __init__(self):
            self.tools = []
            self.data_lake = []
            self.libraries = []
            self.know_how = []
        # 兼容 Pydantic V2 的方法
        def model_dump(self) -> Dict[str, List[int]]:
            return {"tools": self.tools, "data_lake": self.data_lake, "libraries": self.libraries, "know_how": self.know_how}
    
    # 针对 BaseChatModel 的 Dummy
    class DummyChatModel:
        def with_structured_output(self, output_class):
            return self
        def invoke(self, input):
            return SelectedResources()
    BaseChatModel = DummyChatModel


class ToolRetriever:
    def __init__(self):
        # 优化后的专业英文提示词 (包含 user_query 变量)
        self.retrieval_prompt = ChatPromptTemplate.from_messages(
            [
                (
                    "system", 
                    "You are a Bioinformatics Resource Specialist.\n"
                    "### Critical Instruction:\n"
                    "1. **Prioritize SOTA**: If the user query implies phenotype association, drug response, or spatial niche analysis, you MUST select specialized tools (e.g., TiRank, SpaPheno, BeyondCell) over generic ones.\n" # 👈 强制检索 SOTA
                    "2. **Coverage**: Select tools that cover Analysis AND Validation phases."
                ),
                (
                    "human", 
                    "USER QUERY: {user_query}\n\nAVAILABLE RESOURCES:\n{formatted_query_and_resources}"
                ),
            ]
        )

    def _format_resources_list(self, resource_list: List[Any]) -> str:
        def get_desc(item):
            return item['description'] if isinstance(item, dict) and 'description' in item else str(item)
        return "\n".join(f"[{i}]: {get_desc(desc)}" for i, desc in enumerate(resource_list))
    
    def prompt_based_retrieval(self, query: str, resources: Dict[str, List[Any]], llm: BaseChatModel) -> Dict[str, List[Any]]:
        if llm is None:
            raise ValueError("LLM 实例必须提供给 ToolRetriever。")
            
        formatted_query_and_resources = f"""
AVAILABLE TOOLS (Total {len(resources.get('tools', []))} items):
{self._format_resources_list(resources.get('tools', []))}

AVAILABLE DATA_LAKE ITEMS (Total {len(resources.get('data_lake', []))} items):
{self._format_resources_list(resources.get('data_lake', []))}

AVAILABLE KNOW-HOW DOCUMENTS (Total {len(resources.get('know_how', []))} items):
{self._format_resources_list(resources.get('know_how', []))}
"""
        
        retriever_chain = self.retrieval_prompt | llm.with_structured_output(SelectedResources)
        
        try:
            # 【修复关键点】：在这里传入 user_query
            structured_indices = retriever_chain.invoke(
                {
                    "user_query": query, 
                    "formatted_query_and_resources": formatted_query_and_resources
                }
            )
            selected_indices = structured_indices.model_dump()
            # 打印推理过程，方便你调试
            print(f"   - [Retrieval Reasoning]: {selected_indices.get('reasoning')}")
            
        except Exception as e:
            print(f"结构化检索失败: {e}")
            selected_indices = {"tools": [], "data_lake": [], "libraries": [], "know_how": []}

        final_resources = {}
        for key in ["tools", "data_lake", "libraries", "know_how"]:
            original_list = resources.get(key, [])
            retrieved_indices = selected_indices.get(key, [])
            valid_indices = [idx for idx in retrieved_indices if isinstance(idx, int) and 0 <= idx < len(original_list)]
            final_resources[key] = [original_list[i] for i in valid_indices]

        return final_resources