# File: tiagent_master.py
import json
import os
import re
from pathlib import Path
from collections import deque
from openai import OpenAI

# --- 导入子 Agent 核心模块 (名称已更新) ---
# 注意：你的目录结构如果是 Evidence_Agent，请保持导入路径，或重命名文件夹为 Evidence_Agent
from Evidence_Agent.main import (
    load_rag_assets, 
    run_rag_pipeline, 
    translate_answer_to_original,
    API_KEY, 
    API_BASE
)
from Evidence_Agent.orchestrator import ORCHESTRATOR_MODEL

from Workflow_Agent.env_desc import library_content_dict
from Workflow_Agent.know_how.loader import KnowHowLoader
from Workflow_Agent.model.retriever import ToolRetriever
from Workflow_Agent.agent.planner_agent import PlannerAgent
from Workflow_Agent.llm import get_llm

print("📦 正在初始化 TiAgent 全局资源...")
openai_client = OpenAI(api_key=API_KEY, base_url=API_BASE)

# --- 1. 全局记忆管理器 (Sliding Window Memory Management) ---
class GlobalMemoryManager:
    """
    维护全局会话历史的队列数据结构，实现状态机连续性与滑动窗口记忆管理。
    优先保留“高密度实体句”（核心基因、细胞亚型、意图），赋予早期对话时间衰减权重。
    """
    def __init__(self, max_turns=6, max_tokens=4000):
        self.history_queue = deque()
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        # 生物学高密度实体正则（简单模拟，匹配基因、细胞、疾病等大写/特定词根）
        self.entity_pattern = re.compile(r'([A-Z0-9]{3,}|[A-Z][a-z]+-cell|tumor|cancer|CRISPR|Cas9|RNA|seq)', re.IGNORECASE)

    def add_interaction(self, role: str, content: str):
        self.history_queue.append({"role": role, "content": content})
        self._apply_sliding_window()

    def _apply_sliding_window(self):
        """衰减权重与滑动窗口裁剪策略"""
        while len(self.history_queue) > self.max_turns * 2:
            # 移除最早的一轮对话 (User + Assistant)
            old_user = self.history_queue.popleft()
            old_assistant = self.history_queue.popleft()
            
            # 提取早期对话中的高密度实体，作为压缩记忆重新插入队列头部（防止逻辑断裂）
            entities = set(self.entity_pattern.findall(old_user['content'] + " " + old_assistant['content']))
            if entities:
                compressed_memory = f"[Memory Context: User previously discussed {', '.join(entities)}]"
                # 如果头部已经是记忆标签，则合并
                if self.history_queue and self.history_queue[0]['role'] == 'system' and 'Memory Context' in self.history_queue[0]['content']:
                    self.history_queue[0]['content'] += f" | {compressed_memory}"
                else:
                    self.history_queue.appendleft({"role": "system", "content": compressed_memory})

    def get_context(self) -> list:
        return list(self.history_queue)

    def get_context_str(self) -> str:
        return "\n".join([f"{item['role'].capitalize()}: {item['content']}" for item in self.history_queue])


# --- 2. 增强版语言引擎 (Language Engine) ---
def process_query_for_llm(client: OpenAI, query: str, global_history: str) -> dict:
    """
    将模糊查询转化为符合 Biomedical Ontologies 规范的 Standardized English Query。
    处理剧烈的视角切换与上下文补全。
    """
    system_prompt = (
        "You are the TiAgent Language Engine. Your task is to resolve user queries using the Global History state machine.\n"
        "1. Detect the user's original language (e.g., 'zh', 'en').\n"
        "2. Handle sudden perspective shifts (e.g., shifting from marker expression to CRISPR validation).\n"
        "3. Transform the query into a STANDARDIZED ENGLISH QUERY compliant with Biomedical Ontologies (e.g., standardizing gene symbols, cell types, pathways).\n"
        "4. Ensure the output query is completely standalone and incorporates resolved pronouns/entities from the history.\n\n"
        "Output ONLY a raw JSON object with keys: 'original_language' and 'english_query'."
    )
    
    user_prompt = (
        f"### Global History:\n{global_history if global_history else 'None'}\n\n"
        f"### Current User Input:\n{query}\n\n"
        "Generate the structured JSON."
    )

    try:
        response = client.chat.completions.create(
            model=ORCHESTRATOR_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.0
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"⚠️ Language Engine Error: {e}")
        return {"original_language": "zh", "english_query": query}


# --- 3. 意图路由 (Master Orchestrator) ---
def master_orchestrate(client: OpenAI, en_query: str, global_history: str):
    """总路由逻辑：使用更新后的 Agent 名称"""
    system_instruction = """
    You are the Master Orchestrator for TiAgent.
    Decide which sub-systems to call based on the user's standardized query and history intent:
    1. [Evidence Agent]: Seeking biological facts, marker expressions, literature evidence, or spatial co-localization.
    2. [Workflow Agent]: Seeking computational analysis steps, code, dry/wet-lab experimental designs (e.g., CRISPR protocols, scRNA-seq pipelines).
    
    Return JSON: {"route": ["Evidence Agent", "Workflow Agent"]}
    """
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"Query: {en_query}\nHistory:\n{global_history}"}
    ]
    response = client.chat.completions.create(
        model=ORCHESTRATOR_MODEL,
        messages=messages,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# --- (全局资源加载与 run_tiagent 函数，根据你原有的逻辑进行小幅调整，将 chat_history 替换为 global_memory) ---
# ... (此处省略与原有资源加载重复的代码，重点关注流程逻辑)

global_memory = GlobalMemoryManager()

def run_tiagent(user_input: str):
    history_str = global_memory.get_context_str()
    
    # 1. 语言引擎处理
    lang_info = process_query_for_llm(openai_client, user_input, history_str)
    en_query = lang_info['english_query']
    orig_lang = lang_info['original_language']
    
    # 2. 路由决策
    routes = master_orchestrate(openai_client, en_query, history_str)
    print(f"🚦 路由决策: {routes['route']}")
    
    responses = []
    
    # 3. 子智能体调度 (更新名称)
    if "Evidence Agent" in routes["route"] or "Evidence_Agent" in routes["route"]:
        print("🧬 [Evidence Agent] 正在检索循证文献与多模态数据...")
        # 注意: 需同步修改 run_rag_pipeline 内部的提示词
        paper_answer, _ = run_rag_pipeline(openai_client, en_query, index, id_map, rag_data, global_memory.get_context())
        responses.append(f"### Evidence Agent (Literature & Data):\n{paper_answer}")

    if "Workflow Agent" in routes["route"] or "Workflow_Agent" in routes["route"]:
        print("⚙️ [Workflow Agent] 正在构建实验与计算分析工作流...")
        retrieved = retriever.prompt_based_retrieval(en_query, all_tool_resources, retriever_llm)
        tool_answer = planner.go(en_query, retrieved, history_str)
        responses.append(f"### Workflow Agent (Protocols & Pipelines):\n{tool_answer}")

    # 4. 全局翻译与记忆更新
    combined_answer = "\n\n---\n\n".join(responses)
    final_translated = translate_answer_to_original(openai_client, combined_answer, orig_lang)
    
    global_memory.add_interaction(user_input, combined_answer)
    return final_translated