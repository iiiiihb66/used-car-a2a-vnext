"""
需求池模型
记录用户的购车需求
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.database import Base


class DemandPool(Base):
    """
    需求池表
    记录用户的购车需求
    """
    __tablename__ = "demand_pool"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # 需求唯一标识
    demand_id = Column(String(50), unique=True, index=True, nullable=False)
    
    # 用户关联
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # 需求类型
    car_type = Column(String(50), nullable=False, comment="想要的车型类别")
    brand_preference = Column(String(100), nullable=True, comment="品牌偏好")
    series_preference = Column(String(100), nullable=True, comment="车系偏好")
    
    # 预算范围
    budget_min = Column(Float, default=0, nullable=False, comment="最低预算")
    budget_max = Column(Float, nullable=False, comment="最高预算")
    
    # 地区偏好
    region = Column(String(50), nullable=True, comment="期望地区")
    city = Column(String(50), nullable=True, comment="期望城市")
    
    # 车龄偏好
    year_min = Column(Integer, nullable=True, comment="接受的最早年份")
    year_max = Column(Integer, nullable=True, comment="接受的最晚年份")
    
    # 里程偏好
    mileage_max = Column(Float, nullable=True, comment="可接受的最大里程")
    
    # 需求状态
    status = Column(String(20), default="active", nullable=False, comment="状态: active/paused/fulfilled/cancelled")
    priority = Column(Integer, default=5, nullable=False, comment="优先级 1-10")
    
    # 其他偏好
    preferences = Column(JSON, default=dict, comment="其他偏好设置")
    # 结构: {"color": "白色", "transmission": "自动", "fuel_type": "汽油", "configuration": [...]}
    
    # 备注
    notes = Column(String(500), nullable=True, comment="备注说明")
    
    # 匹配历史
    match_history = Column(JSON, default=list, comment="匹配历史")
    # 结构: [{"car_id": "xxx", "matched_at": "2024-01-15", "result": "interested/rejected"}, ...]
    
    # 提醒设置
    notify_enabled = Column(Integer, default=1, nullable=False, comment="是否开启提醒")
    
    # ==================== 扩展字段 (Phase 2) ====================
    last_match_at = Column(DateTime, nullable=True, comment="上次执行自动匹配的时间")
    match_count = Column(Integer, default=0, nullable=False, comment="当前有效匹配数")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    fulfilled_at = Column(DateTime, nullable=True, comment="满足时间")
    
    # 关系
    user = relationship("User", back_populates="demands")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "demand_id": self.demand_id,
            "user_id": self.user_id,
            "car_type": self.car_type,
            "brand_preference": self.brand_preference,
            "series_preference": self.series_preference,
            "budget_min": self.budget_min,
            "budget_max": self.budget_max,
            "region": self.region,
            "city": self.city,
            "year_min": self.year_min,
            "year_max": self.year_max,
            "mileage_max": self.mileage_max,
            "status": self.status,
            "priority": self.priority,
            "preferences": self.preferences,
            "notes": self.notes,
            "match_history": self.match_history,
            "notify_enabled": self.notify_enabled,
            "last_match_at": self.last_match_at.isoformat() if self.last_match_at else None,
            "match_count": self.match_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "fulfilled_at": self.fulfilled_at.isoformat() if self.fulfilled_at else None,
        }

    def add_match_record(self, car_id: str, result: str):
        """
        添加匹配记录
        """
        if self.match_history is None:
            self.match_history = []
        self.match_history.append({
            "car_id": car_id,
            "matched_at": datetime.utcnow().isoformat(),
            "result": result
        })

    def is_match(self, car: dict) -> bool:
        """
        判断车辆是否匹配此需求
        """
        # 检查预算
        if not (self.budget_min <= car.get("price", 0) <= self.budget_max):
            return False
        
        # 检查年份
        car_year = car.get("year", 0)
        if self.year_min and car_year < self.year_min:
            return False
        if self.year_max and car_year > self.year_max:
            return False
        
        # 检查里程
        if self.mileage_max and car.get("mileage", 0) > self.mileage_max:
            return False
        
        # 检查品牌（支持批量，以逗号分隔）
        if self.brand_preference:
            preferred_brands = [b.strip() for b in self.brand_preference.split(",") if b.strip()]
            if preferred_brands and car.get("brand", "") not in preferred_brands:
                return False
        
        return True
