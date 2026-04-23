"""
车辆生命周期记录表（不可篡改）
采用链式哈希设计，确保数据完整性
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import hashlib
import json

from models.database import Base


class CarLifecycleRecord(Base):
    """
    车辆生命周期记录（不可篡改）
    
    采用链式哈希设计：
    - 每条记录包含 prev_hash（前一记录的哈希）
    - 当前记录的 record_hash 由内容 + prev_hash 计算
    - 支持可选的数字签名 signed_by
    
    记录类型：
    - maintenance: 保养记录
    - accident: 事故记录
    - price: 价格变更
    - ownership: 所有权变更
    """
    __tablename__ = "car_lifecycle_records"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # 车辆标识
    car_id = Column(String(50), index=True, nullable=False, comment="车辆ID")
    
    # 记录类型
    record_type = Column(String(20), nullable=False, comment="记录类型 maintenance/accident/price/ownership")
    
    # 记录内容（JSON）
    data = Column(JSON, nullable=False, comment="记录内容")
    
    # ==================== 不可篡改核心 ====================
    # 前一记录的 SHA256 哈希（创世块为 "0" * 64）
    prev_hash = Column(String(64), nullable=True, comment="前一记录哈希")
    
    # 当前记录的 SHA256 哈希
    record_hash = Column(String(64), nullable=False, comment="当前记录哈希")
    
    # 录入者（用户ID/4S店ID/平台）
    signed_by = Column(String(50), nullable=False, comment="录入者")
    
    # 数字签名（可选，用于增强信任）
    signature = Column(Text, nullable=True, comment="数字签名")
    
    # 默克尔树根（用于批量验证）
    merkle_root = Column(String(64), nullable=True, comment="默克尔树根")
    
    # ==================== 元数据 ====================
    # 记录是否已验证
    is_verified = Column(Integer, default=0, nullable=False, comment="是否已验证 0-否 1-是")
    
    # ==================== 平台审核字段 ====================
    # 验证状态：pending/approved/rejected
    verification_status = Column(String(20), default="pending", nullable=False, comment="验证状态 pending/approved/rejected")
    
    # 验证文档URL（用户上传的照片/PDF）
    verification_doc_url = Column(String(500), nullable=True, comment="验证文档URL")
    
    # 验证者（platform_admin 或 4S店ID）
    verified_by = Column(String(50), nullable=True, comment="验证者")
    
    # 验证时间
    verified_at = Column(DateTime, nullable=True, comment="验证时间")
    
    # 备注
    remark = Column(String(500), nullable=True, comment="备注")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 存储用于计算哈希的时间戳（确保验证一致性）
    hash_timestamp = Column(String(50), nullable=True, comment="哈希计算时间戳")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "car_id": self.car_id,
            "record_type": self.record_type,
            "data": self.data,
            "prev_hash": self.prev_hash,
            "record_hash": self.record_hash,
            "signed_by": self.signed_by,
            "signature": self.signature,
            "merkle_root": self.merkle_root,
            "is_verified": bool(self.is_verified),
            "verification_status": self.verification_status,
            "verification_doc_url": self.verification_doc_url,
            "verified_by": self.verified_by,
            "verified_at": self.verified_at.isoformat() if self.verified_at else None,
            "remark": self.remark,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "hash_timestamp": self.hash_timestamp
        }

    @staticmethod
    def compute_hash(car_id: str, record_type: str, data: dict, prev_hash: str, signed_by: str, timestamp: str) -> str:
        """
        计算记录的哈希值
        
        Args:
            car_id: 车辆ID
            record_type: 记录类型
            data: 记录内容
            prev_hash: 前一记录哈希
            signed_by: 录入者
            timestamp: 时间戳
        
        Returns:
            SHA256 哈希值
        """
        record_data = {
            "car_id": car_id,
            "record_type": record_type,
            "data": data,
            "prev_hash": prev_hash,
            "signed_by": signed_by,
            "timestamp": timestamp
        }
        content = json.dumps(record_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode('utf-8')).hexdigest()

    def verify_chain(self) -> bool:
        """
        验证链式哈希完整性
        
        Returns:
            是否验证通过
        """
        # 使用存储的时间戳进行验证（确保一致性）
        timestamp = self.hash_timestamp or (self.created_at.isoformat() if self.created_at else datetime.utcnow().isoformat())
        
        # 重新计算当前记录的哈希
        expected_hash = self.compute_hash(
            car_id=self.car_id,
            record_type=self.record_type,
            data=self.data,
            prev_hash=self.prev_hash or "0" * 64,
            signed_by=self.signed_by,
            timestamp=timestamp
        )
        
        return expected_hash == self.record_hash


def create_lifecycle_record(
    db,
    car_id: str,
    record_type: str,
    data: dict,
    signed_by: str,
    remark: str = None,
    auto_reward: bool = True
) -> dict:
    """
    创建生命周期记录（自动计算哈希 + 自动发积分）
    
    Args:
        db: 数据库会话
        car_id: 车辆ID
        record_type: 记录类型
        data: 记录内容
        signed_by: 录入者
        remark: 备注
        auto_reward: 是否自动发放积分（默认True）
    
    Returns:
        {"record": CarLifecycleRecord, "reward": dict or None}
    """
    # 获取上一条记录
    prev_record = db.query(CarLifecycleRecord).filter(
        CarLifecycleRecord.car_id == car_id
    ).order_by(CarLifecycleRecord.id.desc()).first()
    
    prev_hash = prev_record.record_hash if prev_record else "0" * 64
    
    # 统一用一个时间戳，避免 created_at 和 hash_timestamp 不一致
    now = datetime.utcnow()
    timestamp = now.isoformat()
    
    # 计算当前记录哈希
    record_hash = CarLifecycleRecord.compute_hash(
        car_id=car_id,
        record_type=record_type,
        data=data,
        prev_hash=prev_hash,
        signed_by=signed_by,
        timestamp=timestamp
    )
    
    # 创建记录
    record = CarLifecycleRecord(
        car_id=car_id,
        record_type=record_type,
        data=data,
        prev_hash=prev_hash,
        record_hash=record_hash,
        signed_by=signed_by,
        remark=remark,
        created_at=now,  # 使用同一个 now
        hash_timestamp=timestamp  # 使用同一个 timestamp
    )
    
    db.add(record)
    
    # 自动发放积分
    reward_result = None
    if auto_reward:
        from models.reputation import ReputationEngine
        engine = ReputationEngine(db)
        
        # 解析用户ID（signed_by 格式可能是 "user_1" / "1" / "platform_xxx"）
        user_id = 0
        try:
            if "_" in str(signed_by):
                parts = str(signed_by).split("_")
                # 尝试找到数字部分
                for part in reversed(parts):
                    if part.isdigit():
                        user_id = int(part)
                        break
            else:
                user_id = int(signed_by)
        except:
            user_id = 0
        
        # 判断验证状态（平台/4S店录入=已验证，用户录入=未验证）
        verified = (
            str(signed_by).startswith("platform") or 
            str(signed_by).startswith("4s_") or 
            str(signed_by).startswith("dealer_")
        )
        
        if user_id > 0:
            reward_result = engine.reward_for_record(
                user_id=user_id,
                record_type=record_type,
                verified=verified
            )
    
    db.commit()
    db.refresh(record)
    
    return {
        "record": record,
        "reward": reward_result
    }


def verify_car_chain(db, car_id: str) -> dict:
    """
    验证某车辆的所有记录链
    
    Args:
        db: 数据库会话
        car_id: 车辆ID
    
    Returns:
        验证结果
    """
    records = db.query(CarLifecycleRecord).filter(
        CarLifecycleRecord.car_id == car_id
    ).order_by(CarLifecycleRecord.id.asc()).all()
    
    if not records:
        return {"valid": True, "records": 0, "message": "无记录"}
    
    results = []
    for i, record in enumerate(records):
        valid = record.verify_chain()
        
        # 检查与前一条记录的链接
        if i > 0:
            prev_record = records[i - 1]
            chain_valid = record.prev_hash == prev_record.record_hash
        else:
            chain_valid = record.prev_hash == "0" * 64 or record.prev_hash is None
        
        results.append({
            "id": record.id,
            "record_type": record.record_type,
            "hash_valid": valid,
            "chain_valid": chain_valid,
            "created_at": record.created_at.isoformat() if record.created_at else None
        })
    
    all_valid = all(r["hash_valid"] and r["chain_valid"] for r in results)
    
    return {
        "valid": all_valid,
        "records": len(records),
        "details": results
    }


def verify_full_chain(db, car_id: str) -> dict:
    """
    验证整条哈希链的连续性（不只是单条记录）
    比 verify_car_chain 提供更详细的验证信息
    
    Returns:
        {
            "valid": True/False,
            "total_records": N,
            "broken_at": None 或记录ID,
            "records": [{"id": 1, "hash_valid": True, "chain_valid": True}, ...]
        }
    """
    records = db.query(CarLifecycleRecord).filter(
        CarLifecycleRecord.car_id == car_id
    ).order_by(CarLifecycleRecord.id.asc()).all()
    
    if not records:
        return {"valid": True, "total_records": 0, "message": "无记录"}
    
    results = []
    valid = True
    broken_at = None
    
    for i, record in enumerate(records):
        # 验证单条记录的哈希
        hash_valid = record.verify_chain()
        
        # 验证链的连续性
        chain_valid = True
        if i == 0:
            # 创世块：prev_hash 应该是 "0"*64 或 None
            if record.prev_hash and record.prev_hash != "0" * 64:
                chain_valid = False
                valid = False
                broken_at = record.id
        else:
            # 非创世块：prev_hash 必须等于上一条的 record_hash
            if record.prev_hash != records[i-1].record_hash:
                chain_valid = False
                valid = False
                broken_at = record.id
        
        results.append({
            "id": record.id,
            "record_type": record.record_type,
            "hash_valid": hash_valid,
            "chain_valid": chain_valid,
            "record_hash": (record.record_hash[:16] + "...") if record.record_hash else None,
            "prev_hash": (record.prev_hash[:16] + "...") if record.prev_hash else None,
            "signed_by": record.signed_by,
            "created_at": record.created_at.isoformat() if record.created_at else None
        })
    
    return {
        "valid": valid,
        "total_records": len(records),
        "broken_at": broken_at,
        "records": results
    }
