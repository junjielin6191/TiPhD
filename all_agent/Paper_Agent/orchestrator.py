import json
import sys
from openai import OpenAI
from typing import Dict, List, Any

# --- Configuration Definition ---
# Use a powerful model for routing and intent recognition
ORCHESTRATOR_MODEL = "gpt-4o" 

# Knowledge Base Descriptions, used to guide the LLM for routing decisions. MUST BE IN ENGLISH.
# Paper_Agent/orchestrator.py

# 1. 精简知识库映射，仅保留文献相关 Agent
KNOWLEDGE_BASE_MAP = {
    "Celltype Agent": {
        "source_table": "CellType_Phenotype",
        "description": "Queries related to cell types, cell markers, phenotypes, and cell-drug associations. E.g., 'What is the marker of Treg cells in liver cancer?'"
    },
    "Spatial Agent": {
        "source_table": "Spatial_Phenotype",
        "description": "Queries related to spatial distribution, cell-cell interactions, microenvironment structure, and spatial omics. E.g., 'What is the spatial co-localization relationship of Tregs in colorectal cancer?'"
    }
}

# 2. 修改 orchestrate_query 函数中的系统提示词
def orchestrate_query(client: OpenAI, user_query: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    # ... (保持原本的 kb_description 生成逻辑)
    
    system_instruction = (
        "You are a Literature RAG Routing Agent. Your task is to identify biological evidence retrieval intent."
        "1. **Context Analysis**: Resolve pronouns using history."
        "2. **Agent Selection**: Select from Celltype Agent or Spatial Agent. If unsure, select both."
        f"Knowledge Base List:\n{kb_description}\n"
        # 删除了原有的 Special Analysis Workflow Rule 逻辑
        "3. **Query Optimization**: Refine intent into keywords for vector retrieval."
        "4. **Output Format**: Strictly output JSON."
    )
    # ... (后续调用逻辑保持不变)

# --- Core Agent Implementation ---

def orchestrate_query(client: OpenAI, user_query: str, history: List[Dict[str, str]]) -> Dict[str, Any]:
    """
    Orchestrator Agent: Receives the English query and outputs a structured routing decision.
    
    Args:
        client: OpenAI client instance.
        user_query: The user's current query (already translated to English).
        history: The conversation history (all messages are in English for consistent context).
    """
    
    kb_description = "\n".join([
        f"  - [{name}]: {info['description']} (Source Table: {info['source_table']})"
        for name, info in KNOWLEDGE_BASE_MAP.items()
    ])
    
    # --- System Prompt (MUST BE IN ENGLISH) ---
    system_instruction = (
        "You are a high-level RAG Routing Agent (Orchestrator Agent), responsible for analyzing the user's query and generating a structured routing decision JSON."
        "Your primary goals are to: identify the query intent, select the appropriate expert Agent(s), and extract accurate search keywords and metadata filtering conditions."
        "\n--- Core Instructions ---\n"
        "1. **Context Analysis (Mandatory):** The user's query may be context-dependent. You MUST check the provided `Conversation History` to resolve pronouns (like 'it', 'these') and combine the full intent with the current query into a single, complete `search_query`."
        "2. **Agent Selection:** Select one or more of the most relevant Agents from the knowledge base list below. If unsure, select multiple to improve recall."
        # ADDED/MODIFIED RULE: Special Analysis Workflow Rule - 强制路由到 Tool Agent
        f"Knowledge Base List:\n{kb_description}\n"
        "3. **Query Optimization:** Refine the full user intent into a concise, general `search_query` keyword suitable for vector retrieval."
        "4. **Metadata Filtering:** Identify explicit metadata mentioned in the query, such as cancer type (`main_cancer_type`) or species (`species`), and extract them precisely into the `metadata_filter` field. **For any metadata not explicitly mentioned, use an empty string `\"\"`**."
        "5. **Output Format:** You MUST and can ONLY output a complete JSON string that strictly adheres to the schema below. DO NOT output any explanatory text, markdown formatting, or other content."
        "\n--- JSON Schema ---\n"
        "{\n"
        "  \"target_agents\": [\"Agent Name 1\", \"Agent Name 2\", ...], \n"
        "  \"search_query\": \"Optimized English search query (must include the full, resolved intent)\",\n"
        "  \"metadata_filter\": {\n"
        "    \"main_cancer_type\": \"Colorectal cancer\" or \"\", \n"
        "    \"species\": \"Human\" or \"\",\n"
        "    \"technology_type_for_discovery\": \"Spatial transcriptomics\" or \"\",\n"
        "    \"cell_marker\": \"FOXP3\" or \"\",\n"
        "    \"source_table\": \"\" \n"
        "  }\n"
        "}"
    )
    
    # Construct messages list
    messages = [
        {"role": "system", "content": system_instruction}
    ]
    
    # 1. Add conversation history (providing English context)
    if history:
        # Note: history items should now contain English content
        messages.extend(history)
        
    # 2. Add current English user query
    messages.append({"role": "user", "content": user_query})

    # 3. Call LLM
    try:
        response = client.chat.completions.create(
            model=ORCHESTRATOR_MODEL,
            messages=messages, 
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        # Parse and return JSON result
        decision_json = response.choices[0].message.content
        return json.loads(decision_json)
        
    except Exception as e:
        print(f"❌ Error: Orchestrator Agent call failed or JSON parsing error. Error message: {e}")
        # Return an empty result to trigger a graceful failure in the main loop
        return {}