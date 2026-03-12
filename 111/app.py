from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, distinct
import pandas as pd
from database import session, SpatialLayer, CellType, SPATIALLAYER_FIELDS, CELLTYPE_FIELDS, format_entry,flatten_entry

app = Flask(__name__)


# 数据库连接
DATABASE_URL = "sqlite:///database.db"  # 数据库地址
engine = create_engine(DATABASE_URL)


# --------------------------------------------路由：主页
@app.route("/")
def home():
    return render_template("home.html")

# --------------------------------------------路由：Browse 页面
@app.route('/browse/<table_name>')
def browse_page(table_name):
    """
    渲染 browse 页面
    """
    if table_name not in ["celltype", "spatiallayer"]:
        return render_template("404.html"), 404
    return render_template("browse.html", table_name=table_name)

@app.route('/browse/data/<table_name>')
def get_browse_data(table_name):
    """
    返回表格数据，支持分页
    """
    # 获取分页参数
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 5, type=int)  # 每页显示多少条数据
    offset = (page - 1) * limit  # 计算偏移量

    # 根据表格名称查询数据
    if table_name == "spatiallayer":
        query = session.query(SpatialLayer)
        fields = SPATIALLAYER_FIELDS
        format_function = format_entry
    elif table_name == "celltype":
        query = session.query(CellType)
        fields = CELLTYPE_FIELDS
        format_function = format_entry
    else:
        return jsonify({"error": "Invalid table name"}), 404

    # 获取数据和总数
    total_items = query.count()
    total_pages = (total_items + limit - 1) // limit  # 计算总页数
    data = query.offset(offset).limit(limit).all()  # 获取当前页的数据

    # 格式化数据
    formatted_data = [format_function(entry, fields) for entry in data]
    flattened_data = [flatten_entry(item) for item in formatted_data]

    return jsonify({
        "page": page,
        "total_pages": total_pages,
        "total_items": total_items,
        "data": flattened_data,
    })






# --------------------------------------------路由：detail 页面
# 详情页路由
@app.route("/details/<table_name>/<item_id>")
def get_details(table_name, item_id):
    if table_name == "celltype":
        entry = session.query(CellType).filter_by(CTID=item_id).first()
        if not entry:
            return jsonify({"error": "Item not found"}), 404
        formatted_data = format_entry(entry, CELLTYPE_FIELDS)
    elif table_name == "spatiallayer":
        entry = session.query(SpatialLayer).filter_by(SLID=item_id).first()
        if not entry:
            return jsonify({"error": "Item not found"}), 404
        formatted_data = format_entry(entry, SPATIALLAYER_FIELDS)
    else:
        return jsonify({"error": "Invalid table name"}), 404

    return render_template("details.html", data=formatted_data)

# -------------------------------------------路由：Statistics 页面
@app.route('/statistics/<table_name>')
def statistics_page(table_name):
    """
    渲染统计页面
    """
    return render_template("statistics.html", table_name=table_name)


@app.route('/api/statistics/<table_name>')
def statistics_data(table_name):
    """
    返回指定表的统计信息的 API 接口
    """
    try:
        statistics = generate_statistics(table_name)
        if "error" in statistics:
            return jsonify({"error": statistics["error"]}), 400
        return jsonify(statistics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def generate_statistics(table_name):
    """
    为指定的表生成统计信息
    """
    if table_name == "spatiallayer":
        query = session.query(SpatialLayer).all()
    elif table_name == "celltype":
        query = session.query(CellType).all()
    else:
        return {"error": f"无效的表名: {table_name}"}

    data = pd.DataFrame([item.__dict__ for item in query])
    data = data.drop("_sa_instance_state", axis=1, errors="ignore")

    if table_name == "celltype":
        heatmap_data = data.groupby(["cell_name","cancer_type"]).size().unstack(fill_value=0)
        return {
            "cells type": data["big_cell_type"].value_counts().to_dict(),
            "main cancer type": data["main_cancer_type"].value_counts().to_dict(),
            "phenotype type": data["Phenotype_type"].value_counts().to_dict(),
            "phenotype label": data["main_Phenotype_label"].value_counts().to_dict(),
            "heatmap": {
                "x": heatmap_data.columns.tolist(),
                "y": heatmap_data.index.tolist(),
                "z": heatmap_data.values.tolist(),
            },
        }
    elif table_name == "spatiallayer":
        heatmap_data = data.groupby(["spatial_layer","cancer_type"]).size().unstack(fill_value=0)
        return {
            "spatial layer": data["main_spatial_layer"].value_counts().to_dict(),
            "main cancer type": data["main_cancer_type"].value_counts().to_dict(),
            "phenotype type": data["Phenotype_type"].value_counts().to_dict(),
            "phenotype label": data["main_Phenotype_label"].value_counts().to_dict(),
            "heatmap": {
                "x": heatmap_data.columns.tolist(),
                "y": heatmap_data.index.tolist(),
                "z": heatmap_data.values.tolist(),
            },
        }


# -------------------------------------------路由：Search 页面
@app.route('/search/<table_name>')
def search_page(table_name):
    return render_template("search.html", table_name=table_name)

# 获取当前表的数据查询对象
def get_query_by_table(table_name, filter_conditions):
    if table_name == 'celltype':
        query = session.query(CellType)
        for key, value in filter_conditions.items():
            if value:
                query = query.filter(getattr(CellType, key) == value)
    elif table_name == 'spatiallayer':
        query = session.query(SpatialLayer)
        for key, value in filter_conditions.items():
            if value:
                query = query.filter(getattr(SpatialLayer, key) == value)
    else:
        raise ValueError("Unknown table name provided")
    return query


@app.route('/api/get_options', methods=['GET'])
def get_options():
    """获取下拉框选项，支持多重筛选"""
    table_name = request.args.get('table')
    field_name = request.args.get('field')
    
    try:
        if table_name == 'celltype':
            # 使用 distinct 确保返回唯一值
            query = session.query(distinct(getattr(CellType, field_name)))
            
            # 添加所有其他筛选条件
            for key, value in request.args.items():
                if key not in ['table', 'field'] and value:
                    query = query.filter(getattr(CellType, key) == value)
                    
        elif table_name == 'spatiallayer':
            query = session.query(distinct(getattr(SpatialLayer, field_name)))
            
            # 添加所有其他筛选条件
            for key, value in request.args.items():
                if key not in ['table', 'field'] and value:
                    query = query.filter(getattr(SpatialLayer, key) == value)
        else:
            return jsonify({"error": "Invalid table name"}), 400

        results = [row[0] for row in query.all() if row[0] is not None]
        return jsonify(results)
    except Exception as e:
        print(f"Error in get_options: {str(e)}")
        return jsonify({"error": str(e)}), 500



@app.route('/api/search/<table_name>', methods=['GET'])
def search_data(table_name):
    try:
        filters = {}
        if table_name == 'celltype':
            fields = ['main_cancer_type','cancer_type', 'big_cell_type','major_cell_type', 'cell_name', 'Phenotype_type', 'main_Phenotype_label','Phenotype_label']
            for field in fields:
                if request.args.get(field):
                    filters[field] = request.args.get(field)
            
            query = session.query(CellType)
            for key, value in filters.items():
                if value:
                    query = query.filter(getattr(CellType, key) == value)
            
            results = query.all()
            formatted_results = [{
                "CTID": item.CTID,
                "species": item.species,
                "tissue_class": item.tissue_class,
                "main_cancer_type":item.main_cancer_type,
                "cancer_type": item.cancer_type,
                "big_cell_type":item.big_cell_type,
                "major_cell_type": item.major_cell_type,
                "cell_name": item.cell_name,
                "Phenotype_type": item.Phenotype_type,
                "main_Phenotype_label":item.main_Phenotype_label,
                "Phenotype_label": item.Phenotype_label,
                "Paper_Title": item.Paper_Title,
                "journal": item.journal,
                "year": item.year,
                "PMID": item.PMID
            } for item in results]
            
        elif table_name == 'spatiallayer':
            fields = ['main_cancer_type','cancer_type', 'main_spatial_layer', 'spatial_layer', 'main_Phenotype_label','Phenotype_label']
            for field in fields:
                if request.args.get(field):
                    filters[field] = request.args.get(field)
            
            query = session.query(SpatialLayer)
            for key, value in filters.items():
                if value:
                    query = query.filter(getattr(SpatialLayer, key) == value)
            
            results = query.all()
            formatted_results = [{
                "SLID": item.SLID,
                "species": item.species,
                "tissue_class": item.tissue_class,
                "main_cancer_type":item.main_cancer_type,                
                "cancer_type": item.cancer_type,
                "main_spatial_layer":item.main_spatial_layer,
                "spatial_layer": item.spatial_layer,
                "Cell_type_composition": item.Cell_type_composition,
                "main_Phenotype_label":item.main_Phenotype_label,                
                "Phenotype_type": item.Phenotype_type,
                "Phenotype_label": item.Phenotype_label,
                "Paper_Title": item.Paper_Title,
                "journal": item.journal,
                "year": item.year,
                "PMID": item.PMID
            } for item in results]
        
        else:
            return jsonify({"error": "Invalid table name"}), 400

        return jsonify(formatted_results)
        
    except Exception as e:
        print(f"Search error: {str(e)}")
        return jsonify({"error": str(e)}), 500



# -------------------------------------------路由：Download 页面
@app.route("/download")
def download():
    return render_template("download.html")

@app.route('/api/get_cell_type_data')
def get_cell_type_data():
    try:
        # 查询 cell type 数据
        results = session.query(CellType).all()
        
        # 格式化数据
        data = [{
            "CTID": item.CTID,
            "species": item.species,
            "tissue_class": item.tissue_class,
            "cancer_type": item.cancer_type,
            "major_cell_type": item.major_cell_type,
            "cell_name": item.cell_name,
            "Phenotype_type": item.Phenotype_type,
            "Phenotype_label": item.Phenotype_label,
            "Paper_Title": item.Paper_Title,
            "journal": item.journal,
            "year": item.year,
            "PMID": item.PMID
        } for item in results]
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/get_spatial_structure_data')
def get_spatial_structure_data():
    try:
        # 查询 spatial structure 数据
        results = session.query(SpatialLayer).all()
        
        # 格式化数据
        data = [{
            "SLID": item.SLID,
            "species": item.species,
            "tissue_class": item.tissue_class,
            "cancer_type": item.cancer_type,
            "spatial_layer": item.spatial_layer,
            "Cell_type_composition": item.Cell_type_composition,
            "Phenotype_type": item.Phenotype_type,
            "Phenotype_label": item.Phenotype_label,
            "Paper_Title": item.Paper_Title,
            "journal": item.journal,
            "year": item.year,
            "PMID": item.PMID
        } for item in results]
        
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -------------------------------------------路由：Tools 页面
@app.route("/tools")
def tools():
    # 读取所有需要的数据
    bulk_data = pd.read_csv('data/bulk.csv')
    scrna_data = pd.read_csv('data/scRNA.csv')
    st_data = pd.read_csv('data/ST.csv')
    tools_data = pd.read_csv('data/tools.csv')
    
    return render_template('tools.html',
                         bulk_data=bulk_data.to_dict('records'),
                         scrna_data=scrna_data.to_dict('records'),
                         st_data=st_data.to_dict('records'),
                         tools_data=tools_data.to_dict('records'))

@app.route("/tools/TiRank-Celltype")
def tirank_celltype():
    # 读取所有需要的数据，指定编码格式
    bulk_data = pd.read_csv('data/bulk.csv')  # 或者使用 'gb18030'
    scrna_data = pd.read_csv('data/scRNA.csv')
    
    return render_template('tools.html',
                         page='celltype',
                         bulk_data=bulk_data.to_dict('records'),
                         scrna_data=scrna_data.to_dict('records'))

@app.route("/tools/TiRank-Spatiallayer")
def tirank_spatial():
    # 读取所有需要的数据，指定编码格式
    bulk_data = pd.read_csv('data/bulk.csv')
    st_data = pd.read_csv('data/ST.csv')
    
    return render_template('tools.html',
                         page='spatial',
                         bulk_data=bulk_data.to_dict('records'),
                         st_data=st_data.to_dict('records'))

@app.route("/tools/ToolDB")
def tooldb():
    # 读取工具数据，指定编码格式
    tools_data = pd.read_csv('data/tools.csv')
    
    # 按第一列分类
    categories = tools_data.iloc[:, 0].unique().tolist()
    tools_by_category = {
        category: tools_data[tools_data.iloc[:, 0] == category].to_dict('records')
        for category in categories
    }
    
    return render_template('tools.html',
                         page='tooldb',
                         categories=categories,
                         tools_by_category=tools_by_category)
# -------------------------------------------路由：experiment 页面
@app.route('/experiment')
def experiment():
    # 读取 CSV 文件
    df = pd.read_csv('data/experiment.csv')
    
    # 将数据转换为字典列表
    experiments = df.to_dict('records')
    
    # 获取唯一的分类值用于过滤器
    categories = {
        'spatial_layers': df['Spatiallayer'].dropna().unique().tolist(),
        'experimental_designs': df['Experimental Design'].dropna().unique().tolist(),
        'methodologies': df['Methodology'].dropna().unique().tolist()
    }
    
    return render_template('experiment.html', 
                         experiments=experiments,
                         categories=categories)
# -------------------------------------------路由：Guideline 页面
@app.route("/guideline")
def guideline():
    return render_template("guideline.html")

# -------------------------------------------路由：Contact 页面
@app.route("/contact")
def contact():
    return render_template("contact.html")

if __name__ == "__main__":
    app.run(debug=True)
