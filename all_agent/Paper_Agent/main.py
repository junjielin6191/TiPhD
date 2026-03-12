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
from Paper_Agent.orchestrator import orchestrate_query, KNOWLEDGE_BASE_MAP
# Import RAG Agents core functions
try:
    from Paper_Agent.rag_multi_agent_query import generate_answer, retrieve_chunks, validate_and_finalize_answer
except ImportError:
    # Fallback/Mock import if the file is missing
    print("⚠️ 警告：未找到 rag_multi_agent_query.py 文件。请确保函数已定义或导入。")
    def generate_answer(client: OpenAI, query: str, retrieved_chunks: list, history: List[Dict[str, str]]) -> str:
        return "模拟答案生成：请确保 rag_multi_agent_query 文件存在。"
    def retrieve_chunks(client: OpenAI, query: str, index: faiss.Index, id_map: list, rag_data: list, source_table: str, metadata_filter: Dict[str, str], k: int = 5) -> list:
        return []
    def validate_and_finalize_answer(client: OpenAI, reasoning_answer: str, retrieved_chunks: list) -> str:
        return reasoning_answer


# --- Configuration Definition (Must be consistent) ---
import os
from pathlib import Path

# 获取当前文件 (main.py) 所在的目录路径
BASE_DIR = Path(__file__).parent

# 修改资产文件路径，将其指向 Paper_Agent 文件夹内部
VECTOR_INDEX_FILE = str(BASE_DIR / 'rag_knowledge_index.faiss')
RAG_DATA_JSON = str(BASE_DIR / 'rag_knowledge_data.json')
ID_MAP_FILE = str(BASE_DIR / 'faiss_id_map.json')
EMBEDDING_MODEL = 'text-embedding-3-large'

REASONING_MODEL = "gpt-4o" # Reasoning Agent and Translation Agent Model

# 🛠️ User provided API Configuration
# Note: You should replace this with your actual, private API key if running outside the provided environment
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
        # 即使模型输出了 ```json ... ``` 或其他杂质，正则也能把最外层的 {} 抓出来
        match = re.search(r"\{.*\}", response_str, re.DOTALL)
        if match:
            clean_json_str = match.group(0)
            translation_info = json.loads(clean_json_str)
        else:
            # 如果正则都没找到 {}，那说明模型彻底崩了，抛出异常进入下面的 except
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
    
    如果 target_language_code 是 'en' 或 'english'，则直接返回英文答案。
    否则，执行翻译流程。
    """
    
    # *** 关键：判断是否需要翻译 ***
    if target_language_code.lower() in ['en', 'english']:
        print("    - 目标语言为英文，跳过翻译步骤。")
        return english_answer 
        
    print(f"    - 目标语言为 '{target_language_code}'，执行翻译。")
    
    # 设置翻译 Agent 的系统提示，要求翻译到目标语言
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
        # Translation does not require JSON output
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
             print(f"    - 缺失文件: 请检查 {VECTOR_INDEX_FILE}, {ID_MAP_FILE}, {RAG_DATA_JSON} 是否存在。")
        raise


# --- Core Function B: RAG Pipeline Execution (Supporting Multi-turn conversation) ---
def run_rag_pipeline(openai_client: OpenAI, user_input: str, index: faiss.Index, id_map: list, rag_data: list, history: List[Dict[str, str]]) -> Tuple[str, List[Dict[str, str]]]:
    """
    Executes the RAG Multi-Agent flow: Translation -> Orchestration -> Retrieval -> Reasoning -> Validation -> Translation.
    
    The internal chat_history stores ENGLISH messages for consistent context for the LLM agents.
    """
    
    # 1. --- [Agent X] Language Processing Agent (Translate/Detect) ---
    print("\n--- Starting Language Agent (Translation/Detection) ---")
    translation_info = process_query_for_llm(openai_client, user_input, history)
    english_query = translation_info['english_query']
    original_language = translation_info['original_language']
    
    print(f"✅ [Language Agent] Detected Language: {original_language}. Search Query (EN): '{english_query}'")


    # 2. --- [Agent 1] Orchestrator Agent (Routing) ---
    print("\n--- Starting Orchestrator Agent (Routing Decision) ---")
    # Pass the English query and the English history
    routing_decision = orchestrate_query(openai_client, english_query, history) 
    
    if not routing_decision:
        print("❌ Orchestrator failed to route or returned an invalid decision. Process aborted.")
        error_msg_en = "Routing failed. The knowledge retrieval process was aborted."
        # 返回翻译后的错误信息
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
        # 返回翻译后的错误信息
        return translate_answer_to_original(openai_client, error_msg_en, original_language), history
    else:
        print("\n--- Starting Expert Retrieval Agent ---")
        for agent_name in target_agents:
            if agent_name not in KNOWLEDGE_BASE_MAP: continue

            source_table = KNOWLEDGE_BASE_MAP[agent_name]['source_table']
            
            # Call the expert Agent's retrieval function
            chunks = retrieve_chunks(
                client=openai_client, 
                query=search_query, # Use the English search_query
                index=index, 
                id_map=id_map, 
                rag_data=rag_data, 
                source_table=source_table,
                metadata_filter=metadata_filter,
                k=5  # Retrieve 5 chunks per agent
            )
            all_retrieved_chunks.extend(chunks)

        # Integrate retrieval results, sort by distance, and deduplicate
        unique_chunks_map = {chunk['chunk_id']: chunk for chunk in all_retrieved_chunks}
        sorted_unique_chunks = sorted(unique_chunks_map.values(), key=lambda x: x['distance'])
        
        print(f"\n✅ Retrieval phase complete. Found {len(sorted_unique_chunks)} unique knowledge chunks.")

        # 4. --- [Agent 4] Answer Generation Agent (Reasoning Agent) ---
        print("\n--- Starting Reasoning Agent (Answer Generation in EN) ---")
        # Reasoning Agent returns an English answer
        # Note: Must pass the ENGLISH search_query
        reasoning_answer_en = generate_answer(openai_client, search_query, sorted_unique_chunks, history) 
        
        # 5. --- [Agent 5] Validation Agent (Review and Citation in EN) ---
        print("\n--- Starting Validation Agent (Review and Citation in EN) ---")
        english_answer = validate_and_finalize_answer(openai_client, reasoning_answer_en, sorted_unique_chunks)
        
        # 6. --- [Agent X] Language Processing Agent (Final Translation) ---
        print(f"\n--- Starting Language Agent (Final Output Language: {original_language}) ---")
        
        # *** 关键：调用翻译函数，根据 original_language 决定是否翻译 ***
        final_answer_translated = translate_answer_to_original(openai_client, english_answer, original_language)
        
        
        # --- Update History: Store the ENGLISH conversation for subsequent LLM context ---
        # 仅将翻译后的查询和最终英文答案存储到历史中
        new_history = history.copy()
        new_history.append({"role": "user", "content": english_query})
        new_history.append({"role": "assistant", "content": english_answer})
        
        # Simple history truncation strategy (Optional): keep only the last N pairs
        MAX_HISTORY_PAIRS = 5
        if len(new_history) > MAX_HISTORY_PAIRS * 2:
            new_history = new_history[-MAX_HISTORY_PAIRS * 2:]

        return final_answer_translated, new_history

    # Should be unreachable
    return "发生未知错误。", history 


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
    # History stores ENGLISH version of the conversation for internal LLM context
    chat_history: List[Dict[str, str]] = [] 
    
    print("\n========================================================")
    print(f"🚀 RAG Multi-Agent Chatbot Started (Session ID: {session_id})")
    print("--------------------------------------------------------")
    print("示例查询 (可使用任何语言): 'Treg细胞在结直肠癌中的空间共定位是什么？' 或 'What is its mechanism of action?'")
    print("输入 'exit' 或 'quit' 退出。")
    print("========================================================\n")

    # Core: Conversation input entry point (while True loop)
    while True:
        try:
            # Use input() to receive user input
            user_input = input("👤 用户查询: ").strip()

            if user_input.lower() in ['exit', 'quit']:
                print("\n👋 退出 RAG 聊天机器人。")
                break
            
            if not user_input:
                continue

            # Execute RAG flow and receive the updated history
            final_answer_translated, chat_history = run_rag_pipeline(
                openai_client, 
                user_input, 
                index, 
                id_map, 
                rag_data, 
                chat_history 
            )

            # Print the final translated result
            if final_answer_translated:
                print("\n========================================================")
                
                # 从 chat_history 中找到 LLM 成功检测的语言代码
                # 如果检测失败，语言代码会回退到 'zh'（如果包含中文）或 'en'
                # 即使 LLM 失败，我们现在也能正确打印出目标语言代码，并判断是否需要翻译
                detected_lang = chat_history[-2]['content'] if len(chat_history) >= 2 else 'en'
                is_translated = detected_lang.lower() not in ['en', 'english']
                
                # 检查翻译是否失败的回退信息
                output_label = "最终回答 (已翻译)" if is_translated and "Translation Failed" not in final_answer_translated else "最终回答 (EN)"
                
                print(f"🤖 {output_label}:")
                print("--------------------------------------------------------")
                print(final_answer_translated)
                print("========================================================\n")

        except KeyboardInterrupt:
            print("\n👋 退出 RAG 聊天机器人。")
            break
        except Exception as e:
            # Print detailed traceback to prevent hiding errors
            import traceback
            print(f"❌ 发生意外错误: {e}")
            traceback.print_exc()
            break