"""
匹配模型
记录需求与车源的匹配关系及状态
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.database import Base


class MatchPool(Base):
    """
    匹配池表
    记录需求与车源的匹配建议
    """
    __tablename__ = "match_pool"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # 匹配唯一标识
    match_id = Column(String(50), unique=True, index=True, nullable=False)
    
    # 关联
    demand_id = Column(String(50), ForeignKey("demand_pool.demand_id"), nullable=False)
    car_id = Column(String(50), ForeignKey("car_memories.car_id"), nullable=False)
    
    # 匹配评价
    match_score = Column(Float, default=0.0, nullable=False, comment="匹配分 0-100")
    match_reason = Column(String(500), nullable=True, comment="匹配原因/标签")
    
    # 匹配状态: new/interested/rejected/negotiating/deal_ready/failed
    status = Column(String(20), default="new", nullable=False, comment="匹配状态")
    
    # 关联 Session (如果已发起协商)
    session_id = Column(String(50), nullable=True, comment="关联的协商会话 ID")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关系
    demand = relationship("DemandPool")
    car = relationship("CarMemory")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "match_id": self.match_id,
            "demand_id": self.demand_id,
            "car_id": self.car_id,
            "match_score": self.match_score,
            "match_reason": self.match_reason,
            "status": self.status,
            "session_id": self.session_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
