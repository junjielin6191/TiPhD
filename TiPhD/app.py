import sys
import os
from flask import Flask, render_template, request, jsonify
from sqlalchemy import create_engine, distinct
import pandas as pd
from database import session, SpatialLayer, CellType, SPATIALLAYER_FIELDS, CELLTYPE_FIELDS, format_entry, flatten_entry

# -------------------------------------------
# 引入 TiAgent 模块
# 请确保这里 sys.path.append 的路径能正确指向你的 TiAgent 文件夹
# -------------------------------------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'TiAgent')))
try:
    from tiagent_master import run_tiagent, global_memory
except ImportError:
    print("⚠️ 警告: 无法导入 tiagent_master，智能体对话不可用。请检查路径。")
    run_tiagent = None

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
    if table_name not in ["celltype", "spatiallayer"]:
        return render_template("404.html"), 404
    return render_template("browse.html", table_name=table_name)

@app.route('/browse/data/<table_name>')
def get_browse_data(table_name):
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 5, type=int)
    offset = (page - 1) * limit

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

    total_items = query.count()
    total_pages = (total_items + limit - 1) // limit
    data = query.offset(offset).limit(limit).all()

    formatted_data = [format_function(entry, fields) for entry in data]
    flattened_data = [flatten_entry(item) for item in formatted_data]

    return jsonify({
        "page": page,
        "total_pages": total_pages,
        "total_items": total_items,
        "data": flattened_data,
    })

# --------------------------------------------路由：detail 页面
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
    return render_template("statistics.html", table_name=table_name)

@app.route('/api/statistics/<table_name>')
def statistics_data(table_name):
    try:
        statistics = generate_statistics(table_name)
        if "error" in statistics:
            return jsonify({"error": statistics["error"]}), 400
        return jsonify(statistics)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def generate_statistics(table_name):
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
            "cells type": data["major_cell_type"].value_counts().to_dict(),
            "main cancer type": data["major_cancer_type"].value_counts().to_dict(),
            "phenotype type": data["Phenotype_type"].value_counts().to_dict(),
            "phenotype label": data["major_Phenotype_label"].value_counts().to_dict(),
            "heatmap": {
                "x": heatmap_data.columns.tolist(),
                "y": heatmap_data.index.tolist(),
                "z": heatmap_data.values.tolist(),
            },
        }
    elif table_name == "spatiallayer":
        heatmap_data = data.groupby(["spatial_layer","cancer_type"]).size().unstack(fill_value=0)
        return {
            "spatial layer": data["major_spatial_layer"].value_counts().to_dict(),
            "main cancer type": data["major_cancer_type"].value_counts().to_dict(),
            "phenotype type": data["Phenotype_type"].value_counts().to_dict(),
            "phenotype label": data["major_Phenotype_label"].value_counts().to_dict(),
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

@app.route('/api/get_options', methods=['GET'])
def get_options():
    table_name = request.args.get('table')
    field_name = request.args.get('field')
    
    try:
        if table_name == 'celltype':
            query = session.query(distinct(getattr(CellType, field_name)))
            for key, value in request.args.items():
                if key not in ['table', 'field'] and value:
                    query = query.filter(getattr(CellType, key) == value)
        elif table_name == 'spatiallayer':
            query = session.query(distinct(getattr(SpatialLayer, field_name)))
            for key, value in request.args.items():
                if key not in ['table', 'field'] and value:
                    query = query.filter(getattr(SpatialLayer, key) == value)
        else:
            return jsonify({"error": "Invalid table name"}), 400

        results = [row[0] for row in query.all() if row[0] is not None]
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/search/<table_name>', methods=['GET'])
def search_data(table_name):
    try:
        filters = {}
        if table_name == 'celltype':
            fields = ['major_cancer_type','cancer_type', 'major_cell_type','major_cell_type', 'cell_name', 'Phenotype_type', 'major_Phenotype_label','Phenotype_label']
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
                "major_cancer_type":item.major_cancer_type,
                "cancer_type": item.cancer_type,
                "major_cell_type":item.major_cell_type,
                "major_cell_type": item.major_cell_type,
                "cell_name": item.cell_name,
                "Phenotype_type": item.Phenotype_type,
                "major_Phenotype_label":item.major_Phenotype_label,
                "Phenotype_label": item.Phenotype_label,
                "Paper_Title": item.Paper_Title,
                "journal": item.journal,
                "year": item.year,
                "PMID": item.PMID
            } for item in results]
            
        elif table_name == 'spatiallayer':
            fields = ['major_cancer_type','cancer_type', 'major_spatial_layer', 'spatial_layer', 'major_Phenotype_label','Phenotype_label']
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
                "major_cancer_type":item.major_cancer_type,                
                "cancer_type": item.cancer_type,
                "major_spatial_layer":item.major_spatial_layer,
                "spatial_layer": item.spatial_layer,
                "Cell_type_composition": item.Cell_type_composition,
                "major_Phenotype_label":item.major_Phenotype_label,                
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
        return jsonify({"error": str(e)}), 500

# -------------------------------------------路由：Download 页面
@app.route("/download")
def download():
    return render_template("download.html")

@app.route('/api/get_cell_type_data')
def get_cell_type_data():
    try:
        results = session.query(CellType).all()
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
        results = session.query(SpatialLayer).all()
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

# -------------------------------------------路由：TiAgent 智能体页面
@app.route("/agent")
def agent_page():
    return render_template("agent.html")

@app.route('/api/chat', methods=['POST'])
def chat_api():
    if run_tiagent is None:
        return jsonify({"error": "TiAgent backend is not initialized."}), 500

    data = request.get_json()
    user_query = data.get("query")
    
    if not user_query:
        return jsonify({"error": "Query cannot be empty."}), 400

    try:
        answer = run_tiagent(user_query)
        return jsonify({"answer": answer})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat/clear', methods=['POST'])
def clear_chat_api():
    try:
        global_memory.history_queue.clear()
        return jsonify({"status": "success"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------------------------------------------路由：Guideline / Contact 页面
@app.route("/guideline")
def guideline():
    return render_template("guideline.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

if __name__ == "__main__":
    # 将 host 设置为 '0.0.0.0'，允许外部网络访问
    app.run(host='0.0.0.0', port=5000, debug=True)