import pandas as pd
import numpy as np
import json
import os
from pathlib import Path
import sys
# 1. 引入 OpenAI 客户端
try:
    from openai import OpenAI 
    # 额外引入 API 异常类型，以便更精准捕获
    from openai import APIError
except ImportError:
    print("❌ 错误：请安装 openai 库：pip install openai")
    sys.exit(1)

# 尝试导入 faiss
try:
    import faiss
except ImportError:
    faiss = None
    # 注意：我们在这里不退出，允许代码在没有 faiss 的情况下运行并保存 JSON
    
# --- 1. 配置和路径定义 ---
JSON_INPUT_DIR = Path('./database/data/json')
JSON_FILE_NAMES = {
    'celltype': 'celltype_records.json',
    'spatial': 'spatial_records.json',
    'tool': 'tool_records.json',
    'experiment': 'experiment_records.json'
}

# 🛠️ 关键配置：text-embedding-3-large 模型参数
EMBEDDING_MODEL = 'text-embedding-3-large'
EMBEDDING_DIMENSION = 3072  
VECTOR_INDEX_FILE = 'rag_knowledge_index.faiss'
RAG_DATA_JSON = 'rag_knowledge_data.json'

# ⚠️ 用户提供的配置，覆盖环境变量，用于知识块生成和向量化
API_KEY_OVERRIDE = 'sk-GBBQQWHSKHU76HFS5tsHmmffzbQi1dnLy5VdnPU6Kp9gtm3n'
API_BASE_OVERRIDE = 'https://api.bianxie.ai/v1' # 已添加 /v1 路径后缀，以兼容 OpenAI 格式


# --- 2. 核心功能：数据加载与展平 (小幅优化) ---

def load_and_normalize_json():
    """加载 JSON 文件，假定所有文件都是记录列表格式。"""
    
    normalized_data = {}
    
    for filename_key, filename in JSON_FILE_NAMES.items():
        filepath = JSON_INPUT_DIR / filename
        
        if not filepath.exists():
            print(f"❌ 错误：未找到 JSON 文件 {filepath}，请检查路径和文件名。")
            sys.exit(1)

        with open(filepath, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"❌ 错误：文件 {filepath} 格式错误，无法解析。")
                sys.exit(1)

        # 优化：由于所有文件都是 records 格式，无需冗余的 if/elif 检查
        if not isinstance(data, list):
            print(f"⚠️ 警告：文件 {filename} 内容预期为列表，但加载结果不是列表。")
            
        normalized_data[filename_key] = data
        
        print(f"✅ JSON 文件 {filename} 加载成功，共 {len(normalized_data[filename_key])} 条记录。")

    return normalized_data

# --- 3. 核心功能：知识块生成函数 (保持一致，已包含所有字段) ---

def generate_rag_chunks(data):
    """
    根据输入的四个 JSON 结构数据，生成 RAG 知识块 (Chunk Text) 和 Metadata。
    """
    
    rag_knowledge_base = []

    # --- 1. CellType_Phenotype 知识块生成 ---
    for row in data.get('celltype', []):
        # A. 身份与来源信息 (ID, 文献)
        identity_info = (
            f"PMID: {row.get('PMID', 'N/A')}, 文献标题: {row.get('Paper_Title', 'N/A')}, "
            f"期刊: {row.get('journal', 'N/A')}, 研究年份: {row.get('year', 'N/A')}."
        )
        # B. 生物背景 (物种, 组织, 癌症类型)
        context_info = (
            f"物种: {row.get('species', 'N/A')}, 组织类型: {row.get('tissue_class', 'N/A')}/{row.get('tissue_type', 'N/A')}. "
            f"主要癌症类型: {row.get('main_cancer_type', 'N/A')}, 详细癌症类型: {row.get('cancer_type_detail', 'N/A')}."
        )
        # C. 细胞详情 (大类, 小类, 标志物)
        cell_info = (
            f"细胞大类: {row.get('big_cell_type', 'N/A')}, 细胞小类: {row.get('major_cell_type', 'N/A')}, "
            f"具体细胞名称: {row.get('cell_name', 'N/A')}. "
            f"关键细胞标志物: {row.get('cell_marker', 'N/A')}."
        )
        # D. 表型与结果 (类型, 标签, 关联)
        phenotype_info = (
            f"表型类型: {row.get('Phenotype_type', 'N/A')}, 主要表型标签: {row.get('main_Phenotype_label', 'N/A')}, "
            f"具体表型结果: {row.get('Phenotype_label', 'N/A')}, 如何影响表型: {row.get('Association_Type', 'N/A')}."
        )
        # E. 研究方法和证据类型 (发现, 验证, 样本)
        method_info = (
            f"发现技术: {row.get('Technology_Type_for_Discovery', 'N/A')}. "
            f"研究模型/样本: {row.get('model_type', 'N/A')}. "
            f"验证技术类型: {row.get('technology_type_for_validation', 'N/A')}. "
            f"证据级别: {row.get('evidence_type', 'N/A')}."
        )
        # F. 核心证据
        evidence_info = f"核心证据描述: \"{row.get('Phenotype_evidence', '无')}\""
        chunk_text = f"实体类型: 细胞表型. {identity_info} {context_info} {cell_info} {phenotype_info} {method_info} {evidence_info}"
        metadata = {
            "chunk_id": row.get('chunk_id'), "source_table": "CellType_Phenotype", 
            "main_cancer_type": row.get('main_cancer_type'), "cell_name": row.get('cell_name'), "PMID": row.get('PMID'),
            "year": row.get('year'), "Technology_Type_for_Discovery": row.get('Technology_Type_for_Discovery'), "Technology_Type_for_validation": row.get('Technology_Type_for_validation')
        }
        rag_knowledge_base.append({"chunk_id": row.get('chunk_id'), "text": chunk_text, "metadata": metadata})

    # --- 2. Spatial_Phenotype 知识块生成 ---
    for row in data.get('spatial', []):
        identity_info = (f"PMID: {row.get('PMID', 'N/A')}, 文献标题: {row.get('Paper_Title', 'N/A')}, 期刊: {row.get('journal', 'N/A')}, 研究年份: {row.get('year', 'N/A')}." )
        context_info = (f"物种: {row.get('species', 'N/A')}, 组织类型: {row.get('tissue_class', 'N/A')}/{row.get('tissue_type', 'N/A')}. 主要癌症类型: {row.get('main_cancer_type', 'N/A')}, 详细癌症类型: {row.get('cancer_type_detail', 'N/A')}." )
        spatial_info = (f"主要空间层级: {row.get('main_spatial_layer', 'N/A')}, 具体空间结构名称: {row.get('spatial_layer', 'N/A')}. 组成细胞类型: {row.get('Cell_type_composition', 'N/A')}." )
        phenotype_info = (f"表型类型: {row.get('Phenotype_type', 'N/A')}, 主要表型: {row.get('main_Phenotype_label', 'N/A')}, 具体表型: {row.get('Phenotype_label', 'N/A')}." )
        method_info = (f"发现技术: {row.get('technology_type_for_discovery', 'N/A')}.验证技术类型: {row.get('technology_type_for_validation', 'N/A')}. 证据级别: {row.get('evidence_type', 'N/A')}." )
        evidence_info = f"核心证据描述: \"{row.get('Phenotype_evidence', '无')}\""
        chunk_text = f"实体类型: 空间层级表型. {identity_info} {context_info} {spatial_info} {phenotype_info} {method_info} {evidence_info}"
        metadata = {
            "chunk_id": row.get('chunk_id'), "source_table": "Spatial_Phenotype", 
            "main_cancer_type": row.get('main_cancer_type'), "spatial_layer": row.get('main_spatial_layer'), 
            "PMID": row.get('PMID'), "year": row.get('year'), "technology": row.get('technology_type_for_discovery'), "Technology_Type_for_validation": row.get('Technology_Type_for_validation')
        }
        rag_knowledge_base.append({"chunk_id": row.get('chunk_id'), "text": chunk_text, "metadata": metadata})

    # --- 3. Tool_Catalog 知识块生成 ---
    for row in data.get('tool', []):
        tool_info = (f"工具名称: {row.get('Method', 'N/A')}. 主要功能分类: {row.get('Main_function', 'N/A')}. 具体作用: {row.get('Function', 'N/A')}." )
        detail_info = (f"适用技术: {row.get('Technology', 'N/A')}. 功能细节描述: \"{row.get('Function_detail', '无')}\"" )
        citation_info = (f"关联文献PMID: {row.get('PMID', 'N/A')}. 完整论文引用: \"{row.get('Paper', '无')}\". Github链接/资源地址: {row.get('Github', '无')}" )
        chunk_text = f"实体类型: 生物信息学工具. {tool_info} {detail_info} {citation_info}"
        metadata = {
            "chunk_id": row.get('chunk_id'), "source_table": "Tool_Catalog", "tool_name": row.get('Method'),
            "main_function": row.get('Main_function'), "technology": row.get('Technology'), "PMID": row.get('PMID')
        }
        rag_knowledge_base.append({"chunk_id": row.get('chunk_id'), "text": chunk_text, "metadata": metadata})

    # --- 4. Experiment_Protocol 知识块生成 ---
    for row in data.get('experiment', []):
        identity_info = (f"内部ID: {row.get('db_id', 'N/A')}, 业务ID: {row.get('chunk_id', 'N/A')}. 适用空间层级: {row.get('Spatiallayer', 'N/A')}." )
        design_info = (f"实验设计: {row.get('Experimental_Design', 'N/A')}. 具体方法论: {row.get('Methodology', 'N/A')}." )
        purpose_analysis_info = (f"实验目的: \"{row.get('Purpose', '无')}\". 关键分析步骤: \"{row.get('Key_Analyses', '无')}\"" )
        chunk_text = f"实体类型: 实验方法论. {identity_info} {design_info} {purpose_analysis_info}"
        metadata = {
            "chunk_id": row.get('chunk_id'), "source_table": "Experiment_Protocol", "spatial_layer": row.get('Spatiallayer'),
            "design": row.get('Experimental_Design'), "methodology": row.get('Methodology')
        }
        rag_knowledge_base.append({"chunk_id": row.get('chunk_id'), "text": chunk_text, "metadata": metadata})

    return rag_knowledge_base

# --------------------------------------------------------------------------------------------------
# --- 4. 向量化与索引函数 (已更新为用户提供的自定义 API) ---
# --------------------------------------------------------------------------------------------------

def create_openai_embeddings_and_indexing(rag_data):
    """
    使用 OpenAI Embedding 模型生成向量，并创建 FAISS 索引。
    已更新为使用用户提供的自定义 API 终结点。
    """
    
    global faiss # 明确使用全局 faiss 变量
    
    if faiss is None:
        print("\n=== 警告：缺少 FAISS 依赖 ===")
        print("请运行 'pip install faiss-cpu' 安装。当前将跳过索引创建，仅生成 JSON 文件。")
    
    # --- OPENAI CONFIG START (已更新为用户提供的自定义 API) ---
    # 优先使用硬编码的覆盖值，否则尝试从环境变量 OPENAI_API_KEY 读取密钥
    api_key = API_KEY_OVERRIDE or os.environ.get('OPENAI_API_KEY')
    api_base = API_BASE_OVERRIDE or None

    if not api_key:
        print("\n❌ 错误：未找到 API 密钥。请设置 OPENAI_API_KEY 环境变量或在代码中手动指定密钥。")
        sys.exit(1)

    try:
        # 使用提供的基准 URL 和密钥初始化客户端
        client = OpenAI(api_key=api_key, base_url=api_base)
        print(f"✅ OpenAI 客户端初始化成功。使用基准URL: {api_base}")
    except Exception as e:
        print(f"\n❌ 错误：无法初始化 OpenAI 客户端（Embedding 阶段）。请确认 API 密钥和基准 URL 是否正确。详细错误: {e}")
        sys.exit(1)
    # --- OPENAI CONFIG END ---
        
    print(f"\n--- 正在使用 {EMBEDDING_MODEL} (dim={EMBEDDING_DIMENSION}) 模型生成 {len(rag_data)} 条记录的向量 ---")

    # 1. 提取所有知识块文本和 ID 映射
    texts_to_embed = [item['text'] for item in rag_data]
    chunk_id_map = [item['chunk_id'] for item in rag_data]
    
    # 2. 调用 Embedding API
    try:
        response = client.embeddings.create(
            input=texts_to_embed,
            model=EMBEDDING_MODEL
        )
        # 提取向量并转换为 float32 numpy 数组
        vectors = np.array([e.embedding for e in response.data], dtype='float32')
        print(f"✅ 成功从 OpenAI API 获取 {len(vectors)} 个向量。")

    except APIError as e:
        # 捕获 OpenAI API 自身的错误，例如认证失败 (401)、速率限制 (429) 或模型不存在
        print(f"\n❌ 错误：OpenAI API 调用失败 ({e.status_code})。请检查您的 API 密钥、模型名称和网络连接。详细错误: {e}")
        sys.exit(1)
    except Exception as e:
        # 捕获其他非 API 错误 (如网络问题)
        print(f"\n❌ 错误：Embedding API 调用失败。请检查您的网络连接或 Python 环境。详细错误: {e}")
        sys.exit(1)

    # 3. 创建 FAISS 索引
    if faiss:
        if len(vectors) == 0:
            print("⚠️ 警告：没有生成向量，跳过 FAISS 索引创建。")
        else:
            # 使用 IndexFlatL2 创建 L2 距离索引
            index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
            index.add(vectors)
            
            # 4. 保存索引和 ID 映射
            faiss.write_index(index, VECTOR_INDEX_FILE)
            
            # 保存 chunk_id 映射
            with open('faiss_id_map.json', 'w', encoding='utf-8') as f:
                json.dump(chunk_id_map, f, ensure_ascii=False, indent=2)

            print(f"🎉 向量索引创建成功！索引文件保存于：{VECTOR_INDEX_FILE}")
            print(f"   ID 映射文件保存于：faiss_id_map.json")
    
    # 5. 保存 RAG 原始数据
    with open(RAG_DATA_JSON, 'w', encoding='utf-8') as f:
        json.dump(rag_data, f, ensure_ascii=False, indent=2)
        
    print(f"🎉 RAG 知识块数据（含 Metadata）已保存至：{RAG_DATA_JSON}")
    
    return rag_data

# --- 主执行流程 (保持不变) ---
if __name__ == "__main__":
    
    # 1. 加载和展平 JSON 数据
    json_data = load_and_normalize_json()
    
    # 2. 生成 RAG 知识块
    rag_knowledge_base = generate_rag_chunks(json_data)

    print(f"\n--- RAG 知识块生成摘要 ---")
    print(f"总共生成 {len(rag_knowledge_base)} 个知识块。")

    # 仅在有数据时打印示例
    if rag_knowledge_base:
        print("第一个知识块示例：")
        print(json.dumps(rag_knowledge_base[0], indent=2, ensure_ascii=False))

    # 3. 向量化和索引 (使用实际的 API)
    create_openai_embeddings_and_indexing(rag_knowledge_base)