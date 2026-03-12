import pandas as pd
import sqlite3
import uuid
import os
import re
from io import StringIO
from pathlib import Path

# --- 1. 定义文件路径和数据库保存路径 ---
# CSV 文件所在的相对路径
FILE_PATHS = {
    'celltype': './database/data/celltype.csv',
    'spatial': './database/data/spatialayer.csv',
    'tool': './database/data/tools.csv',
    'experiment': './database/data/experiment.csv'
}

# 数据库文件保存路径：指定为 database/database.db
DB_PATH = Path('./database/database.db')

# --- 2. 数据处理：添加 db_id (PK) 和 chunk_id (RAG Key) ---

def process_dataframe(df, prefix):
    """为 DataFrame 添加内部主键 db_id 和 RAG 关联键 chunk_id。"""
    df = df.copy().fillna('') 
    df = df.reset_index(drop=True)
    
    # db_id: 内部自增主键 (用于SQLite内部优化)
    df.insert(0, 'db_id', df.index + 1)
    
    # chunk_id: RAG 关联键 (用于向量数据库链接)
    df.insert(1, 'chunk_id', [f"{prefix}_{uuid.uuid4().hex[:8]}" for _ in range(len(df))])
    
    return df

# --- 3. 数据库连接与表创建函数 ---

def clean_column_name(col_name):
    """清理列名，移除特殊字符，确保 SQLite 兼容性"""
    cleaned = re.sub(r'[()\-\s/\\\,]+', '_', col_name).strip('_')
    return cleaned

def create_table_from_df(conn, df, table_name, pk_col='db_id', business_id_col=None):
    """
    创建 SQLite 表，支持内部主键 (db_id) 和业务唯一索引 (如 CTID, SLID)。
    """
    
    # 统一清理列名
    df.columns = [clean_column_name(col) for col in df.columns]
    
    sql_cols = []
    
    for col in df.columns:
        col_name_cleaned = clean_column_name(col)
        
        if col_name_cleaned == pk_col:
            # 内部自增主键
            sql_cols.append(f'"{col_name_cleaned}" INTEGER PRIMARY KEY')
        elif col_name_cleaned in ['PMID', 'year']: 
            # 数字类型
            sql_cols.append(f'"{col_name_cleaned}" INTEGER')
        elif col_name_cleaned == business_id_col:
            # 业务 ID (您的 CTID/SLID)，设为 TEXT 并添加 UNIQUE 约束
            sql_cols.append(f'"{col_name_cleaned}" TEXT UNIQUE')
        else:
            # 默认 TEXT
            sql_cols.append(f'"{col_name_cleaned}" TEXT')
    
    create_stmt = f'CREATE TABLE IF NOT EXISTS "{table_name}" ({", ".join(sql_cols)})'
    
    # 执行创建表
    conn.execute(create_stmt)
    # 使用 to_sql 导入数据
    df.to_sql(table_name, conn, if_exists='append', index=False)
    
    print(f"✅ 表 '{table_name}' 创建并导入成功，共 {len(df)} 条记录。")


# --- 主执行函数 ---
def setup_database_with_business_keys():
    """读取文件、处理数据并搭建 SQLite 数据库，并指定保存路径。"""
    
    dataframes = {}
    
    # 1. 数据加载：尝试从指定路径读取，失败则使用模拟内容
    for key, path in FILE_PATHS.items():
        try:
            # 尝试从指定路径读取
            dataframes[key] = pd.read_csv(path, keep_default_na=False).fillna('')
        except FileNotFoundError:
            # 如果本地路径读取失败，则使用模拟内容
            print(f"警告: 文件 {path} 未找到，使用模拟内容继续。")
            dataframes[key] = pd.read_csv(StringIO(FILE_CONTENTS[key]), keep_default_na=False).fillna('')
        except Exception as e:
            print(f"加载文件 {path} 失败: {e}")
            return

    # 2. 数据处理
    df_celltype_processed = process_dataframe(dataframes['celltype'], 'CT')
    df_spatial_processed = process_dataframe(dataframes['spatial'], 'SL')
    df_tool_processed = process_dataframe(dataframes['tool'], 'TL')
    df_experiment_processed = process_dataframe(dataframes['experiment'], 'EX')
    print("数据处理完成：已为四个表添加 db_id 和 chunk_id。")

    # 3. 数据库目录创建与连接
    db_dir = DB_PATH.parent
    if not db_dir.exists():
        db_dir.mkdir(parents=True, exist_ok=True)
        print(f"已创建数据库目录: {db_dir}")

    # 4. 删除旧数据库文件（可选，用于测试环境）
    if DB_PATH.exists():
        os.remove(DB_PATH)
        print(f"已删除旧的数据库文件: {DB_PATH}")

    # 连接数据库
    conn = sqlite3.connect(DB_PATH)

    # 5. 导入数据到 SQLite 表 (设置业务 ID 约束)
    create_table_from_df(conn, df_celltype_processed, 'CellType_Phenotype', business_id_col='CTID')
    create_table_from_df(conn, df_spatial_processed, 'Spatial_Phenotype', business_id_col='SLID')
    
    # Tool 和 Experiment 使用默认的 db_id 作为唯一性保证
    create_table_from_df(conn, df_tool_processed, 'Tool_Catalog')
    create_table_from_df(conn, df_experiment_processed, 'Experiment_Protocol')

    conn.close()

    # 6. 验证与总结
    print(f"\n🎉 结构化数据库搭建成功！文件保存路径为: {DB_PATH.resolve()}")

    # 示例验证
    conn_check = sqlite3.connect(DB_PATH)
    print("\n--- CellType_Phenotype 表结构验证 (CTID/SLID 为 UNIQUE 索引) ---")
    query_df = pd.read_sql_query("PRAGMA table_info(CellType_Phenotype)", conn_check)
    print(query_df[['name', 'type', 'pk']].to_markdown(index=False))
    query_df = pd.read_sql_query("PRAGMA table_info(Spatial_Phenotype)", conn_check)
    print(query_df[['name', 'type', 'pk']].to_markdown(index=False))
    query_df = pd.read_sql_query("PRAGMA table_info(Tool_Catalog)", conn_check)
    print(query_df[['name', 'type', 'pk']].to_markdown(index=False))
    query_df = pd.read_sql_query("PRAGMA table_info(Experiment_Protocol)", conn_check)
    print(query_df[['name', 'type', 'pk']].to_markdown(index=False))
    conn_check.close()
    
# 执行数据库搭建
if __name__ == "__main__":
    setup_database_with_business_keys()