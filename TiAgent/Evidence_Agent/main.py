import numpy as np
import json
import os
import sys
import time
from openai import OpenAI
from typing import Dict, List, Any, Tuple 
# 尝试导入 faiss
try:
    import faiss
except ImportError:
    faiss = None
    print("❌ 警告：未找到 faiss 依赖。请运行 'pip install faiss-cpu'")

# 1. 导入 Orchestrator 逻辑和配置
from Evidence_Agent.orchestrator import orchestrate_query, KNOWLEDGE_BASE_MAP
# Import RAG Agents core functions
from Evidence_Agent.rag_multi_agent_query import retrieve_chunks, generate_answer, validate_and_finalize_answer

# --- Configuration Definition (Must be consistent) ---
import os
from pathlib import Path

# 获取当前文件 (main.py) 所在的目录路径
BASE_DIR = Path(__file__).parent

# 修改资产文件路径，将其指向 Evidence_Agent 文件夹内部
VECTOR_INDEX_FILE = str(BASE_DIR / 'rag_knowledge_index.faiss')
RAG_DATA_JSON = str(BASE_DIR / 'rag_knowledge_data.json')
ID_MAP_FILE = str(BASE_DIR / 'faiss_id_map.json')
EMBEDDING_MODEL = 'text-embedding-3-large'

REASONING_MODEL = "gpt-4o" # Reasoning Agent and Translation Agent Model

# 🛠️ User provided API Configuration
API_KEY = "sk-GBBQQWHSKHU76HFS5tsHmmffzbQi1dnLy5VdnPU6Kp9gtm3n"
API_BASE = "https://api.bianxie.ai/v1" 


# --- Helper Function: LLM Call and Retry ---

def llm_call_with_retry(client: OpenAI, messages: List[Dict[str, str]], response_format: Dict[str, str] = None) -> str:
    """Helper function to call LLM with simple exponential backoff retry."""
    MAX_RETRIES = 3
    # 强制使用 REASONING_MODEL，除非明确配置其他模型
    model_name = REASONING_MODEL
    
    for attempt in range(MAX_RETRIES):
        try:
            response = client.chat.completions.create(
                model=model_name,
                messages=messages,
                response_format=response_format if response_format else {"type": "text"},
                temperature=0.0
            )
            return response.choices[0].message.content
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                print(f"    [LLM Call Retry {attempt + 1}] 遇到错误: {e}. 正在重试...")
                time.sleep(2 ** attempt) # Exponential backoff
                continue
            raise e
    return "" 

# --- Helper Function: Robust Chinese Detection ---

def contains_chinese(text: str) -> bool:
    """使用 Unicode 范围简单检查字符串是否包含 CJK 字符，作为语言检测的回退机制。"""
    # Unicode range for CJK Unified Ideographs
    return any('\u4e00' <= char <= '\u9fff' for char in text)


# --- Core Function X: Language Processing Agent (Translation and Language Detection) ---

import re  # 务必确保在文件顶部导入 re

def process_query_for_llm(client: OpenAI, query: str, history: List[Dict[str, str]]) -> Dict[str, str]:
    """
    Language Processing Agent: 检测语言并生成英文搜索查询。
    优化版：强化了 Prompt 对 JSON 格式的约束，并增加了正则提取逻辑，彻底消除格式错误。
    """
    
    # 1. System Prompt: 极度明确的格式要求
    system_prompt = (
        "You are a strict Language Processing Agent. Your goal is to prepare a search query for a vector database.\n"
        "Your Output MUST be a raw JSON object with exactly two keys:\n"
        "1. 'original_language': The 2-letter ISO code of the user's input (e.g., 'zh', 'en').\n"
        "2. 'english_query': A standalone, context-aware English search query based on the user input and history.\n"
        "\n"
        "⛔ CONSTRAINT: Do NOT return Markdown formatting (no ```json). Do NOT return any text outside the JSON object."
    )
    
    # history stores ENGLISH messages for consistent context
    full_conversation_context = "\n".join([f"{item['role']: <10}: {item['content']}" for item in history]) if history else "None"
    
    # 2. User Prompt: 增加 One-Shot 示例
    user_prompt = (
        f"### Conversation History (English Context):\n{full_conversation_context}\n\n"
        f"### Current User Input:\n{query}\n\n"
        "### Task:\n"
        "1. Detect the language of 'Current User Input'.\n"
        "2. Resolve pronouns (it, this, that) using History and translate/refine Input into a specific English search query.\n\n"
        "### Expected Output Format (Example):\n"
        '{"original_language": "zh", "english_query": "What are the T-cell subtypes in liver cancer?"}'
    )
    
    # 定义 LLM 输出的 JSON 结构
    response_format = {"type": "json_object"}
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    # 语言回退机制
    lang_code_fallback = 'zh' if contains_chinese(query) else 'en'
    fallback_info = {'original_language': lang_code_fallback, 'english_query': query} 
    
    try:
        # 调用 LLM
        response_str = llm_call_with_retry(
            client, 
            messages, 
            response_format=response_format,
        )
        
        # 3. Python 侧的鲁棒性处理：正则提取 JSON
        match = re.search(r"\{.*\}", response_str, re.DOTALL)
        if match:
            clean_json_str = match.group(0)
            translation_info = json.loads(clean_json_str)
        else:
            raise ValueError("No JSON object found in LLM response")
        
        # 验证关键键
        if 'english_query' in translation_info and 'original_language' in translation_info:
             # 标准化语言代码 (移除 'zh-CN' -> 'zh')
             original_lang = translation_info['original_language'].lower().split('-')[0]
             translation_info['original_language'] = original_lang
             return translation_info
        else:
             print(f"❌ [Warning] Language Agent output missing keys. Raw: {response_str[:50]}...")
             return fallback_info
             
    except json.JSONDecodeError:
        print(f"❌ [Warning] Language Agent produced invalid JSON. Raw: {response_str[:50]}...")
        return fallback_info
    except Exception as e:
        print(f"❌ [Error] Language Agent failed: {e}")
        return fallback_info


def translate_answer_to_original(client: OpenAI, english_answer: str, target_language_code: str) -> str:
    """
    根据用户的原始语言代码，决定是翻译还是直接返回英文答案。
    """
    if target_language_code.lower() in ['en', 'english']:
        print("    - 目标语言为英文，跳过翻译步骤。")
        return english_answer 
        
    print(f"    - 目标语言为 '{target_language_code}'，执行翻译。")
    
    system_prompt = (
        f"You are a professional Translation Agent. Translate the provided English biological RAG answer precisely and naturally into the language corresponding to the code '{target_language_code}'. "
        "Strictly preserve all formatting (markdown, lists, tables), and keep all internal references (like [ID: SL001], PMIDs, links) exactly in their original location. "
        "Do not add any extra commentary, explanation, or translation notes."
    )
    user_prompt = f"Target language code: '{target_language_code}'. Translate the following English RAG answer: \n---\n{english_answer}"
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]
    
    try:
        return llm_call_with_retry(client, messages, response_format={"type": "text"})
    except Exception as e:
        print(f"❌ Language Agent (Answer Translation) failed: {e}. Returning English answer with a warning.")
        return f"[Translation Failed. Returning English answer due to API error.]\n---\n{english_answer}"


# --- Core Function A: Asset Loading ---

def load_rag_assets():
    """Load FAISS index, ID mapping, and raw RAG knowledge data."""
    if faiss is None:
        raise RuntimeError("FAISS library not installed, cannot perform vector retrieval.")

    try:
        index = faiss.read_index(VECTOR_INDEX_FILE)
        with open(ID_MAP_FILE, 'r', encoding='utf-8') as f:
            id_map = json.load(f)
        with open(RAG_DATA_JSON, 'r', encoding='utf-8') as f:
            rag_data = json.load(f)
        
        print(f"✅ RAG assets loaded successfully. Index size: {index.ntotal}, Chunk count: {len(rag_data)}")
        return index, id_map, rag_data
    except Exception as e:
        print(f"❌ 错误: 无法加载 RAG 资产文件。请先运行 chrunk.py 生成资产。错误信息: {e}")
        if isinstance(e, FileNotFoundError):
             print(f"    - 缺失文件: 请检查 {VECTOR_INDEX_FILE}, {ID_MAP_FILE}, {RAG_DATA_JSON} 是否存在。")
        raise


# --- Core Function B: RAG Pipeline Execution (Supporting Multi-turn conversation) ---
def run_rag_pipeline(openai_client: OpenAI, user_input: str, index: faiss.Index, id_map: list, rag_data: list, history: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
    """
    Executes the RAG Multi-Agent flow: Translation -> Orchestration -> Retrieval -> Reasoning -> Validation -> Translation.
    """
    
    # 1. --- [Agent X] Language Processing Agent (Translate/Detect) ---
    print("\n--- Starting Language Agent (Translation/Detection) ---")
    translation_info = process_query_for_llm(openai_client, user_input, history)
    english_query = translation_info['english_query']
    original_language = translation_info['original_language']
    
    print(f"✅ [Language Agent] Detected Language: {original_language}. Search Query (EN): '{english_query}'")


    # 2. --- [Agent 1] Orchestrator Agent (Routing) ---
    print("\n--- Starting Orchestrator Agent (Routing Decision) ---")
    routing_decision = orchestrate_query(openai_client, english_query, history) 
    
    if not routing_decision:
        print("❌ Orchestrator failed to route or returned an invalid decision. Process aborted.")
        error_msg_en = "Routing failed. The knowledge retrieval process was aborted."
        return translate_answer_to_original(openai_client, error_msg_en, original_language), history

    target_agents = routing_decision.get("target_agents", [])
    search_query = routing_decision.get("search_query", english_query) 
    metadata_filter = routing_decision.get("metadata_filter", {})
    
    print("✅ [Orchestrator] Routing Decision:")
    print(f" - Unified Search Keyword: '{search_query}'")
    print(f" - Target Expert Agent(s): {', '.join(target_agents)}")
    print(f" - Applied Filters: {metadata_filter}")

    # 3. --- [Agent 3] Knowledge Retrieval Agents (Loop through expert agents) ---
    all_retrieved_chunks = []
    
    if not target_agents:
        print("⚠️ Orchestrator did not identify target agents. Process aborted.")
        error_msg_en = "No target knowledge base agent was identified, retrieval cannot be performed."
        return translate_answer_to_original(openai_client, error_msg_en, original_language), history
    else:
        print("\n--- Starting Expert Retrieval Agent ---")
        for agent_name in target_agents:
            if agent_name not in KNOWLEDGE_BASE_MAP: continue

            source_table = KNOWLEDGE_BASE_MAP[agent_name]['source_table']
            
            chunks = retrieve_chunks(
                client=openai_client, 
                query=search_query, 
                index=index, 
                id_map=id_map, 
                rag_data=rag_data, 
                source_table=source_table,
                metadata_filter=metadata_filter,
                k=5  
            )
            all_retrieved_chunks.extend(chunks)

        unique_chunks_map = {chunk['chunk_id']: chunk for chunk in all_retrieved_chunks}
        sorted_unique_chunks = sorted(unique_chunks_map.values(), key=lambda x: x['distance'])
        
        print(f"\n✅ Retrieval phase complete. Found {len(sorted_unique_chunks)} unique knowledge chunks.")

        # 4. --- [Agent 4] Answer Generation Agent (Reasoning Agent) ---
        print("\n--- Starting Reasoning Agent (Answer Generation in EN) ---")
        reasoning_answer_en = generate_answer(openai_client, search_query, sorted_unique_chunks, history) 
        
        # 5. --- [Agent 5] Validation Agent (Review and Citation in EN) ---
        print("\n--- Starting Validation Agent (Review and Citation in EN) ---")
        english_answer = validate_and_finalize_answer(openai_client, reasoning_answer_en, sorted_unique_chunks)
        
        # 6. --- [Agent X] Language Processing Agent (Final Translation) ---
        print(f"\n--- Starting Language Agent (Final Output Language: {original_language}) ---")
        
        final_answer_translated = translate_answer_to_original(openai_client, english_answer, original_language)
        
        # --- Update History ---
        new_history = history.copy()
        new_history.append({"role": "user", "content": english_query})
        new_history.append({"role": "assistant", "content": english_answer})
        
        MAX_HISTORY_PAIRS = 5
        if len(new_history) > MAX_HISTORY_PAIRS * 2:
            new_history = new_history[-MAX_HISTORY_PAIRS * 2:]

        return final_answer_translated, new_history

    return "发生未知错误。", history 


# =====================================================================
# 🌟 新增：供总控 (tiagent_master.py) 调用的统一入口函数
# =====================================================================
_cached_index = None
_cached_id_map = None
_cached_rag_data = None
_cached_openai_client = None

def run_evidence_agent(query: str) -> str:
    """
    接收 master 传来的标准化 query，执行 RAG 检索并返回最终字符串结果。
    """
    global _cached_index, _cached_id_map, _cached_rag_data, _cached_openai_client
    
    # 1. 全局缓存加载：保证巨大的 FAISS 索引在整个网站运行期间只加载一次
    if _cached_index is None:
        print("📦 [Evidence Agent] 正在初始化本地知识库资产...")
        if faiss is None:
            return "❌ 错误: FAISS 库未安装，无法执行 RAG 检索。"
        _cached_index, _cached_id_map, _cached_rag_data = load_rag_assets()
        _cached_openai_client = OpenAI(api_key=API_KEY, base_url=API_BASE)
        
    # 2. 调用核心 RAG 流程
    # 此时 query 已经是 master 经过语义消解的英文检索词，所以 history 传空即可
    try:
        final_answer, _ = run_rag_pipeline(
            openai_client=_cached_openai_client, 
            user_input=query, 
            index=_cached_index, 
            id_map=_cached_id_map, 
            rag_data=_cached_rag_data, 
            history=[]  
        )
        return final_answer
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Evidence Agent 检索过程中发生错误: {str(e)}"

# =====================================================================


if __name__ == "__main__":
    # --- Global Asset Initialization (Only once) ---
    if faiss is None:
        print("❌ 错误: FAISS 库未安装，无法执行 RAG 流程。请安装 'pip install faiss-cpu'")
        sys.exit(1)

    try:
        index, id_map, rag_data = load_rag_assets()
        openai_client = OpenAI(api_key=API_KEY, base_url=API_BASE)
        print(f"✅ OpenAI Client initialized with base URL: {API_BASE}")
    except Exception:
        sys.exit(1)

    # --- Start Multi-turn Conversation Loop ---
    session_id = f"session-{os.getpid()}-{os.urandom(4).hex()}" 
    chat_history: List[Dict[str, str]] = [] 
    
    print("\n========================================================")
    print(f"🚀 RAG Multi-Agent Chatbot Started (Session ID: {session_id})")
    print("--------------------------------------------------------")
    print("示例查询 (可使用任何语言): 'Treg细胞在结直肠癌中的空间共定位是什么？' 或 'What is its mechanism of action?'")
    print("输入 'exit' 或 'quit' 退出。")
    print("========================================================\n")

    while True:
        try:
            user_input = input("👤 用户查询: ").strip()

            if user_input.lower() in ['exit', 'quit']:
                print("\n👋 退出 RAG 聊天机器人。")
                break
            
            if not user_input:
                continue

            final_answer_translated, chat_history = run_rag_pipeline(
                openai_client, 
                user_input, 
                index, 
                id_map, 
                rag_data, 
                chat_history 
            )

            if final_answer_translated:
                print("\n========================================================")
                detected_lang = chat_history[-2]['content'] if len(chat_history) >= 2 else 'en'
                is_translated = detected_lang.lower() not in ['en', 'english']
                output_label = "最终回答 (已翻译)" if is_translated and "Translation Failed" not in final_answer_translated else "最终回答 (EN)"
                
                print(f"🤖 {output_label}:")
                print("--------------------------------------------------------")
                print(final_answer_translated)
                print("========================================================\n")

        except KeyboardInterrupt:
            print("\n👋 退出 RAG 聊天机器人。")
            break
        except Exception as e:
            import traceback
            print(f"❌ 发生意外错误: {e}")
            traceback.print_exc()
            break