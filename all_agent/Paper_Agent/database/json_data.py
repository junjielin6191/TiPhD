import pandas as pd
import uuid
import os
import re
from io import StringIO
from pathlib import Path
import json

# --- 1. 配置和路径定义 ---
FILE_PATHS = {
    'celltype': './database/data/celltype.csv',
    'spatial': './database/data/spatialayer.csv',
    'tool': './database/data/tools.csv',
    'experiment': './database/data/experiment.csv'
}
JSON_OUTPUT_DIR = Path('./database/data/json/')

# --- 2. 辅助函数（与结构化数据库部分保持一致） ---

def clean_column_name(col_name):
    """清理列名，确保 DataFrame 和 JSON 键兼容性"""
    return re.sub(r'[()\-\s/\\\,]+', '_', col_name).strip('_')

def process_dataframe(df, prefix):
    """为 DataFrame 添加 db_id 和 chunk_id 并清理列名"""
    df = df.copy()
    df.columns = [clean_column_name(col) for col in df.columns]
    # 注意：这里我们不fillna('')，保持原始数据类型，让JSON导出更准确
    df = df.reset_index(drop=True)
    df.insert(0, 'db_id', df.index + 1)
    df.insert(1, 'chunk_id', [f"{prefix}_{uuid.uuid4().hex[:8]}" for _ in range(len(df))])
    return df

def load_data():
    """读取指定路径下的 CSV 文件内容（使用模拟内容以确保运行）"""
    dataframes = {}
    
    # 模拟文件内容（替换为您的实际内容，此处使用前面步骤获取的内容）
    # 实际运行时，此部分代码应尝试读取 FILE_PATHS 中的文件
    
    # 假设文件内容已通过某种方式获取并存储在变量中（这里使用占位符）
    file_content = {
        'celltype': Path(FILE_PATHS['celltype']).read_text(encoding='utf-8') if Path(FILE_PATHS['celltype']).exists() else Path('celltype.csv').read_text(encoding='utf-8'),
        'spatial': Path(FILE_PATHS['spatial']).read_text(encoding='utf-8') if Path(FILE_PATHS['spatial']).exists() else Path('spatialayer.csv').read_text(encoding='utf-8'),
        'tool': Path(FILE_PATHS['tool']).read_text(encoding='utf-8') if Path(FILE_PATHS['tool']).exists() else Path('tools.csv').read_text(encoding='utf-8'),
        'experiment': Path(FILE_PATHS['experiment']).read_text(encoding='utf-8') if Path(FILE_PATHS['experiment']).exists() else Path('experiment.csv').read_text(encoding='utf-8')
    }
    
    for key in FILE_PATHS.keys():
        try:
            # 尝试读取并处理数据
            df = pd.read_csv(StringIO(file_content[key]), keep_default_na=False)
            dataframes[key] = df
            print(f"✅ 文件 {key}.csv 加载成功。")
        except Exception as e:
            print(f"❌ 文件 {key}.csv 加载失败: {e}")
            return None

    # 3. 数据预处理
    dataframes['celltype'] = process_dataframe(dataframes['celltype'], 'CT')
    dataframes['spatial'] = process_dataframe(dataframes['spatial'], 'SL')
    dataframes['tool'] = process_dataframe(dataframes['tool'], 'TL')
    dataframes['experiment'] = process_dataframe(dataframes['experiment'], 'EX')
    
    return dataframes

# --- 4. 核心功能：JSON 转换函数 ---

def convert_and_save_json(dataframes):
    """根据不同策略将 DataFrame 转换为 JSON 文件并保存。"""
    
    # 确保输出目录存在
    JSON_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"\n--- 正在将数据转换为 JSON 并保存至 {JSON_OUTPUT_DIR.resolve()} ---")

    # 4.1 策略一：按行转化为 JSON 结构体 (用于 CellType 和 SpatialLayer)
    # 每个元素是一个完整的记录，适合直接作为 Metadata
    
    # CellType_Phenotype
    celltype_json = dataframes['celltype'].to_dict(orient='records')
    with open(JSON_OUTPUT_DIR / 'celltype_records.json', 'w', encoding='utf-8') as f:
        json.dump(celltype_json, f, ensure_ascii=False, indent=4)
    print(f"✅ celltype_records.json (共 {len(celltype_json)} 条记录) 保存成功。")

    # Spatial_Phenotype
    spatial_json = dataframes['spatial'].to_dict(orient='records')
    with open(JSON_OUTPUT_DIR / 'spatial_records.json', 'w', encoding='utf-8') as f:
        json.dump(spatial_json, f, ensure_ascii=False, indent=4)
    print(f"✅ spatial_records.json (共 {len(spatial_json)} 条记录) 保存成功。")
    
    # Tool_Catalog
    tool_json = dataframes['tool'].to_dict(orient='records')
    with open(JSON_OUTPUT_DIR / 'tool_records.json', 'w', encoding='utf-8') as f:
        json.dump(tool_json, f, ensure_ascii=False, indent=4)
    print(f"✅ tool_records.json (共 {len(tool_json)} 条记录) 保存成功。")
    
    # Experiment_Protocol
    experiment_json = dataframes['experiment'].to_dict(orient='records')
    with open(JSON_OUTPUT_DIR / 'experiment_records.json', 'w', encoding='utf-8') as f:
        json.dump(experiment_json, f, ensure_ascii=False, indent=4)
    print(f"✅ experiment_records.json (共 {len(experiment_json)} 条记录) 保存成功。")
    
# --- 主执行函数 ---
def run_json_conversion():
    
    dataframes = load_data()
    
    if dataframes is None:
        print("由于数据加载失败，终止 JSON 转换。")
        return

    convert_and_save_json(dataframes)
    
    print("\n🎉 所有表格已成功转换为 JSON 文件，并保存在 ./database/data/json/ 目录下。")

# 执行转换
if __name__ == "__main__":
    run_json_conversion()