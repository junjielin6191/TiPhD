import sys
import os
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from sqlalchemy import create_engine, distinct
import pandas as pd

# -------------------------------------------
# 导入生物学数据库模型 (database.py)
# -------------------------------------------
from database import session, SpatialLayer, CellType, SPATIALLAYER_FIELDS, CELLTYPE_FIELDS, format_entry, flatten_entry
import sys
import io
# 强制指定标准输出流为 UTF-8，彻底解决后台 print 中文导致的崩溃
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
import random
from datetime import datetime, timedelta
from flask_mail import Mail, Message
from user_db import user_db_session, User, ChatSession, ChatMessage, VerificationCode
# 原本的 import 往下挪...
import os
import uuid
# ...
# -------------------------------------------
# 导入用户系统数据库模型 (user_db.py)
# -------------------------------------------
try:
    from user_db import user_db_session, User, ChatSession, ChatMessage
except ImportError:
    print("⚠️ 警告: 无法导入 user_db.py，请确认该文件存在且已运行。")

# -------------------------------------------
# 引入 TiAgent 模块
# -------------------------------------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'TiAgent')))
try:
    # 此时的 run_tiagent 签名已更新为: run_tiagent(user_query, history_str)
    from tiagent_master import run_tiagent
except ImportError:
    print("⚠️ 警告: 无法导入 tiagent_master，智能体对话不可用。请检查路径。")
    run_tiagent = None

app = Flask(__name__)
app = Flask(__name__)
# 从环境变量读取，如果没读到就给个默认值
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key")

# ================= 邮箱发送配置 (安全版) =================
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.qq.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 465))
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL') == 'True'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
mail = Mail(app)
# =======================================================

# -------------------------------------------
# 用户登录管理 (Flask-Login)
# -------------------------------------------
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return user_db_session.query(User).get(int(user_id))

# --------------------------------------------
# 路由：身份验证 (Register / Login / Logout)
# --------------------------------------------
@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # 检查邮箱是否已被注册
        existing_user = user_db_session.query(User).filter_by(email=email).first()
        if existing_user:
            flash("This email is already registered. Please log in.")
            return redirect(url_for('register'))
            
        # 创建新用户并加密密码
        new_user = User(email=email)
        new_user.set_password(password)
        user_db_session.add(new_user)
        user_db_session.commit()
        
        flash("Registration successful! Please log in.")
        return redirect(url_for('login'))
    return render_template("register.html")

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        user = user_db_session.query(User).filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('agent_page'))
            
        flash("Invalid email or password.")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))


# --------------------------------------------
# 路由：静态与主页面
# --------------------------------------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/guideline")
def guideline():
    return render_template("guideline.html")

@app.route("/contact")
def contact():
    return render_template("contact.html")

# 注意：这里不再使用 @login_required，以便前端根据登录状态展示不同界面
@app.route("/agent")
def agent_page():
    return render_template("agent.html")


# --------------------------------------------
# 路由：Browse 页面
# --------------------------------------------
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

# --------------------------------------------
# 路由：Details 页面
# --------------------------------------------
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


# -------------------------------------------
# 路由：Statistics 页面
# -------------------------------------------
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

    # 1. 转换为 DataFrame 并清理不必要的状态字段
    data = pd.DataFrame([item.__dict__ for item in query])
    data = data.drop("_sa_instance_state", axis=1, errors="ignore")
    
    # 2. 【关键修复】填充空值，防止数据为空时 groupby 报错导致图表全军覆没
    data = data.fillna("Unknown")

    if table_name == "celltype":
        # 3. 使用 major 字段来生成热图，避免过于细碎
        heatmap_data = data.groupby(["major_cell_type", "major_cancer_type"]).size().unstack(fill_value=0)
        return {
            "major_cell_type": data["major_cell_type"].value_counts().to_dict(),
            "major_cancer_type": data["major_cancer_type"].value_counts().to_dict(),
            "Phenotype_type": data["Phenotype_type"].value_counts().to_dict(),
            "major_Phenotype_label": data["major_Phenotype_label"].value_counts().to_dict(),
            "heatmap": {
                "x": heatmap_data.columns.tolist(),
                "y": heatmap_data.index.tolist(),
                "z": heatmap_data.values.tolist(),
            },
        }
    elif table_name == "spatiallayer":
        # 3. 使用 major 字段来生成热图
        heatmap_data = data.groupby(["major_spatial_layer", "major_cancer_type"]).size().unstack(fill_value=0)
        return {
            "major_spatial_layer": data["major_spatial_layer"].value_counts().to_dict(),
            "major_cancer_type": data["major_cancer_type"].value_counts().to_dict(),
            "Phenotype_type": data["Phenotype_type"].value_counts().to_dict(),
            "major_Phenotype_label": data["major_Phenotype_label"].value_counts().to_dict(),
            "heatmap": {
                "x": heatmap_data.columns.tolist(),
                "y": heatmap_data.index.tolist(),
                "z": heatmap_data.values.tolist(),
            },
        }

# -------------------------------------------
# 路由：Search 页面
# -------------------------------------------
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
            fields = ['major_cancer_type','cancer_type', 'major_cell_type','cell_type', 'cell_name', 'Phenotype_type', 'major_Phenotype_label','Phenotype_label']
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
                "major_cancer_type":item.main_cancer_type,
                "cancer_type": item.cancer_type,
                "major_cell_type":item.big_cell_type,
                "cell_type": item.major_cell_type,
                "cell_type": item.cell_type,
                "cell_name": item.cell_name,
                "Phenotype_type": item.Phenotype_type,
                "major_Phenotype_label":item.main_Phenotype_label,
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
                "major_cancer_type":item.main_cancer_type,                
                "cancer_type": item.cancer_type,
                "major_spatial_layer":item.main_spatial_layer,
                "spatial_layer": item.spatial_layer,
                "Cell_type_composition": item.Cell_type_composition,
                "major_Phenotype_label":item.main_Phenotype_label,                
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


# -------------------------------------------
# 路由：Download 页面
# -------------------------------------------
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
            "tissue_type": item.tissue_type,
            "major_cancer_type": item.major_cancer_type,
            "cancer_type": item.cancer_type,
            "cancer_type_detail": item.cancer_type_detail,
            "major_cell_type": item.major_cell_type,
            "cell_type": item.cell_type,
            "cell_name": item.cell_name,
            "cell_marker": item.cell_marker,
            "PMID": item.PMID,
            "Paper_Title": item.Paper_Title,
            "journal": item.journal,
            "year": item.year,
            "Phenotype_type": item.Phenotype_type,
            "major_Phenotype_label": item.major_Phenotype_label,
            "Phenotype_label": item.Phenotype_label,
            "Association_Type": item.Association_Type,
            "Phenotype_evidence": item.Phenotype_evidence
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
            "tissue_type": item.tissue_type,
            "major_cancer_type": item.major_cancer_type,
            "cancer_type": item.cancer_type,
            "cancer_type_detail": item.cancer_type_detail,
            "major_spatial_layer": item.major_spatial_layer,
            "spatial_layer": item.spatial_layer,
            "Cell_type_composition": item.Cell_type_composition,
            "PMID": item.PMID,
            "Paper_Title": item.Paper_Title,
            "journal": item.journal,
            "year": item.year,
            "Phenotype_type": item.Phenotype_type,
            "major_Phenotype_label": item.major_Phenotype_label,
            "Phenotype_label": item.Phenotype_label,
            "Phenotype_evidence": item.Phenotype_evidence
        } for item in results]
        return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# -------------------------------------------
# 路由：TiAgent 智能体接口 (多会话管理)
# -------------------------------------------

@app.route('/api/sessions/list', methods=['GET'])
@login_required
def list_sessions():
    """获取当前登录用户的所有历史会话"""
    sessions = user_db_session.query(ChatSession).filter_by(user_id=current_user.id).order_by(ChatSession.created_at.desc()).all()
    return jsonify([{"id": s.id, "title": s.title} for s in sessions])

@app.route('/api/sessions/create', methods=['POST'])
@login_required
def create_session():
    """创建一个新的聊天会话"""
    new_id = str(uuid.uuid4())
    new_session = ChatSession(id=new_id, user_id=current_user.id, title="New Conversation")
    user_db_session.add(new_session)
    user_db_session.commit()
    return jsonify({"session_id": new_id})

@app.route('/api/sessions/<session_id>', methods=['GET'])
@login_required
def get_session_history(session_id):
    """根据 session_id 获取该会话下的所有历史消息"""
    records = user_db_session.query(ChatMessage).filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
    return jsonify([{"role": msg.role, "content": msg.content} for msg in records])

@app.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    if run_tiagent is None:
        return jsonify({"error": "TiAgent backend is not initialized."}), 500

    data = request.get_json()
    user_query = data.get("query")
    session_id = data.get("session_id")
    
    if not user_query or not session_id:
        return jsonify({"error": "Query and session_id are required."}), 400

    try:
        # 1. 从独立数据库提取属于该用户、该会话的历史记录
        history_records = user_db_session.query(ChatMessage).filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
        
        # 2. 格式化为 Context 字符串，供 Language Agent 进行语义消解
        history_str = ""
        for msg in history_records:
            role_label = "User" if msg.role == "user" else "TiAgent"
            history_str += f"{role_label}: {msg.content}\n"

        # 3. 调用智能体 (传入上下文历史)
        answer = run_tiagent(user_query, history_str)

        # 4. 持久化本次对话到用户数据库
        new_user_msg = ChatMessage(session_id=session_id, role='user', content=user_query)
        new_agent_msg = ChatMessage(session_id=session_id, role='agent', content=answer)
        user_db_session.add(new_user_msg)
        user_db_session.add(new_agent_msg)
        user_db_session.commit()

        return jsonify({"answer": answer})
    except Exception as e:
        user_db_session.rollback()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # 使用 host='0.0.0.0' 以允许外部访问
    app.run(host='0.0.0.0', port=5000, debug=True)