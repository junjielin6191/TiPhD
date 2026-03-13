import json
from openai import OpenAI
from Evidence_Agent.main import run_evidence_agent
from Workflow_Agent.run_agent import run_workflow_agent

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
    3. Standardization: Output a complete, standalone English query that conforms to Biomedical Ontologies.
    
    User-Specific History:
    {history_str}
    
    Current User Input: {user_query}
    
    Standardized English Query:"""
    
    # ... 调用 OpenAI ...
    response = client.chat.completions.create(
        model="gpt-4o", # 或你的模型
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
    - [General]: Greetings, introductions, or non-technical chat. Provide the response directly.
    - [Evidence_Agent]: Retrieval of biological facts, literature, or database records.
    - [Workflow_Agent]: Experimental protocols, bioinformatics workflows, or code generation.
    
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
# 3. 总控运行逻辑（删除翻译步骤）
# ---------------------------------------------------------
# 删掉原本的 global_memory = Memory() 这一行

def run_tiagent(user_input, history_str):
    """
    history_str 是 app.py 从数据库中提取的、属于该用户的特定历史。
    """
    client = OpenAI(api_key="你的API_KEY")

    # 1. Language Agent 使用用户专属的历史进行“语义消解”
    # 比如用户在自己的历史里提过 TAMs，这里就会根据 history_str 解析出来
    std_query = language_agent_standardize(client, user_input, history_str)

    # 2. 路由决策 (同之前逻辑)
    decision = master_orchestrate(client, std_query)
    
    if "General" in decision["route"]:
        # 自由回答：例如打招呼、身份介绍，直接返回 direct_response
        return decision.get("direct_response", "我是 TiAgent，您的生物医学研究助理。")

    # 3. 任务分配
    results = []
    if "Evidence_Agent" in decision["route"]:
        results.append(run_evidence_agent(std_query)) # 传入标准化后的英文词
    if "Workflow_Agent" in decision["route"]:
        results.append(run_workflow_agent(std_query))
    
    # 4. 直接返回结果（不再强行翻译回中文，保留原始专业度）
    return "\n\n".join(results)