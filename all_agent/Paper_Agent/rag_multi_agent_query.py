import numpy as np
import json
import sys
from openai import OpenAI
from typing import Dict, List, Any
# Try importing faiss
try:
    import faiss
except ImportError:
    faiss = None
    print("❌ Warning: faiss dependency not found. Please run 'pip install faiss-cpu'")

# --- Configuration Definition (Must be consistent) ---
EMBEDDING_MODEL = 'text-embedding-3-large'
VECTOR_INDEX_FILE = 'rag_knowledge_index.faiss'
RAG_DATA_JSON = 'rag_knowledge_data.json'
ID_MAP_FILE = 'faiss_id_map.json'
REASONING_MODEL = "gpt-4o"  # Reasoning/Validation Agent model


# --- Core Function B: Expert Retrieval Agent (Spatial Agent, Celltype Agent, etc.) ---

def retrieve_chunks(client: OpenAI, query: str, index: faiss.Index, id_map: list, rag_data: list, 
                    source_table: str, metadata_filter: Dict[str, str], k: int = 5) -> list:
    """
    Performs vector retrieval and applies multi-level metadata filtering provided by the Orchestrator.
    """
    
    print(f"    - Executing retrieval for {source_table} (K={k})...")
    
    # 1. Query vectorization (The query is already in English)
    try:
        response = client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=[query]
        )
        query_vector = np.array(response.data[0].embedding, dtype='float32').reshape(1, -1)
    except Exception as e:
        print(f"❌ Error: Embedding API call failed. {e}")
        return []

    # 2. Vector Search (Get K*5 results to handle post-filtering)
    D, I = index.search(query_vector, k * 5) 
    
    retrieved_chunks = []
    
    # 3. Post-filtering
    for distance, chunk_index in zip(D[0], I[0]):
        # chunk_index is the integer index returned by FAISS (i.e., the index in the rag_data list)
        
        # 1. Check if the index is valid, and use the integer index to get the raw knowledge chunk
        if chunk_index >= len(rag_data) or chunk_index < 0:
            continue 
            
        chunk = rag_data[chunk_index]
        
        # 2. Get the string ID of the knowledge chunk from id_map 
        chunk_id = id_map[chunk_index]
        
        # 3.1. Mandatory filter: Filter by source_table
        if chunk['metadata'].get('source_table') != source_table:
            continue
            
        # 3.2. Metadata filtering: Check if all non-empty metadata fields match
        metadata_match = True
        for key, value in metadata_filter.items():
            if value and key in chunk['metadata']: 
                # Check if the chunk's metadata contains the exact value (case-insensitive) provided by the Orchestrator
                if value.lower() not in chunk['metadata'][key].lower():
                    metadata_match = False
                    break
        
        if metadata_match:
            chunk['distance'] = distance # Add distance information
            chunk['chunk_id'] = chunk_id # Ensure ID exists
            retrieved_chunks.append(chunk)
            
            # Stop after reaching the required K results
            if len(retrieved_chunks) >= k:
                break

    print(f"    - Retrieval for {source_table} complete, returned {len(retrieved_chunks)} chunks.")
    return retrieved_chunks


# --- Core Function C: Reasoning Agent (Answer Generation) ---


def generate_answer(client: OpenAI, query: str, retrieved_chunks: list, history: List[Dict[str, str]]) -> str:
    """
    Reasoning Agent: 使用 LLM 和检索到的上下文生成英文答案，并强制使用 PMID 进行引用。
    """
    if not retrieved_chunks:
        return "Sorry, no exact information related to this query was found in the knowledge base."

    # 1. 构造上下文：在每个知识块头部显式标注 PMID
    context_list = []
    for i, chunk in enumerate(retrieved_chunks):
        # 兼容处理大小写 PMID 键名
        pmid = chunk['metadata'].get('PMID') or chunk['metadata'].get('pmid', 'N/A')
        header = f"--- Knowledge Chunk {i+1} [PMID: {pmid}] (Source: {chunk['metadata'].get('source_table', 'N/A')}) ---"
        context_list.append(f"{header}\n{chunk['text']}\n")
    
    context = "\n\n".join(context_list)
    
    # 2. 判断是否包含工具类知识以切换推理模式
    methodology_agents_for_code_gen = ['Tool_Catalog'] 
    has_methodology_chunks = any(
        chunk['metadata'].get('source_table') in methodology_agents_for_code_gen 
        for chunk in retrieved_chunks
    )

    # 3. 构造系统提示词：强制 PMID 引用格式
    base_prompt = (
        "You are a high-level biological knowledge integration and reasoning Agent. "
        "Your task is to synthesize the provided context and generate a professional answer in **ENGLISH**.\n"
        "### STRICT CITATION RULE:\n"
        "For every factual claim, you MUST cite the source using the format [PMID: xxxxxxxx] (e.g., [PMID: 12345678]) "
        "based on the PMID provided in the chunk headers. DO NOT use [ID: XXX] or simple numbers.\n"
    )

    if has_methodology_chunks:
        reasoning_rule = (
            "3. **Reasoning Level (Flexible/Workflow):** Construct a step-by-step workflow based on tool descriptions.\n"
            "4. **Code Generation:** Generate functional code snippets (Python/R) based on the context.\n"
        )
    else:
        reasoning_rule = (
            "3. **Reasoning Level (Strict/Factual):** Restate facts precisely. Minimize reasoning.\n"
            "4. **Code Restriction:** Do not generate new code unless present in the context.\n"
        )

    system_prompt = base_prompt + reasoning_rule + (
        "5. **Professionalism:** Maintain a rigorous tone suitable for bioinformatics research.\n"
        "6. **Coherence:** Ensure the answer aligns with the conversation history."
    )
    
    messages = [{"role": "system", "content": system_prompt}]
    if history:
        messages.extend(history)

    final_user_prompt = (
        f"--- Knowledge Chunk Context ---\n{context}\n\n"
        f"--- Current Query ---\n{query}"
    )
    messages.append({"role": "user", "content": final_user_prompt})

    try:
        response = client.chat.completions.create(
            model=REASONING_MODEL,
            messages=messages, 
            temperature=0.0
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"❌ Error: Reasoning Agent call failed: {e}")
        return "Reasoning Agent error, failed to generate an answer."


# --- Core Function D: Validation Agent (Review and Citation) ---

import re  # 务必确保在文件顶部导入 re 模块

def validate_and_finalize_answer(client: OpenAI, llm_answer: str, retrieved_chunks: list) -> str:
    """
    Validation Agent: 审核答案并附加仅在正文中被引用的 PMID 参考文献列表。
    修改说明：改为基于正则提取的确定性逻辑，解决“引用列表包含未引用文献”的幻觉问题。
    """
    
    # 1. 使用正则表达式提取正文中实际出现的引用
    # 匹配格式如 [PMID: 12345678] 或 [PMID:12345678]，忽略大小写
    cited_pmids = set(re.findall(r'\[PMID:\s*(\d+)\]', llm_answer, re.IGNORECASE))
    
    # 2. 构造去重且排序后的参考文献列表
    if cited_pmids:
        # 将提取到的 PMID 字符串排序，保证输出顺序稳定
        sorted_pmids = sorted(list(cited_pmids))
        
        # 构造 Reference 文本块
        # 如果您希望列表更丰富，可以在这里遍历 retrieved_chunks 匹配标题，
        # 但最稳妥的方式是保持简洁，只列出 PMID。
        references_lines = [f"- [PMID: {pmid}]" for pmid in sorted_pmids]
        references_text = "References:\n" + "\n".join(references_lines)
    else:
        # 如果正文中没有检测到任何引用（可能是回答一般性问题或模型未遵循指令）
        # 保持为空，或者您可以设置为提示语
        references_text = "" 

    # 3. 最终组合
    # 直接拼接返回，不再调用 LLM。
    # 这避免了 Validation Agent 再次把未引用的 chunk 加回来的风险。
    
    if references_text:
        final_output = f"{llm_answer}\n\n---\n{references_text}"
    else:
        final_output = llm_answer

    return final_output