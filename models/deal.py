"""
成交模型
记录 Agent 协商达成意向后的人类决策与成交结果
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from models.database import Base


class Deal(Base):
    """
    成交记录表
    从 deal_ready 的匹配记录创建，由人类确认/拒绝/还价
    """
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    # 成交唯一标识
    deal_id = Column(String(50), unique=True, index=True, nullable=False)

    # 关联匹配记录
    match_id = Column(String(50), ForeignKey("match_pool.match_id"), nullable=False)

    # 关联用户与车辆
    car_id = Column(String(50), ForeignKey("car_memories.car_id"), nullable=False)
    buyer_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # 成交价格（由协商确定）
    agreed_price = Column(Float, nullable=False, comment="协商成交价")

    # 状态: pending/accepted/rejected/countered
    status = Column(String(20), default="pending", nullable=False, comment="成交状态")

    # 还价（如果人类提出不同价格）
    counter_price = Column(Float, nullable=True, comment="人类还价")

    # 决策记录
    decided_by = Column(Integer, nullable=True, comment="做出决策的用户ID")
    decision_note = Column(Text, nullable=True, comment="决策备注")

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    match = relationship("MatchPool")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "deal_id": self.deal_id,
            "match_id": self.match_id,
            "car_id": self.car_id,
            "buyer_id": self.buyer_id,
            "seller_id": self.seller_id,
            "agreed_price": self.agreed_price,
            "status": self.status,
            "counter_price": self.counter_price,
            "decided_by": self.decided_by,
            "decision_note": self.decision_note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
