"""
车辆模型
包含车辆生命周期档案
已移除不可篡改的 JSON 字段，改为使用 CarLifecycleRecord 表
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from models.database import Base


class CarMemory(Base):
    """
    车辆生命周期档案表
    记录每辆车的完整生命周期信息
    
    注意：历史记录字段已移除，改为使用 car_lifecycle_records 表
    通过链式哈希确保不可篡改
    """
    __tablename__ = "car_memories"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # 车辆标识
    car_id = Column(String(50), unique=True, index=True, nullable=False, comment="车辆唯一标识")
    plate_number = Column(String(20), nullable=True, comment="车牌号")
    
    # 基本信息
    brand = Column(String(50), nullable=False, comment="品牌")
    series = Column(String(50), nullable=False, comment="车系")
    model = Column(String(100), nullable=False, comment="车型")
    year = Column(Integer, nullable=False, comment="年份")
    color = Column(String(20), nullable=True, comment="颜色")
    
    # 车辆状态
    current_status = Column(String(20), default="上架中", nullable=False, comment="当前状态")
    is_listed = Column(Boolean, default=False, nullable=False, comment="是否上架")
    
    # 价格信息
    price = Column(Float, nullable=False, comment="售价")
    original_price = Column(Float, nullable=True, comment="新车指导价")
    target_price = Column(Float, nullable=True, comment="车主心理价位")
    
    # 车辆参数
    mileage = Column(Float, nullable=False, comment="里程数")
    engine = Column(String(50), nullable=True, comment="发动机")
    transmission = Column(String(20), nullable=True, comment="变速箱")
    fuel_type = Column(String(20), nullable=True, comment="燃料类型")
    
    # 车辆配置
    configuration = Column(JSON, default=dict, comment="配置信息 JSON")
    
    # ==================== 历史记录已移除 ====================
    # maintenance_history, accident_history, valuation_history, ownership_history
    # 现在存储在 car_lifecycle_records 表中，通过链式哈希保证不可篡改
    # 使用 get_lifecycle_records() 方法查询
    
    # 车况评估（仅存储最新评估结果）
    condition_assessment = Column(JSON, default=dict, comment="车况评估报告")
    
    # 关联
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    owner = relationship("User", back_populates="cars")
    
    # 区域信息
    region = Column(String(50), nullable=True, comment="所在地区")
    city = Column(String(50), nullable=True, comment="城市")
    
    # 图片描述
    image_descriptions = Column(JSON, default=list, comment="车辆图片描述")
    
    # 链式记录验证状态
    chain_verified = Column(Integer, default=0, nullable=False, comment="链式记录是否已验证 0-否 1-是")
    last_chain_verify_at = Column(DateTime, nullable=True, comment="上次链式验证时间")
    
    # ==================== 置顶功能 ====================
    is_boosted = Column(Boolean, default=False, nullable=False, comment="是否置顶")
    boost_expiry = Column(DateTime, nullable=True, comment="置顶到期时间")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    listed_at = Column(DateTime, nullable=True, comment="上架时间")
    sold_at = Column(DateTime, nullable=True, comment="成交时间")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "car_id": self.car_id,
            "plate_number": self.plate_number,
            "brand": self.brand,
            "series": self.series,
            "model": self.model,
            "year": self.year,
            "color": self.color,
            "current_status": self.current_status,
            "is_listed": self.is_listed,
            "price": self.price,
            "original_price": self.original_price,
            "target_price": self.target_price,
            "mileage": self.mileage,
            "engine": self.engine,
            "transmission": self.transmission,
            "fuel_type": self.fuel_type,
            "configuration": self.configuration,
            "condition_assessment": self.condition_assessment,
            "owner_id": self.owner_id,
            "region": self.region,
            "city": self.city,
            "image_descriptions": self.image_descriptions,
            "chain_verified": bool(self.chain_verified),
            "last_chain_verify_at": self.last_chain_verify_at.isoformat() if self.last_chain_verify_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "listed_at": self.listed_at.isoformat() if self.listed_at else None,
            "sold_at": self.sold_at.isoformat() if self.sold_at else None,
            # 置顶功能
            "is_boosted": self.is_boosted,
            "boost_expiry": self.boost_expiry.isoformat() if self.boost_expiry else None,
        }

    def get_lifecycle_records(self, db, record_type: str = None) -> list:
        """
        获取车辆生命周期记录（不可篡改）
        
        Args:
            db: 数据库会话
            record_type: 记录类型筛选（可选）
        
        Returns:
            记录列表
        """
        from models.car_lifecycle_record import CarLifecycleRecord
        
        query = db.query(CarLifecycleRecord).filter(
            CarLifecycleRecord.car_id == self.car_id
        )
        
        if record_type:
            query = query.filter(CarLifecycleRecord.record_type == record_type)
        
        records = query.order_by(CarLifecycleRecord.created_at.desc()).all()
        return [r.to_dict() for r in records]

    def get_maintenance_history(self, db) -> list:
        """获取保养记录"""
        return self.get_lifecycle_records(db, record_type="maintenance")

    def get_accident_history(self, db) -> list:
        """获取事故记录"""
        return self.get_lifecycle_records(db, record_type="accident")

    def get_price_history(self, db) -> list:
        """获取价格变更记录"""
        return self.get_lifecycle_records(db, record_type="price")

    def get_ownership_history(self, db) -> list:
        """获取所有权变更记录"""
        return self.get_lifecycle_records(db, record_type="ownership")

    def verify_chain(self, db) -> dict:
        """
        验证链式记录完整性
        
        Args:
            db: 数据库会话
        
        Returns:
            验证结果
        """
        from models.car_lifecycle_record import verify_car_chain
        
        result = verify_car_chain(db, self.car_id)
        
        # 更新验证状态
        self.chain_verified = 1 if result["valid"] else 0
        self.last_chain_verify_at = datetime.utcnow()
        db.commit()
        
        return result
