import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from Evidence_Agent.main import run_evidence_agent
from Workflow_Agent.run_agent import run_workflow_agent
from Workflow_Agent.config import default_config  # 统一从 config 导入

# ==========================================
# 提前加载 .env 文件
# ==========================================
load_dotenv()

# ---------------------------------------------------------
# 1. Language Agent: 语义消解与标准化查询
# ---------------------------------------------------------
def language_agent_standardize(client, user_query, history_str):
    prompt = f"""
    You are a Biomedical Language Agent. 
    Your goal is to perform Semantic Disambiguation and Query Refinement.
    
    Tasks:
    1. Resolve Pronouns: If user says 'its impact', identify what 'it' refers to from the history.
    2. Expand Abbreviations: Convert terms like 'TAMs' to 'Tumor-associated Macrophages'.
    3. Standardization: Output a complete, standalone English query.
    
    CRITICAL RULE: If the user input is a simple greeting (like "你好", "hello") or casual chat, DO NOT add any biomedical instructions. Just output the simple greeting directly (e.g., "Hello").
    
    User-Specific History:
    {history_str}
    
    Current User Input: {user_query}
    
    Standardized English Query:"""
    
    response = client.chat.completions.create(
        model=default_config.llm, # 统一模型
        messages=[{"role": "system", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# ---------------------------------------------------------
# 2. Master Orchestrator: 自主路由与直接回复 (已修复 JSON 解析错误)
# ---------------------------------------------------------
def master_orchestrate(client, standardized_query):
    prompt = f"""
        You are the Master Orchestrator of TiAgent, a sophisticated Biomedical Assistant. 
        Your task is to route the Standardized Query to the most appropriate functional agent(s).

        ### Agent Responsibilities:
        1. [General]: 
           - Scope: Greetings, self-introductions, casual chat, or general non-technical questions.
           - Example: "Hello", "Who are you?", "What can you do?".
        2. [Evidence_Agent]: 
           - Scope: Retrieval of biological facts, literature evidence, database records, and specific entity information. 
           - Keywords: "What is", "impact of", "distribution of", "correlation between", "expression level".
           - Example: "The spatial distribution of TAMs in bladder cancer", "Are TAMs important in cancer immunity?".
        3. [Workflow_Agent]: 
           - Scope: Designing experimental protocols, bioinformatics pipelines, analysis workflows, or generating R/Python code for data analysis.
           - Keywords: "How to analyze", "design a pipeline", "workflow for", "code to calculate", "protocol for".
           - Example: "Design a pipeline to analyze spatial topology", "Workflow for single-cell annotation".

        ### Routing Rules:
        - If the query asks for "How-to" or "Analysis Process", choose [Workflow_Agent].
        - If the query asks for "Facts", "Knowledge", or "Data Retrieval", choose [Evidence_Agent].
        - If it's a greeting, choose [General].
        - You CAN select both [Evidence_Agent] and [Workflow_Agent] if the query requires both knowledge and a plan.

        Standardized Query: "{standardized_query}"

        Return JSON format:
        {{
            "route": ["General" | "Evidence_Agent" | "Workflow_Agent"],
            "direct_response": "Your friendly response in the user's original language ONLY if route is General, else null"
        }}
    """
    try:
        response = client.chat.completions.create(
            model=default_config.llm,
            messages=[{"role": "system", "content": prompt}],
            response_format={"type": "json_object"}
        )
        
        raw_content = response.choices[0].message.content
        
        # 核心防御逻辑：防止空内容或非JSON内容导致崩溃
        if not raw_content or not raw_content.strip():
            return {"route": ["General"], "direct_response": "抱歉，系统响应异常，请稍后再试。"}
            
        return json.loads(raw_content)
        
    except json.JSONDecodeError:
        print(f"❌ JSON 解析失败，原始内容: {raw_content}")
        return {"route": ["General"], "direct_response": "我是 TiAgent，目前正在处理您的请求，请稍候。"}
    except Exception as e:
        print(f"❌ 路由决策异常: {str(e)}")
        return {"route": ["General"], "direct_response": f"🤖 系统繁忙: {str(e)}"}

# ---------------------------------------------------------
# 3. 总控运行逻辑
# ---------------------------------------------------------
def run_tiagent(user_input, history_str):
    api_key = os.getenv("BIANXIE_AI_API_KEY")
    if not api_key:
        return "❌ 抱歉，系统无法获取 API 密钥，请检查服务器 .env 配置。"

    client = OpenAI(
        api_key=api_key,
        base_url="https://api.bianxie.ai/v1"
    )

    try:
        # 1. 语义消解
        std_query = language_agent_standardize(client, user_input, history_str)

        # 2. 路由决策 
        decision = master_orchestrate(client, std_query)
        
        if "General" in decision.get("route", ["General"]):
            return decision.get("direct_response", "我是 TiAgent，您的生物医学研究助理。")

        # 3. 任务分配
        results = []
        if "Evidence_Agent" in decision["route"]:
            results.append(run_evidence_agent(std_query)) 
        if "Workflow_Agent" in decision["route"]:
            results.append(run_workflow_agent(std_query))
        
        return "\n\n".join(results) if results else "未能找到相关结果。"
        
    except Exception as e:
        return f"🤖 TiAgent 运行异常: {str(e)}"

# ---------------------------------------------------------
# 4. 自动生成简短对话标题
# ---------------------------------------------------------
def generate_session_title(user_query):
    api_key = os.getenv("BIANXIE_AI_API_KEY")
    if not api_key:
        return user_query[:10] + "..."
        
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.bianxie.ai/v1"
    )
    
    prompt = f"Extract the core keywords from the user input below to generate a very short conversation title. Strictly limit it to 10 words or fewer. Output ONLY the title text. User Input: {user_query}\nTitle:"
    
    try:
        response = client.chat.completions.create(
            model=default_config.llm, # 统一模型
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.3 
        )
        title = response.choices[0].message.content.strip()
        title = title.replace('"', '').replace('”', '').replace('“', '')
        return title
    except Exception:
        return user_query[:10] + "..."

# ---------------------------------------------------------
# 5. 测试函数 (Main Test Suite)
# ---------------------------------------------------------
if __name__ == "__main__":
    import sys
    
    # 确保 API 密钥存在
    test_api_key = os.getenv("BIANXIE_AI_API_KEY")
    if not test_api_key:
        print("❌ 错误: 未在 .env 或环境变量中找到 BIANXIE_AI_API_KEY")
        sys.exit(1)

    print(f"🚀 开始 TiAgent 功能测试 (当前模型: {default_config.llm})")
    print("-" * 50)

    # 定义测试用例
    test_cases = [
        {
            "name": "闲聊/打招呼测试 (General)",
            "input": "你好呀，你是谁？",
            "history": ""
        },
        {
            "name": "语义消解测试 (Contextual)",
            "input": "它在膀胱癌中的空间分布是怎样的？",
            "history": "User: TAMs are important in cancer immunity."
        },
        {
            "name": "工作流规划测试 (Workflow_Agent)",
            "input": "帮我设计一个分析肿瘤相关巨噬细胞空间拓扑结构的生物信息学流程。",
            "history": ""
        }
    ]

    for case in test_cases:
        print(f"\n执行测试: {case['name']}")
        print(f"用户输入: {case['input']}")
        print(f"历史记录: {case['history']}")
        
        try:
            # 运行 TiAgent
            # 注意：run_tiagent 内部会调用标准化和路由决策
            result = run_tiagent(case['input'], case['history'])
            
            print(f"🤖 TiAgent 响应:\n{result}")
            
            # 测试标题生成功能
            title = generate_session_title(case['input'])
            print(f"📌 自动生成标题: {title}")
            
        except Exception as e:
            print(f"💥 测试过程中发生崩溃: {e}")
        
        print("-" * 50)

    print("\n✅ 所有测试用例执行完毕。")