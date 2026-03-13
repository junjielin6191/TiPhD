import json
import os
from dotenv import load_dotenv
from openai import OpenAI
from Evidence_Agent.main import run_evidence_agent
from Workflow_Agent.run_agent import run_workflow_agent

# ==========================================
# 提前加载 .env 文件，这样才能读到你的 API_KEY
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
        model="gpt-4o", 
        messages=[{"role": "system", "content": prompt}]
    )
    return response.choices[0].message.content.strip()

# ---------------------------------------------------------
# 2. Master Orchestrator: 自主路由与直接回复
# ---------------------------------------------------------
def master_orchestrate(client, standardized_query):
    prompt = f"""
        You are the Master Orchestrator of TiAgent. 
        Analyze the Standardized Query: "{standardized_query}"
        
        Routes:
        - [General]: Greetings, introductions, or non-technical chat. 
        - [Evidence_Agent]: Retrieval of biological facts, literature, or database records.
        - [Workflow_Agent]: Experimental protocols, bioinformatics workflows, or code generation.
        
        INSTRUCTIONS for [General]: 
        If the query is a greeting or casual chat, your `direct_response` MUST be warm, natural, and concise (e.g., "你好！我是 TiAgent，有什么我可以帮您的吗？"). DO NOT output robotic instructions or explain your system architecture.
        
        Return JSON format:
        {{
        "route": ["General" | "Evidence_Agent" | "Workflow_Agent"],
        "direct_response": "Your friendly response in the user's original language if route is General, else null"
        }}
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "system", "content": prompt}],
        response_format={"type": "json_object"}
    )
    return json.loads(response.choices[0].message.content)

# ---------------------------------------------------------
# 3. 总控运行逻辑
# ---------------------------------------------------------
def run_tiagent(user_input, history_str):
    """
    history_str 是 app.py 从数据库中提取的、属于该用户的特定历史。
    """
    
    # 🌟 核心修复：从 .env 读取你的专属 BIANXIE_AI_API_KEY
    api_key = os.getenv("BIANXIE_AI_API_KEY")
    if not api_key:
        return "❌ 抱歉，系统无法获取 API 密钥，请检查服务器 .env 配置。"

    # 初始化 OpenAI 客户端
    # 注意：因为你使用的是“边写AI”的中转服务，所以必须加上 base_url 才能调通！
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.bianxie.ai/v1"  # 代理商的接口地址
    )

    try:
        # 1. Language Agent 使用用户专属的历史进行“语义消解”
        std_query = language_agent_standardize(client, user_input, history_str)

        # 2. 路由决策 
        decision = master_orchestrate(client, std_query)
        
        if "General" in decision["route"]:
            # 自由回答：例如打招呼、身份介绍，直接返回 direct_response
            return decision.get("direct_response", "我是 TiAgent，您的生物医学研究助理。")

        # 3. 任务分配
        results = []
        if "Evidence_Agent" in decision["route"]:
            results.append(run_evidence_agent(std_query)) 
        if "Workflow_Agent" in decision["route"]:
            results.append(run_workflow_agent(std_query))
        
        # 4. 直接返回结果
        return "\n\n".join(results)
        
    except Exception as e:
        return f"🤖 TiAgent 运行异常: {str(e)}"

# ---------------------------------------------------------
# 4. 自动生成简短对话标题 (新增)
# ---------------------------------------------------------
def generate_session_title(user_query):
    """根据用户的第一句话，调用 LLM 生成 10 个字以内的简短标题"""
    api_key = os.getenv("BIANXIE_AI_API_KEY")
    if not api_key:
        return user_query[:10] + "..."  # 兜底：直接截取前10个字
        
    client = OpenAI(
        api_key=api_key,
        base_url="https://api.bianxie.ai/v1"
    )
    
    # 巧妙的 Prompt：逼迫模型只输出核心词
    prompt = f"Extract the core keywords from the user input below to generate a very short conversation title. Strictly limit it to 10 words or fewer. Output ONLY the title text—do not include any punctuation, quotation marks, or explanations.\nUser Input: {user_query}\nTitle:"
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20,
            temperature=0.3 # 降低随机性，让标题更准确
        )
        title = response.choices[0].message.content.strip()
        # 清理可能误生成的标点符号
        title = title.replace('"', '').replace('”', '').replace('“', '').replace('《', '').replace('》', '')
        return title
    except Exception:
        # 如果调用失败，静默降级为直接截取
        return user_query[:10] + "..."