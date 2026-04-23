"""
积分流水表
记录用户积分的收支明细
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.database import Base


class PointTransaction(Base):
    """
    积分流水表
    
    记录所有积分变动：
    - earn: 获得积分（录入档案、认证等）
    - redeem: 抵扣消费（验车费抵扣等）
    - boost: 置顶消耗（卖车优先展示）
    - gift: 转赠
    """
    __tablename__ = "point_transactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    # 交易类型
    transaction_type = Column(String(20), nullable=False, index=True, comment="earn/redeem/boost/gift")
    
    # 积分变动
    points_change = Column(Integer, nullable=False, comment="正数=获得，负数=消耗")
    balance_after = Column(Integer, nullable=False, comment="变动后余额")
    
    # 关联信息
    related_type = Column(String(20), nullable=True, comment="关联类型: maintenance/deal/inspection/boost")
    related_id = Column(String(50), nullable=True, comment="关联的记录ID")
    
    # 备注
    remark = Column(String(200), nullable=True, comment="说明")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    # 关系
    user = relationship("User", back_populates="point_transactions")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "transaction_type": self.transaction_type,
            "points_change": self.points_change,
            "balance_after": self.balance_after,
            "related_type": self.related_type,
            "related_id": self.related_id,
            "remark": self.remark,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
