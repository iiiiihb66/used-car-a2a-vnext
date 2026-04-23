"""
数据库配置模块
支持 SQLite 本地开发，预留 PostgreSQL + pgvector 接口
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 数据库路径配置
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DB_PATH, exist_ok=True)

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    f"sqlite:///{os.path.join(DB_PATH, 'c2c_platform.db')}"
)

# PostgreSQL 生产环境配置示例（预留接口）
# DATABASE_URL = os.getenv(
#     "DATABASE_URL",
#     "postgresql://user:password@localhost:5432/c2c_platform"
# )
# pgvector 配置（用于向量相似度搜索）
# CREATE EXTENSION IF NOT EXISTS vector;
# CREATE TABLE car_embeddings (
#     id SERIAL PRIMARY KEY,
#     car_id INTEGER REFERENCES cars(id),
#     embedding vector(1536)
# );

# 创建引擎
if DATABASE_URL.startswith("sqlite"):
    # SQLite 配置
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False
    )
else:
    # PostgreSQL 配置
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Session 工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明基类
Base = declarative_base()


def get_db():
    """
    获取数据库会话的依赖函数
    用于 FastAPI 的 Depends 注入
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_database():
    """
    初始化数据库，创建所有表结构
    
    包含的表：
    - users: 用户表
    - user_personas: 用户画像表
    - car_memories: 车辆档案表
    - car_lifecycle_records: 车辆生命周期记录表（不可篡改）
    - conversation: 对话历史表
    - social_graph: 社交图谱表
    - demand_pool: 需求池表
    - negotiation_history: 议价历史表
    - point_transactions: 积分流水表
    - seller_reports: 卖家举报表
    """
    from models.user import User, UserPersona
    from models.car import CarMemory
    from models.car_lifecycle_record import CarLifecycleRecord
    from models.conversation import Conversation
    from models.social_graph import SocialGraph
    from models.demand import DemandPool
    from models.negotiation import NegotiationHistory
    from models.point_transaction import PointTransaction
    from models.seller_report import SellerReport
    
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库表结构创建完成")


def reset_database():
    """
    重置数据库（删除所有表后重建）
    用于开发环境
    """
    from models.user import User, UserPersona
    from models.car import CarMemory
    from models.car_lifecycle_record import CarLifecycleRecord
    from models.conversation import Conversation
    from models.social_graph import SocialGraph
    from models.demand import DemandPool
    from models.negotiation import NegotiationHistory
    from models.point_transaction import PointTransaction
    from models.seller_report import SellerReport
    
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("✅ 数据库已重置")
