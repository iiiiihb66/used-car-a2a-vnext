"""
议价历史模型
记录用户议价过程
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
from datetime import datetime
from models.database import Base


class NegotiationHistory(Base):
    """
    议价历史表
    记录用户议价过程和结果
    """
    __tablename__ = "negotiation_history"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="用户ID")
    car_id = Column(String(50), nullable=True, index=True, comment="车辆ID")
    
    # 报价信息
    proposed_price = Column(Float, nullable=False, comment="用户报价")
    
    # 结果（pending-待处理/accepted-接受/rejected-拒绝/counter_offered-还价）
    outcome = Column(String(20), default="pending", comment="议价结果")
    
    # 备注
    remark = Column(String(500), nullable=True, comment="备注")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "car_id": self.car_id,
            "proposed_price": self.proposed_price,
            "outcome": self.outcome,
            "remark": self.remark,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
