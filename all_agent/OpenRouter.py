import json
import os
import time
import random
import pandas as pd
from pathlib import Path
from openai import OpenAI

# ==========================================
# 1. 配置区域 (Configuration)
# ==========================================
BASE_PATH = Path("/mnt/data/ljj/Project_TiPhD/TiAgent/all_agent")
INPUT_FILE = BASE_PATH / "test_query.xlsx"
OUTPUT_EXCEL = BASE_PATH / "2.11retest_openrouter_results.xlsx"
OUTPUT_JSON = BASE_PATH / "2.11retest_openrouter_results.json"  # 新增 JSON 输出路径

OPENROUTER_API_KEY = "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"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

RETEST_MODELS = [
    #"qwen/qwen3-next-80b-a3b-instruct:free"
    "google/gemma-3n-e2b-it:free",
    #"google/gemma-3-27b-it:free",
    #"google/gemma-3-12b-it:free",
    #"google/gemma-3-4b-it:free",
    #"tngtech/deepseek-r1t-chimera:free"
]

class OpenRouterSpecialTester:
    def __init__(self):
        print(f"📡 初始化 OpenRouter 客户端...")
        self.client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
        )

    def get_response(self, model_name: str, query: str, max_retries=5) -> str:
        """核心调用逻辑：包含 429 异常处理与自动重试"""
        system_prompt = (
        "You are a professional bioinformatics expert. Provide a detailed workflow or experimental design based on your internal knowledge."
        )
        
        for i in range(max_retries):
            try:
                response = self.client.chat.completions.create(

                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": query}
                    ],
                    temperature=0.7
                )
                return response.choices[0].message.content
            
            except Exception as e:
                error_str = str(e)
                # 如果触发频率限制 (429) 或 Provider 错误
                if "429" in error_str or "Provider returned error" in error_str:
                    # 指数退避等待
                    wait_time = (2 ** (i + 2)) + random.uniform(1, 3)
                    print(f"   ⚠️ 接口繁忙 ({model_name})，{wait_time:.1f}s 后进行第 {i+1} 次重试...")
                    time.sleep(wait_time)
                    continue
                else:
                    return f"Error: {error_str}"
        
        return "Error: Maximum retries exceeded due to rate limiting."

    def _get_short_name(self, model_full_name: str) -> str:
        """辅助函数：根据模型全名生成简短标识"""
        if "qwen" in model_full_name.lower():
            return "qwen"
        elif "gemma" in model_full_name.lower():
            return "gemma"
        elif "deepseek" in model_full_name.lower():
            return "deepseek_r1" # 区分这个 DeepSeek
        else:
            # 如果有新模型，默认取第一段名字
            return model_full_name.split('/')[1].split(':')[0]

    def run_retest(self, df: pd.DataFrame):
        """执行测试循环，包含强制冷却时间"""
        results = []
        for index, row in df.iterrows():
            q_id = row.get('id', index)
            query = row['query']
            print(f"\n🔍 [Testing] ID {q_id}: {query[:40]}...")
            
            res_entry = {"id": q_id, "query": query}
            
            for model in RETEST_MODELS:
                print(f"   -> Calling {model}...")
                start_time = time.time()
                
                answer = self.get_response(model, query)
                latency = round(time.time() - start_time, 2)
                
                # 修复点 1：使用动态生成的唯一列名
                short_name = self._get_short_name(model)
                res_entry[f"answer_{short_name}"] = answer
                res_entry[f"latency_{short_name}"] = latency

                # 模型间冷却
                time.sleep(2)
                
            results.append(res_entry)
            
            # Query 间冷却
            print(f"   ⏳ 完成 ID {q_id}，进入 5s 强制冷却期...")
            time.sleep(5)
            
        return results

# ==========================================
# 2. 执行主程序
# ==========================================
if __name__ == "__main__":
    if not INPUT_FILE.exists():
        print(f"❌ 错误：找不到输入文件 {INPUT_FILE}")
    else:
        df_analysis = pd.read_excel(INPUT_FILE, sheet_name='analysis')
        tester = OpenRouterSpecialTester()
        
        # 执行测试
        test_results = tester.run_retest(df_analysis)
        
        # 保存 Excel
        res_df = pd.DataFrame(test_results)
        
        # 在合并前，先把多余的 id/query 列去掉，防止重复
        cols_to_merge = [col for col in res_df.columns if col not in ['id', 'query']]
        final_df = pd.merge(df_analysis, res_df[['id'] + cols_to_merge], on='id', how='left')
        
        final_df.to_excel(OUTPUT_EXCEL, index=False)
        print(f"\n✅ Excel 结果已保存至: {OUTPUT_EXCEL}")

        # 修复点 2：添加 JSON 保存
        with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
            json.dump(test_results, f, ensure_ascii=False, indent=2)
        print(f"✅ JSON 结果已保存至: {OUTPUT_JSON}")