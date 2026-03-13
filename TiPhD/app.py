import sys
import os
import io
import uuid
import base64
import random
import string
from datetime import datetime, timedelta
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask import session as flask_session # 【重要】起别名，防止与数据库 session 冲突
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from flask_mail import Mail, Message
from captcha.image import ImageCaptcha # 引入图形验证码库

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

load_dotenv()

from sqlalchemy import create_engine, distinct
import pandas as pd
from database import session, SpatialLayer, CellType, SPATIALLAYER_FIELDS, CELLTYPE_FIELDS, format_entry, flatten_entry

try:
    from user_db import user_db_session, User, ChatSession, ChatMessage, VerificationCode
except ImportError:
    print("⚠️ 警告: 无法导入 user_db.py 或缺少 VerificationCode 表。")

# -------------------------------------------
# 引入 TiAgent 模块
# -------------------------------------------
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'TiAgent')))
try:
    # 🌟 新增导入 generate_session_title
    from tiagent_master import run_tiagent, generate_session_title
except ImportError:
    print("⚠️ 警告: 无法导入 tiagent_master，智能体对话不可用。请检查路径。")
    run_tiagent = None

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key")

# ================= 邮箱发送配置 =================
# ================= 邮箱发送配置 (安全版) =================
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 465))
app.config['MAIL_USE_SSL'] = True  # 【关键修改】强制写死 True，防止环境变量没读到导致崩溃
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')
app.config['MAIL_DEFAULT_SENDER'] = os.getenv('MAIL_USERNAME')
mail = Mail(app)
# =======================================================
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
# ==========================================================
# 🌟 升级：注册和登录路由
# ==========================================================
@app.route("/register", methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        code = request.form.get('code')
        
        # 验证邮件验证码
        vc = user_db_session.query(VerificationCode).filter_by(email=email).order_by(VerificationCode.id.desc()).first()
        if not vc or vc.code != code:
            flash("邮件验证码错误。")
            return redirect(url_for('register'))
        if vc.expires_at < datetime.utcnow():
            flash("邮件验证码已过期，请重新获取。")
            return redirect(url_for('register'))
            
        if user_db_session.query(User).filter_by(email=email).first():
            flash("该邮箱已注册。")
            return redirect(url_for('register'))
            
        new_user = User(email=email)
        new_user.set_password(password)
        user_db_session.add(new_user)
        user_db_session.commit()
        
        flash("注册成功！请登录。")
        return redirect(url_for('login'))
        
    return render_template("register.html")

@app.route("/login", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        code = request.form.get('code')
        
        user = user_db_session.query(User).filter_by(email=email).first()
        if not user:
            flash("账号不存在。")
            return redirect(url_for('login'))

        # 验证邮件验证码
        vc = user_db_session.query(VerificationCode).filter_by(email=email).order_by(VerificationCode.id.desc()).first()
        if not vc or vc.code != code:
            flash("邮件验证码错误。")
            return redirect(url_for('login'))
        if vc.expires_at < datetime.utcnow():
            flash("邮件验证码已过期，请重新获取。")
            return redirect(url_for('login'))

        # 验证通过，执行登录
        login_user(user)
        return redirect(url_for('agent_page'))
        
    return render_template("login.html")
@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for('home'))

# ==========================================================
# 🌟 新增：图形验证码与邮件发送 API
# ==========================================================
@app.route('/api/captcha')
def get_captcha():
    """生成 4 位随机图形验证码"""
    image = ImageCaptcha(width=120, height=40)
    captcha_text = ''.join(random.choices(string.ascii_uppercase + string.digits, k=4))
    flask_session['captcha'] = captcha_text # 存入服务器 session
    data = image.generate(captcha_text)
    base64_img = base64.b64encode(data.getvalue()).decode('utf-8')
    return jsonify({'captcha_image': f"data:image/png;base64,{base64_img}"})

@app.route('/api/send_code', methods=['POST'])
def send_code():
    """统一的发送邮件接口，支持注册和登录"""
    data = request.get_json()
    email = data.get('email')
    captcha_input = data.get('captcha')
    action = data.get('action') # 'register' 或 'login'

    if not email or not captcha_input:
        return jsonify({"error": "Email and Captcha are required."}), 400

    # 1. 校验图形验证码
    if captcha_input.upper() != flask_session.get('captcha', ''):
        return jsonify({"error": "图形验证码错误或已过期。"}), 400
    
    # 校验完毕后销毁图形验证码，防止重复使用
    flask_session.pop('captcha', None)

    # 2. 校验用户状态
    user = user_db_session.query(User).filter_by(email=email).first()
    if action == 'register' and user:
        return jsonify({"error": "该邮箱已注册，请直接登录。"}), 400
    if action == 'login' and not user:
        return jsonify({"error": "该邮箱未注册，请先注册。"}), 400

    # 3. 生成 6 位邮件验证码
    code = str(random.randint(100000, 999999))
    expires = datetime.utcnow() + timedelta(minutes=5)
    
    vc = VerificationCode(email=email, code=code, expires_at=expires)
    user_db_session.add(vc)
    user_db_session.commit()

    # 4. 发送邮件
    # 4. 发送邮件
    try:
        # 获取你在配置里写的官方邮箱
        sender_email = app.config['MAIL_USERNAME'] 
        
        # 🌟 【关键】：去掉别名元组，直接传入干净的 sender_email 字符串
        # 换一个看起来像正式通知的标题，避开“测试”、“验证码”等高危词
        msg = Message("Welcome to TiAgent - Account Verification", sender=sender_email, recipients=[email])
        msg.body = f"Hello,\n\nThank you for registering at TiAgent.\n\nYour secure code is: {code}\n\nPlease enter this to complete your action. This code is valid for 5 minutes.\n\nBest regards,\nTiAgent Team"
        
        mail.send(msg)
        return jsonify({"message": "邮件发送成功，请查收！"})
    except Exception as e:
        print(f"\n❌ 邮件发送致命错误: {str(e)}\n") 
        return jsonify({"error": f"Debug报错: {str(e)}"}), 500
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
        # 4. 持久化本次对话到用户数据库
        new_user_msg = ChatMessage(session_id=session_id, role='user', content=user_query)
        new_agent_msg = ChatMessage(session_id=session_id, role='agent', content=answer)
        user_db_session.add(new_user_msg)
        user_db_session.add(new_agent_msg)
        
        # 🌟 5. 自动浓缩标题逻辑 (如果是第一句话，则更新 Session 标题)
        session_record = user_db_session.query(ChatSession).filter_by(id=session_id).first()
        if session_record and session_record.title == "New Conversation":
            # 在后台偷偷调用大模型生成标题
            new_title = generate_session_title(user_query)
            session_record.title = new_title

        user_db_session.commit()

        return jsonify({"answer": answer})
    except Exception as e:
        user_db_session.rollback()
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    # 使用 host='0.0.0.0' 以允许外部访问
    app.run(host='0.0.0.0', port=5000, debug=True)