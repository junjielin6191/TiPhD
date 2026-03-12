# File: tiagent_master.py
import json
import os
from pathlib import Path
from openai import OpenAI

# --- 1. 导入 Paper_Agent 核心模块 ---
from Paper_Agent.main import (
    load_rag_assets, 
    run_rag_pipeline, 
    process_query_for_llm, 
    translate_answer_to_original,
    API_KEY, 
    API_BASE
)
from Paper_Agent.orchestrator import ORCHESTRATOR_MODEL

# --- 2. 导入 Tool_Agent 核心模块 ---
from Tool_Agent.env_desc import library_content_dict
from Tool_Agent.know_how.loader import KnowHowLoader
from Tool_Agent.model.retriever import ToolRetriever
from Tool_Agent.agent.planner_agent import PlannerAgent
from Tool_Agent.llm import get_llm

# --- 3. 全局资源初始化 (单例模式) ---
print("📦 正在初始化 TiAgent 全局资源...")
openai_client = OpenAI(api_key=API_KEY, base_url=API_BASE)

# A. 加载文献 RAG 资产
index, id_map, rag_data = load_rag_assets()

# B. 初始化 Tool_Agent 组件
base_path = Path("/mnt/data/ljj/Project_TiPhD/TiAgent/all_agent")
loader = KnowHowLoader(know_how_dir=str(base_path / "Tool_Agent" / "know_how"))
know_how_docs = loader.get_all_documents()

retriever = ToolRetriever()
retriever_llm = get_llm(model="gpt-4o", temperature=0.0, api_key=API_KEY)
planner = PlannerAgent(llm="gpt-4o", temperature=0.0, api_key=API_KEY)

def _prepare_all_tool_resources():
    tools = []
    # 原有的分类逻辑存在漏斗效应，这里我们保留 tags 检测仅用于增强描述（可选），
    # 但将所有条目都放入 tools 列表，确保 Retriever 能看到它们。
    
    for name, desc in library_content_dict.items():
        # 1. 过滤掉明显的数据文件
        if name.endswith(('.parquet', '.tsv', '.csv', '.pkl')): 
            continue
        
        # 2. 格式化条目
        formatted_entry = f"【{name}】: {desc}"
        
        # 3. 直接全部加入 tools
        # 不再进行关键词判断，因为 env_desc.py 里本质上都是工具
        tools.append(formatted_entry)

    # 整合结构化实验库
    combined_know_how = [{"id": d['id'], "description": d['description'], "content": d['content']} for d in know_how_docs]
    exp_path = base_path / "Paper_Agent" / "database" / "data" / "json" / "experiment_records.json"
    if exp_path.exists():
        with open(exp_path, 'r', encoding='utf-8') as f:
            for rec in json.load(f):
                combined_know_how.append({
                    "id": f"Protocol: {rec.get('Experimental_Design')}",
                    "description": f"Target: {rec.get('Purpose')}",
                    "content": f"Methodology: {rec.get('Methodology')}\nAnalyses: {rec.get('Key_Analyses')}"
                })
    return {"tools": tools, "libraries": libraries, "know_how": combined_know_how}

all_tool_resources = _prepare_all_tool_resources()

# --- 4. 核心路由与执行逻辑 ---

def master_orchestrate(client, en_query, history):
    """总路由逻辑：判断用户意图"""
    system_instruction = """
    You are the Master Orchestrator for TiAgent.
    Decide which sub-systems to call based on user intent:
    1. [Paper_Agent]: Seeking biological facts, markers, or evidence from literature.
    2. [Tool_Agent]: Seeking computational analysis steps, code, or wet-lab experimental designs.
    
    Return JSON: {"route": ["Paper_Agent", "Tool_Agent"]}
    """
    messages = [
        {"role": "system", "content": system_instruction},
        {"role": "user", "content": f"Query: {en_query}\nHistory: {history}"}
    ]
    response = client.chat.completions.create(
        model=ORCHESTRATOR_MODEL,
        messages=messages,
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

def run_tiagent(user_input, chat_history):
    """TiAgent 主运行流程"""
    
    # 1. 全局语言专家：语言检测与英文统一转换
    lang_info = process_query_for_llm(openai_client, user_input, chat_history)
    en_query = lang_info['english_query']
    orig_lang = lang_info['original_language']
    
    # 2. 总路由决策
    routes = master_orchestrate(openai_client, en_query, chat_history)
    print(f"🚦 路由决策: {routes['route']}")
    
    responses = []
    updated_history = chat_history.copy()
    
    # 3. 执行子 Agent
    if "Paper_Agent" in routes["route"]:
        # 执行文献 RAG 流程
        paper_answer, paper_history = run_rag_pipeline(
            openai_client, en_query, index, id_map, rag_data, chat_history
        )
        responses.append(f"### Literature Evidence (PMID Based):\n{paper_answer}")
        updated_history = paper_history # 更新历史记录

    if "Tool_Agent" in routes["route"]:
        # 执行 Tool_Agent 检索与规划流程
        retrieved = retriever.prompt_based_retrieval(en_query, all_tool_resources, retriever_llm)
        tool_answer = planner.go(en_query, retrieved, str(chat_history))
        responses.append(f"### Analysis & Experimental Workflow:\n{tool_answer}")

    # 4. 全局最终翻译
    combined_answer = "\n\n---\n\n".join(responses)
    if not combined_answer:
        combined_answer = "I'm sorry, I couldn't find a suitable agent to handle your request."
        
    final_translated = translate_answer_to_original(openai_client, combined_answer, orig_lang)
    
    # 5. 更新历史记录 (保持 Assistant 的回复为英文)
    updated_history.append({"role": "user", "content": en_query})
    updated_history.append({"role": "assistant", "content": combined_answer})
    
    return final_translated, updated_history

# --- 5. 交互入口 ---
if __name__ == "__main__":
    history = []
    print("\n🚀 TiAgent 已启动。输入 'exit' 退出。")
    while True:
        user_input = input("\n👤 User: ")
        if user_input.lower() in ['exit', 'quit']: break
        
        answer, history = run_tiagent(user_input, history)
        print(f"\n🤖 TiAgent:\n{answer}")