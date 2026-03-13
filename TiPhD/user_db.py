import os
from sqlalchemy import create_engine, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USER_DB_PATH = os.path.join(BASE_DIR, 'user_system.db')

UserBase = declarative_base()
user_engine = create_engine(f'sqlite:///{USER_DB_PATH}')
UserSession = sessionmaker(bind=user_engine)
user_db_session = UserSession()

# 继承 UserMixin 以完美支持 Flask-Login
class User(UserBase, UserMixin):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(120), unique=True, nullable=False) # 使用邮箱登录
    password_hash = Column(String(256), nullable=False) # 存储加密后的哈希值

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class ChatSession(UserBase):
    __tablename__ = 'chat_sessions'
    id = Column(String(50), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    title = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)

class ChatMessage(UserBase):
    __tablename__ = 'chat_messages'
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(50), ForeignKey('chat_sessions.id'))
    role = Column(String(10)) 
    content = Column(Text)
    timestamp = Column(DateTime, default=datetime.utcnow)
# ... [保留原有的 User, ChatSession, ChatMessage 表] ...

class VerificationCode(UserBase):
    __tablename__ = 'verification_codes'
    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(120), nullable=False)
    code = Column(String(6), nullable=False)
    expires_at = Column(DateTime, nullable=False)

# 确保这行代码在最底下，用于自动创建新表
UserBase.metadata.create_all(user_engine)

# 自动创建最新的表结构
UserBase.metadata.create_all(user_engine)