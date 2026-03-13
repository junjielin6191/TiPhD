import pandas as pd
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
import os

# ----------------- 修复核心：使用绝对路径 -----------------
# 获取当前 database.py 所在的绝对路径目录
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# 拼接出固定不变的绝对路径：/home/ljj/TiPhD/TiPhD/database.db
DB_PATH = os.path.join(BASE_DIR, 'database.db')

Base = declarative_base()
# 注意：sqlite 绝对路径需要 4 个斜杠 (sqlite:////...)
engine = create_engine(f'sqlite:///{DB_PATH}')
Session = sessionmaker(bind=engine)
session = Session()
# --------------------------------------------------------
# 定义 SpatialLayer 表

class SpatialLayer(Base):
    __tablename__ = 'spatiallayer'
    
    # 数据库主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 根据 CSV 表头严格定义的字段
    SLID = Column(String, unique=True, nullable=False)  # 唯一标识符
    species = Column(String)
    tissue_class = Column(String)
    tissue_type = Column(String)
    major_cancer_type = Column(String)
    cancer_type = Column(String)
    cancer_type_detail = Column(String)
    major_spatial_layer = Column(String)
    spatial_layer = Column(String)
    Cell_type_composition = Column(String)
    PMID = Column(Integer)
    Paper_Title = Column(String)
    journal = Column(String)
    year = Column(String)
    technology_type_for_discovery = Column(String)
    technology_platform_for_discovery = Column(String)
    Phenotype_type = Column(String)
    major_Phenotype_label = Column(String)
    Phenotype_label = Column(String)
    model_type = Column(String)
    technology_type_for_validation = Column(String)
    technology_platform_for_validation = Column(String)
    evidence_type = Column(String)
    Phenotype_evidence = Column(Text)  # 证据描述通常很长




class CellType(Base):
    __tablename__ = 'celltype'
    
    # 数据库内部主键
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # 根据 CSV 表头定义的字段
    CTID = Column(String, unique=True, nullable=False)  # 唯一标识符
    species = Column(String)
    tissue_class = Column(String)
    tissue_type = Column(String)
    major_cancer_type = Column(String)
    cancer_type = Column(String)
    cancer_type_detail = Column(String)
    major_cell_type = Column(String)
    cell_type = Column(String)
    cell_name = Column(String)
    cell_marker = Column(String)  # 对应表头的 cell_marker
    PMID = Column(Integer)
    Paper_Title = Column(String)
    journal = Column(String)
    year = Column(String)
    technology_type_for_discovery = Column(String)
    technology_platform_for_discovery = Column(String)
    Phenotype_type = Column(String)
    major_Phenotype_label = Column(String)
    Phenotype_label = Column(String)
    Association_Type = Column(String)  # 新增：对应表头字段
    model_type = Column(String)
    technology_type_for_validation = Column(String)
    technology_platform_for_validation = Column(String)
    evidence_type = Column(String)
    Phenotype_evidence = Column(Text)  # 证据内容通常较长，建议用 Text

# 创建表结构
Base.metadata.create_all(engine)

# 定义字段分类规则
SPATIALLAYER_FIELDS = {
    "basic_info": [
        "species", 
        "tissue_class", 
        "tissue_type", 
        "major_cancer_type", 
        "cancer_type", 
        "cancer_type_detail"
    ],
    "spatial_info": [
        "SLID", 
        "major_spatial_layer", 
        "spatial_layer", 
        "Cell_type_composition"
    ],
    "paper_info": [
        "PMID", 
        "Paper_Title", 
        "journal", 
        "year"
    ],
    "technology_info": [
        "technology_type_for_discovery",
        "technology_platform_for_discovery",
        "technology_type_for_validation",
        "technology_platform_for_validation",
        "model_type",
        "evidence_type"
    ],
    "phenotype_info": [
        "Phenotype_type", 
        "major_Phenotype_label", 
        "Phenotype_label", 
        "Phenotype_evidence"
    ],
}

CELLTYPE_FIELDS = {
    "basic_info": [
        "species", 
        "tissue_class", 
        "tissue_type", 
        "major_cancer_type", 
        "cancer_type", 
        "cancer_type_detail"
    ],
    "cell_info": [
        "CTID", 
        "major_cell_type", 
        "cell_type", 
        "cell_name", 
        "cell_marker"
    ],
    "paper_info": [
        "PMID", 
        "Paper_Title", 
        "journal", 
        "year"
    ],
    "technology_info": [
        "technology_type_for_discovery",
        "technology_platform_for_discovery",
        "technology_type_for_validation",
        "technology_platform_for_validation",
        "model_type",
        "evidence_type"
    ],
    "phenotype_info": [
        "Phenotype_type", 
        "major_Phenotype_label", 
        "Phenotype_label", 
        "Association_Type",  # 加入了关联类型
        "Phenotype_evidence"
    ],
}

# 通用数据加载函数
def load_data_to_table(csv_path, table_class, unique_field):
    """
    从 CSV 文件加载数据到指定的数据库表
    """
    data = pd.read_csv(csv_path)

    # 检查唯一字段是否唯一
    if data[unique_field].duplicated().any():
        raise ValueError(f"{unique_field} 列包含重复值，请确保其是唯一的。")

    # 插入数据到指定表
    records = [
        table_class(**row.to_dict()) for _, row in data.iterrows()
    ]

    # 批量插入数据库
    session.bulk_save_objects(records)
    session.commit()
    print(f"数据已成功加载到 {table_class.__tablename__} 表中，共加载 {len(records)} 条记录。")

# 通用数据查询函数
def format_entry(entry, category_fields):
    """
    按类别分组数据
    """
    formatted_entry = {}
    for category, fields in category_fields.items():
        formatted_entry[category] = {field: getattr(entry, field, None) for field in fields}
    return formatted_entry

def get_entry_by_unique_field(table_class, field_name, field_value, category_fields):
    """
    根据唯一字段查询数据表中的数据并按分类返回
    """
    entry = session.query(table_class).filter_by(**{field_name: field_value}).first()
    if not entry:
        return None
    return format_entry(entry, category_fields)
def flatten_entry(entry):
    """
    将按类别分组的条目展平为扁平字典，并确保 CTID 或 SLID 位于第一列
    """
    flattened = {}
    # 优先添加 CTID 或 SLID
    if "CTID" in entry.get("cell_info", {}):
        flattened["CTID"] = entry["cell_info"].get("CTID")
    elif "SLID" in entry.get("spatial_info", {}):
        flattened["SLID"] = entry["spatial_info"].get("SLID")
    
    # 添加其他字段
    for category, fields in entry.items():
        for field, value in fields.items():
            if field not in ["CTID", "SLID"]:  # 避免重复
                flattened[field] = value
    return flattened



# #加载 SpatialLayer 数据
# spatial_csv_path = './TiPhD/data/spatialayer.csv'
# load_data_to_table(spatial_csv_path, SpatialLayer, 'SLID')



# # 加载 CellType 数据
# cell_csv_path = './TiPhD/data/celltype.csv'
# load_data_to_table(cell_csv_path, CellType, 'CTID')

# # 示例查询 SpatialLayer
# SLID_example = "SL001"
# spatial_entry = get_entry_by_unique_field(SpatialLayer, 'SLID', SLID_example, SPATIALLAYER_FIELDS)
# if spatial_entry:
#     print("SpatialLayer 表数据：")
#     print(spatial_entry)
# else:
#     print(f"未找到 SLID 为 {SLID_example} 的条目。")

# # 示例查询 CellType
# CTID_example = "CT001"
# cell_entry = get_entry_by_unique_field(CellType, 'CTID', CTID_example, CELLTYPE_FIELDS)
# if cell_entry:
#     print("CellType 表数据：")
#     print(cell_entry)
# else:
#     print(f"未找到 CTID 为 {CTID_example} 的条目。")
