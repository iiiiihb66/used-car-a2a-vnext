"""
卖家举报表
记录买家对卖家的举报信息
"""

from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.database import Base


class SellerReport(Base):
    """
    卖家举报表
    
    记录买家对卖家的举报，用于：
    - 隐瞒事故
    - 调表（篡改里程）
    - 虚假宣传
    - 其他欺诈行为
    """
    __tablename__ = "seller_reports"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # 举报人信息
    reporter_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="举报者ID")
    
    # 被举报卖家信息
    seller_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True, comment="被举报卖家ID")
    
    # 关联车辆
    car_id = Column(String(50), nullable=True, index=True, comment="关联车辆ID")
    
    # 举报内容
    reason = Column(String(200), nullable=False, comment="举报原因")
    evidence = Column(Text, nullable=True, comment="证据（图片URL或描述）")
    
    # 审核状态
    # pending: 待审核, approved: 已通过, rejected: 已驳回
    status = Column(String(20), default="pending", nullable=False, index=True, comment="状态")
    
    # 审核信息
    reviewed_by = Column(String(50), nullable=True, comment="审核人")
    reviewed_at = Column(DateTime, nullable=True, comment="审核时间")
    review_remark = Column(String(200), nullable=True, comment="审核备注")
    
    # 惩罚标记
    penalty_applied = Column(Boolean, default=False, nullable=False, comment="是否已应用惩罚")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    reporter = relationship("User", foreign_keys=[reporter_id], backref="reports_made")
    seller = relationship("User", foreign_keys=[seller_id], backref="reports_received")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "reporter_id": self.reporter_id,
            "seller_id": self.seller_id,
            "car_id": self.car_id,
            "reason": self.reason,
            "evidence": self.evidence,
            "status": self.status,
            "reviewed_by": self.reviewed_by,
            "reviewed_at": self.reviewed_at.isoformat() if self.reviewed_at else None,
            "review_remark": self.review_remark,
            "penalty_applied": self.penalty_applied,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
