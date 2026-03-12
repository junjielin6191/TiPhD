# 文件名: run_agent.py

import os
import json
from pathlib import Path
from typing import Any, Dict, List

# --- 导入核心模块 ---
# env_desc.py 和 llm.py 假定位于项目根目录
from env_desc import library_content_dict
from llm import get_llm

# 根据您的目录结构进行导入
from know_how.loader import KnowHowLoader
from model.retriever import ToolRetriever
from agent.planner_agent import PlannerAgent


# --- 配置 ---
# 统一使用您的 gpt-4o 模型
RETRIEVAL_MODEL = "gpt-4o" 
PLANNER_MODEL = "gpt-4o" 
TEMPERATURE = 0.0

# 1. 获取 API KEY
# 强烈建议通过环境变量 BIANXIE_AI_API_KEY 设置您的密钥
BIANXIE_AI_API_KEY = os.getenv("BIANXIE_AI_API_KEY") 

if not BIANXIE_AI_API_KEY:
    print("\n" + "=" * 60)
    print("🚨 致命错误：API 密钥未设置！")
    print("请设置环境变量 'export BIANXIE_AI_API_KEY='YOUR_SECRET_KEY' ")
    print("或在代码中手动填入您的密钥。")
    print("=" * 60 + "\n")
    exit() # 退出，因为没有密钥无法运行

def run_interaction(user_query: str, api_key: str):
    """
    运行 Agent 的动态知识检索和规划流程。
    """
    print("=" * 60)
    print(f"🤖 正在处理查询: {user_query}")
    print("=" * 60)
    
    # --- 1. 初始化资源加载器 ---
    print("📜 1. 正在加载 Know-How 文档...")
    know_how_dir = str(Path(__file__).parent / "know_how")
    loader = KnowHowLoader(know_how_dir=know_how_dir)
    know_how_docs = loader.get_all_documents()
    
    # --- 2. 准备所有可用资源 ---
# --- run_agent.py ---

# 找到构建 all_resources 的位置，修改如下：
# 1. 动态准备所有可用资源
    all_resources = {
        "tools": [
            # 优化：带上【工具名】，并包含 [R Package]
            f"【{name}】: {desc}" 
            for name, desc in library_content_dict.items() 
            if any(tag in desc for tag in ["[CLI Tool]", "[Python Package]", "[R Package]"])
        ],
        "data_lake": [
            f"【{name}】: {desc}"
            for name, desc in library_content_dict.items() 
            if name.endswith(('.parquet', '.tsv', '.csv', '.pkl'))
        ],
        "libraries": [], 
        "know_how": [
            {"id": doc['id'], "description": doc['description'], "content": doc['content']}
            for doc in know_how_docs
        ],
    }
    
    total_resources = sum(len(v) for k, v in all_resources.items())
    print(f"   - 成功加载 {total_resources} 个资源。")

    # --- 3. 初始化 LLM 实例 ---
    # 传递 API Key 给 get_llm
    print(f"🧠 LLM初始化: 模型 {PLANNER_MODEL}。")
    retriever_llm = get_llm(model=RETRIEVAL_MODEL, temperature=TEMPERATURE, api_key=api_key)

    # --- 4. 运行动态知识检索 (ToolRetriever) ---
    print("\n🔍 2. 正在执行动态知识检索 (Filtering)...")
    retriever = ToolRetriever()
    
    # 使用 LLM 结构化输出（在 model/retriever.py 中实现）
    retrieved_resources = retriever.prompt_based_retrieval(
        query=user_query,
        resources=all_resources,
        llm=retriever_llm, # 传入已实例化的 LLM
    )
    
    retrieved_count = sum(len(v) for k, v in retrieved_resources.items())
    print(f"   - 检索完成：共筛选出 {retrieved_count} 个高度相关资源。")
    for key, value in retrieved_resources.items():
         if value:
            print(f"     - {key.upper()}: 选中 {len(value)} 个。")

    # --- 5. 运行 Agent 规划 (PlannerAgent) ---
    print("\n📝 3. 正在生成结构化分析计划...")
    
    # 关键：PlannerAgent 必须接收 api_key 并传递给其父类 BaseAgent
    # 确保您的 agent/base_agent.py 构造函数 (BaseAgent.__init__) 能够接收并传递 api_key 到 get_llm。
    planner = PlannerAgent(
        llm=PLANNER_MODEL, 
        temperature=TEMPERATURE,
        api_key=api_key # 确保 BaseAgent 能处理这个参数！
    )
    
    # 运行规划，传入检索结果作为上下文
    final_plan_json = planner.go(user_query, retrieved_resources)

    # --- 6. 输出结果 ---
    print("\n" + "#" * 60)
    print("✅ 最终结构化分析计划 (Structured Analysis Plan)")
    print("#" * 60)
    # 假设 final_plan_json 是一个 JSON 字符串，格式化后输出
    try:
        print(json.dumps(json.loads(final_plan_json), indent=2, ensure_ascii=False))
    except Exception:
        print(final_plan_json) # 如果不是有效JSON，直接输出
    print("\n--- 流程结束 ---")
import json
from pathlib import Path

def _prepare_tool_resources(self) -> Dict[str, List[Any]]:
    """
    构建 Workflow_Agent 资源池：整合无标签工具与 experiment_records.json 实验库
    """
    tools = []
    libraries = []
    
    # 1. 处理计算工具：增加关键词补偿逻辑以识别 Seurat, ABSOLUTE 等无标签工具
    tags = ["[CLI Tool]", "[Python Package]", "[R Package]"]
    tool_keywords = ["software", "package", "tool", "method", "algorithm", "pipeline", "toolkit"]
    core_lib_keywords = ["Data Science", "scientific computing", "visualization", "data manipulation"]

    for name, desc in library_content_dict.items():
        if name.endswith(('.parquet', '.tsv', '.csv', '.pkl')): continue # 排除数据文件
        
        formatted_entry = f"【{name}】: {desc}"
        # 识别逻辑：包含明确标签 OR 描述中包含工具类关键词
        is_tool = any(tag in desc for tag in tags) or any(kw in desc.lower() for kw in tool_keywords)
        
        if is_tool:
            if any(core in desc for core in core_lib_keywords):
                libraries.append(formatted_entry)
            else:
                tools.append(formatted_entry)
        else:
            libraries.append(formatted_entry)

    # 2. 整合 experiment_records.json 中的湿实验协议
    # 路径指向 Paper_Agent 下的数据库文件
    exp_path = Path(__file__).parent.parent / "Paper_Agent" / "database" / "data" / "json" / "experiment_records.json"
    combined_know_how = []
    
    # 加入原有的 Markdown 指南
    for doc in self.know_how_docs:
        combined_know_how.append({"id": doc['id'], "description": doc['description'], "content": doc['content']})

    # 解析结构化实验记录
    if exp_path.exists():
        with open(exp_path, 'r', encoding='utf-8') as f:
            for rec in json.load(f):
                combined_know_how.append({
                    "id": f"Protocol: {rec.get('Experimental_Design')}",
                    "description": f"Target: {rec.get('Purpose')}. Layer: {rec.get('Spatiallayer')}",
                    "content": f"Methodology: {rec.get('Methodology')}\nKey Analyses: {rec.get('Key_Analyses')}"
                })

    return {"tools": tools, "libraries": libraries, "know_how": combined_know_how}

# File: run_agent.py (在 if __name__ == "__main__": 块内部)

# 假设 run_interaction 和 BIANXIE_AI_API_KEY 已经定义

# File: run_agent.py (在 if __name__ == "__main__": 块内部)

# 假设 run_interaction 和 BIANXIE_AI_API_KEY 已经定义

if __name__ == "__main__":
    
    # ------------------------------------------------------------
    # 开启多轮交互循环
    # ------------------------------------------------------------
    print("============================================================")
    print("欢迎使用 TiAgent 命令行交互模式。输入 'exit' 或 'quit' 退出。")
    print("============================================================")
    
    # 【注意】：如果您需要跨轮次保持 Agent 状态，您可能需要将 PlannerAgent 的实例化
    # 移动到 while 循环之外，并修改 run_interaction 来接收 Agent 实例。
    
    while True:
        # 从终端获取用户输入
        user_query = input("\n请输入您的查询: ").strip()
        
        if user_query.lower() in ['exit', 'quit']:
            print("再见！TiAgent 会话结束。")
            break
        
        if not user_query:
            continue
            
        print("============================================================")
        print(f"🤖 正在处理查询: {user_query}")
        print("============================================================")
        
        # 调用交互函数
        run_interaction(user_query, api_key=BIANXIE_AI_API_KEY)
        
        print("\n--- 流程结束 (继续下一轮交互) ---")