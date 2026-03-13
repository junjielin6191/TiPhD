import sys
import os
import uuid
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import create_engine, distinct
from sqlalchemy.orm import sessionmaker
import pandas as pd

# 导入生物数据数据库模型 (database.py)
from database import session as bio_session, SpatialLayer, CellType, \
    SPATIALLAYER_FIELDS, CELLTYPE_FIELDS, format_entry, flatten_entry

# 导入用户系统数据库模型 (user_db.py)
# 请确保你有这个文件，其中定义了 User, ChatSession, ChatMessage 以及 user_db_session
from user_db import user_db_session, User, ChatSession, ChatMessage

# -------------------------------------------
# 引入 TiAgent 模块
# -------------------------------------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'TiAgent')))
try:
    # 此时的 run_tiagent 签名应为: run_tiagent(user_query, history_str)
    from tiagent_master import run_tiagent
except ImportError:
    print("⚠️ 警告: 无法导入 tiagent_master，智能体对话不可用。")
    run_tiagent = None

app = Flask(__name__)
app.secret_key = "tiagent_secret_key_for_session" # 生产环境请更换

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
# 路由：身份验证 (Login/Register)
# --------------------------------------------
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
        new_user.set_password(password) # 使用我们刚写的加密方法
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
        
        # 查找用户
        user = user_db_session.query(User).filter_by(email=email).first()
        
        # 校验密码哈希
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
@app.route('/api/sessions/<session_id>', methods=['GET'])
@login_required
def get_session_history(session_id):
    """根据 session_id 获取该会话下的所有历史消息"""
    records = user_db_session.query(ChatMessage).filter_by(session_id=session_id).order_by(ChatMessage.timestamp.asc()).all()
    # 返回给前端
    return jsonify([{"role": msg.role, "content": msg.content} for msg in records])
# --------------------------------------------
# 路由：主页与基础页面
# --------------------------------------------
@app.route("/")
def home():
    return render_template("home.html")

@app.route("/agent")
@login_required
def agent_page():
    return render_template("agent.html")

# -------------------------------------------
# 接口：TiAgent 智能体核心对话 (用户级隔离)
# -------------------------------------------
@app.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    if run_tiagent is None:
        return jsonify({"error": "TiAgent 后端未初始化"}), 500

    data = request.get_json()
    user_query = data.get("query")
    session_id = data.get("session_id") # 前端传递当前会话ID

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

        # 3. 调用智能体 (内部会进行语义消解 -> 路由 -> 执行)
        answer = run_tiagent(user_query, history_str)

        # 4. 持久化本次对话
        new_user_msg = ChatMessage(session_id=session_id, role='user', content=user_query)
        new_agent_msg = ChatMessage(session_id=session_id, role='agent', content=answer)
        user_db_session.add(new_user_msg)
        user_db_session.add(new_agent_msg)
        user_db_session.commit()

        return jsonify({"answer": answer})
    except Exception as e:
        user_db_session.rollback()
        return jsonify({"error": str(e)}), 500

@app.route('/api/sessions/list', methods=['GET'])
@login_required
def list_sessions():
    sessions = user_db_session.query(ChatSession).filter_by(user_id=current_user.id).order_by(ChatSession.created_at.desc()).all()
    return jsonify([{"id": s.id, "title": s.title} for s in sessions])

@app.route('/api/sessions/create', methods=['POST'])
@login_required
def create_session():
    new_id = str(uuid.uuid4())
    new_session = ChatSession(id=new_id, user_id=current_user.id, title="New Conversation")
    user_db_session.add(new_session)
    user_db_session.commit()
    return jsonify({"session_id": new_id})

# -------------------------------------------
# 路由：数据浏览与搜索 (保持之前的优化版本)
# -------------------------------------------
@app.route('/browse/<table_name>')
def browse_page(table_name):
    return render_template("browse.html", table_name=table_name)

@app.route('/browse/data/<table_name>')
def get_browse_data(table_name):
    page = request.args.get("page", 1, type=int)
    limit = request.args.get("limit", 10, type=int)
    offset = (page - 1) * limit
    
    query = bio_session.query(CellType if table_name == "celltype" else SpatialLayer)
    fields = CELLTYPE_FIELDS if table_name == "celltype" else SPATIALLAYER_FIELDS
    
    total_items = query.count()
    data = query.offset(offset).limit(limit).all()
    formatted_data = [format_entry(entry, fields) for entry in data]
    flattened_data = [flatten_entry(item) for item in formatted_data]

    return jsonify({
        "page": page,
        "total_pages": (total_items + limit - 1) // limit,
        "total_items": total_items,
        "data": flattened_data,
    })

# -------------------------------------------
# 路由：统计分析 (保持之前的填充空值优化)
# -------------------------------------------
@app.route('/statistics/<table_name>')
def statistics_page(table_name):
    return render_template("statistics.html", table_name=table_name)

@app.route('/api/statistics/<table_name>')
def statistics_data(table_name):
    query = bio_session.query(CellType if table_name == "celltype" else SpatialLayer).all()
    data = pd.DataFrame([item.__dict__ for item in query]).drop("_sa_instance_state", axis=1, errors="ignore").fillna("Unknown")

    if table_name == "celltype":
        heatmap = data.groupby(["major_cell_type", "major_cancer_type"]).size().unstack(fill_value=0)
        res = {
            "major_cell_type": data["major_cell_type"].value_counts().to_dict(),
            "major_cancer_type": data["major_cancer_type"].value_counts().to_dict(),
            "Phenotype_type": data["Phenotype_type"].value_counts().to_dict(),
            "major_Phenotype_label": data["major_Phenotype_label"].value_counts().to_dict(),
            "heatmap": {"x": heatmap.columns.tolist(), "y": heatmap.index.tolist(), "z": heatmap.values.tolist()}
        }
    else:
        heatmap = data.groupby(["major_spatial_layer", "major_cancer_type"]).size().unstack(fill_value=0)
        res = {
            "major_spatial_layer": data["major_spatial_layer"].value_counts().to_dict(),
            "major_cancer_type": data["major_cancer_type"].value_counts().to_dict(),
            "Phenotype_type": data["Phenotype_type"].value_counts().to_dict(),
            "major_Phenotype_label": data["major_Phenotype_label"].value_counts().to_dict(),
            "heatmap": {"x": heatmap.columns.tolist(), "y": heatmap.index.tolist(), "z": heatmap.values.tolist()}
        }
    return jsonify(res)

# -------------------------------------------
# 路由：下载接口 (包含 20 个完整字段)
# -------------------------------------------
@app.route('/api/get_cell_type_data')
def get_cell_type_data():
    results = bio_session.query(CellType).all()
    return jsonify([ {k: getattr(item, k) for k in item.__table__.columns.keys() if k != 'id'} for item in results])

@app.route('/api/get_spatial_structure_data')
def get_spatial_structure_data():
    results = bio_session.query(SpatialLayer).all()
    return jsonify([ {k: getattr(item, k) for k in item.__table__.columns.keys() if k != 'id'} for item in results])

# 详情页
@app.route("/details/<table_name>/<item_id>")
def get_details(table_name, item_id):
    model = CellType if table_name == "celltype" else SpatialLayer
    fields = CELLTYPE_FIELDS if table_name == "celltype" else SPATIALLAYER_FIELDS
    entry = bio_session.query(model).filter(getattr(model, 'CTID' if table_name == "celltype" else 'SLID') == item_id).first()
    if not entry: return render_template("404.html"), 404
    return render_template("details.html", data=format_entry(entry, fields))

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)