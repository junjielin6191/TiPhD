# 文件名: run_agent.py

import os
import json
from pathlib import Path
from typing import Any, Dict, List

# --- 导入核心模块 ---
from Workflow_Agent.env_desc import library_content_dict
from Workflow_Agent.llm import get_llm
from Workflow_Agent.know_how.loader import KnowHowLoader
from Workflow_Agent.model.retriever import ToolRetriever
from Workflow_Agent.agent.planner_agent import PlannerAgent
from Workflow_Agent.config import default_config  # 导入配置
# --- 配置 ---


# 1. 获取 API KEY (使用硬编码或环境变量)
BIANXIE_AI_API_KEY = os.getenv("BIANXIE_AI_API_KEY", "sk-GBBQQWHSKHU76HFS5tsHmmffzbQi1dnLy5VdnPU6Kp9gtm3n")
API_BASE = "https://api.bianxie.ai/v1" 
TEMPERATURE=default_config.temperature

def _prepare_resources() -> Dict[str, List[Any]]:
    """
    构建 Workflow_Agent 资源池：整合无标签工具与 experiment_records.json 实验库
    """
    tools = []
    libraries = []
    
    # 1. 处理计算工具：直接加载所有数据，移除标签和关键词判断逻辑
    for name, desc in library_content_dict.items():
        if name.endswith(('.parquet', '.tsv', '.csv', '.pkl')): 
            continue 
            
        formatted_entry = f"【{name}】: {desc}"
        # 直接将所有条目无差别加载到 tools 列表中
        tools.append(formatted_entry) 

    # 2. 整合实验协议与指南
    know_how_dir = str(Path(__file__).parent / "know_how")
    loader = KnowHowLoader(know_how_dir=know_how_dir)
    know_how_docs = loader.get_all_documents()
    
    combined_know_how = []
    # 加入原有的 Markdown 指南
    for doc in know_how_docs:
        combined_know_how.append({"id": doc['id'], "description": doc['description'], "content": doc['content']})

    # 解析结构化实验记录 (路径指向 Evidence_Agent 下的数据库文件)
    exp_path = Path(__file__).parent.parent / "Evidence_Agent" / "database" / "data" / "json" / "experiment_records.json"
    if exp_path.exists():
        with open(exp_path, 'r', encoding='utf-8') as f:
            for rec in json.load(f):
                combined_know_how.append({
                    "id": f"Protocol: {rec.get('Experimental_Design', 'Unknown')}",
                    "description": f"Target: {rec.get('Purpose', 'Unknown')}. Layer: {rec.get('Spatiallayer', 'Unknown')}",
                    "content": f"Methodology: {rec.get('Methodology', '')}\nKey Analyses: {rec.get('Key_Analyses', '')}"
                })
    else:
        print(f"⚠️ 警告: 找不到实验记录文件 {exp_path}")

    return {"tools": tools, "libraries": libraries, "know_how": combined_know_how}


# =====================================================================
# 🌟 新增：供总控 (tiagent_master.py) 调用的统一入口函数
# =====================================================================
def run_workflow_agent(user_query: str) -> str:
    """
    接收 master 传来的 query，执行动态知识检索和规划流程，返回最终字符串结果。
    """
    if not BIANXIE_AI_API_KEY:
        return "🚨 致命错误：API 密钥未设置！请在代码中配置 BIANXIE_AI_API_KEY。"

    print("=" * 60)
    print(f"🤖 [Workflow Agent] 正在处理查询: {user_query}")
    print("=" * 60)
    
    try:
        # 1. 准备所有可用资源
        print("📜 1. 正在加载 工具库 与 Know-How 文档...")
        all_resources = _prepare_resources()
        total_resources = sum(len(v) for k, v in all_resources.items())
        print(f"   - 成功加载 {total_resources} 个资源。")

        # 2. 初始化 LLM 实例
        print(f"🧠 LLM初始化: 模型 {default_config.retrieval_model}。")
        retriever_llm = get_llm(model=default_config.retrieval_model, temperature=TEMPERATURE, api_key=BIANXIE_AI_API_KEY)

        # 3. 运行动态知识检索 (ToolRetriever)
        print("\n🔍 2. 正在执行动态知识检索 (Filtering)...")
        retriever = ToolRetriever()
        retrieved_resources = retriever.prompt_based_retrieval(
            query=user_query,
            resources=all_resources,
            llm=retriever_llm
        )
        
        # 4. 运行 Agent 规划 (PlannerAgent)
        print("\n📝 3. 正在生成结构化分析计划...")
        planner = PlannerAgent(
            llm=default_config.planner_model, 
            temperature=TEMPERATURE,
            api_key=BIANXIE_AI_API_KEY 
        )
        
        # 5. 生成并返回结果
        final_plan_json = planner.go(user_query, retrieved_resources)
        
        # 尝试美化 JSON 字符串输出
        try:
            parsed_json = json.loads(final_plan_json)
            return json.dumps(parsed_json, indent=2, ensure_ascii=False)
        except Exception:
            # 如果解析失败，直接返回原始字符串
            return str(final_plan_json)
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Workflow Agent 执行过程中发生错误: {str(e)}"


# =====================================================================
# 本地测试模块 (单独运行此文件时触发)
# =====================================================================
if __name__ == "__main__":
    print("============================================================")
    print("欢迎使用 Workflow Agent 命令行交互模式。输入 'exit' 或 'quit' 退出。")
    print("============================================================")
    
    while True:
        query = input("\n请输入您的查询: ").strip()
        
        if query.lower() in ['exit', 'quit']:
            print("再见！会话结束。")
            break
        
        if not query:
            continue
            
        result = run_workflow_agent(query)
        
        print("\n" + "#" * 60)
        print("✅ 最终结构化分析计划 (Structured Analysis Plan)")
        print("#" * 60)
        print(result)
        print("\n--- 流程结束 (继续下一轮交互) ---")