"""
用户模型
包含用户基础信息和用户画像
包含行为积分和信誉分
"""

from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.database import Base


class User(Base):
    """
    用户表
    核心用户模型，包含买家和卖家角色
    车商是 is_dealer=True 的特殊用户
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(100), nullable=False, comment="用户名称")
    email = Column(String(255), unique=True, index=True, nullable=False, comment="邮箱")
    phone = Column(String(20), nullable=True, comment="手机号")
    is_dealer = Column(Boolean, default=False, nullable=False, comment="是否车商")
    
    # ==================== 信誉与积分体系 ====================
    # 信誉分 0-100
    reputation_score = Column(Float, default=100.0, nullable=False, comment="信誉分 0-100")
    
    # 行为积分（可累积，用于兑换权益）
    behavior_points = Column(Integer, default=0, nullable=False, comment="行为积分")
    
    # 交易统计
    transaction_count = Column(Integer, default=0, nullable=False, comment="成交次数")
    successful_deals = Column(Integer, default=0, nullable=False, comment="成功交易数")
    
    # ==================== 风险控制体系 ====================
    # 风险等级: normal/warning/danger/banned
    risk_level = Column(String(20), default="normal", nullable=False, comment="风险等级")
    
    # 封禁到期时间
    banned_until = Column(DateTime, nullable=True, comment="封禁到期时间")
    
    # 警告次数
    warning_count = Column(Integer, default=0, nullable=False, comment="警告次数")
    
    # ==================== 身份验证 ====================
    is_identity_verified = Column(Boolean, default=False, nullable=False, comment="是否已实名认证")
    id_card_verified = Column(Boolean, default=False, nullable=False, comment="是否已身份证认证")
    
    # ==================== 促活钩子字段 ====================
    # 免费估价券
    free_evaluation_count = Column(Integer, default=0, nullable=False, comment="免费估价券数量")
    
    # 首录奖励标记
    has_first_record_bonus = Column(Boolean, default=False, nullable=False, comment="是否已领取首录奖励")
    
    # 置顶奖励标记（录入5条档案后获得）
    has_listing_boost = Column(Boolean, default=False, nullable=False, comment="是否有置顶奖励")
    
    # 档案记录数
    record_count = Column(Integer, default=0, nullable=False, comment="档案记录数")
    
    # 贷款召回相关
    loan_end_date = Column(DateTime, nullable=True, comment="贷款结束日期")
    last_recall_at = Column(DateTime, nullable=True, comment="上次召回时间")
    recall_count = Column(Integer, default=0, nullable=False, comment="召回次数")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 最后活跃时间
    last_active_at = Column(DateTime, nullable=True, comment="最后活跃时间")
    
    # 关系
    persona = relationship("UserPersona", back_populates="user", uselist=False, cascade="all, delete-orphan")
    cars = relationship("CarMemory", back_populates="owner", cascade="all, delete-orphan")
    demands = relationship("DemandPool", back_populates="user", cascade="all, delete-orphan")
    social_graph = relationship("SocialGraph", back_populates="user", uselist=False, cascade="all, delete-orphan")
    conversations_sent = relationship("Conversation", foreign_keys="Conversation.from_user_id", back_populates="from_user")
    conversations_received = relationship("Conversation", foreign_keys="Conversation.to_user_id", back_populates="to_user")
    point_transactions = relationship("PointTransaction", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "is_dealer": self.is_dealer,
            "reputation_score": self.reputation_score,
            "behavior_points": self.behavior_points,
            "transaction_count": self.transaction_count,
            "successful_deals": self.successful_deals,
            # 风险控制字段
            "risk_level": self.risk_level or "normal",
            "banned_until": self.banned_until.isoformat() if self.banned_until else None,
            "warning_count": self.warning_count or 0,
            "is_identity_verified": self.is_identity_verified,
            "id_card_verified": self.id_card_verified,
            "last_active_at": self.last_active_at.isoformat() if self.last_active_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            # 促活钩子字段
            "free_evaluation_count": self.free_evaluation_count,
            "has_first_record_bonus": self.has_first_record_bonus,
            "has_listing_boost": self.has_listing_boost,
            "record_count": self.record_count,
            "loan_end_date": self.loan_end_date.isoformat() if self.loan_end_date else None,
            "last_recall_at": self.last_recall_at.isoformat() if self.last_recall_at else None,
            "recall_count": self.recall_count,
        }
    
    def get_trust_level(self) -> str:
        """
        获取信任等级
        
        Returns:
            信任等级：极高/高/中/低
        """
        if self.reputation_score >= 90:
            return "极高"
        elif self.reputation_score >= 75:
            return "高"
        elif self.reputation_score >= 50:
            return "中"
        else:
            return "低"


class UserPersona(Base):
    """
    用户画像表
    每个用户同时拥有买家画像和卖家画像
    """
    __tablename__ = "user_personas"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # 买家画像 JSON 结构
    buyer_persona = Column(JSON, default=dict, nullable=False, comment="买家画像")
    # 卖家画像 JSON 结构
    seller_persona = Column(JSON, default=dict, nullable=False, comment="卖家画像")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    user = relationship("User", back_populates="persona")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "buyer_persona": self.buyer_persona,
            "seller_persona": self.seller_persona,
        }

    @staticmethod
    def create_default_buyer_persona():
        """创建默认买家画像"""
        return {
            "preferred_brands": [],
            "preferred_types": [],
            "budget_range": {"min": 0, "max": 500000},
            "preferred_regions": [],
            "evaluation_criteria": ["价格", "车况", "保值率"],
            "negotiation_style": "温和型",
            "patience_level": "中等"
        }
    
    @staticmethod
    def create_default_seller_persona():
        """创建默认卖家画像"""
        return {
            "selling_brands": [],
            "selling_types": [],
            "price_expectation": "市场价",
            "negotiation_flexibility": "中等",
            "preferred_regions": [],
            "service_level": "标准"
        }
