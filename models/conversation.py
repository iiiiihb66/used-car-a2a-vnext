"""
对话模型
记录 Agent 之间的对话历史
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from models.database import Base


class Conversation(Base):
    """
    对话历史表
    记录 A2A 消息历史
    """
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    
    # 消息唯一标识
    message_id = Column(String(100), unique=True, index=True, nullable=False)
    
    # 发送方和接收方
    from_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    to_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Agent 标识
    from_agent = Column(String(100), nullable=True, comment="发送方 Agent ID")
    to_agent = Column(String(100), nullable=True, comment="接收方 Agent ID")
    
    # 消息内容
    intent = Column(String(50), nullable=False, index=True, comment="意图类型")
    action = Column(String(50), nullable=True, comment="具体动作")
    payload = Column(JSON, default=dict, comment="消息载荷")
    content = Column(Text, nullable=True, comment="消息文本内容")
    
    # 消息状态
    status = Column(String(20), default="sent", nullable=False, comment="状态: sent/delivered/read/replied")
    is_system = Column(Integer, default=0, nullable=False, comment="是否系统消息")
    
    # 关联的车辆
    related_car_id = Column(String(50), ForeignKey("car_memories.car_id"), nullable=True)
    
    # 会话分组
    session_id = Column(String(100), index=True, nullable=True, comment="会话ID")
    parent_message_id = Column(String(100), nullable=True, comment="父消息ID（用于回复链）")
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    delivered_at = Column(DateTime, nullable=True)
    read_at = Column(DateTime, nullable=True)
    
    # 关系
    from_user = relationship("User", foreign_keys=[from_user_id], back_populates="conversations_sent")
    to_user = relationship("User", foreign_keys=[to_user_id], back_populates="conversations_received")
    related_car = relationship("CarMemory", foreign_keys=[related_car_id])

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "message_id": self.message_id,
            "from_user_id": self.from_user_id,
            "to_user_id": self.to_user_id,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "intent": self.intent,
            "action": self.action,
            "payload": self.payload,
            "content": self.content,
            "status": self.status,
            "is_system": self.is_system,
            "related_car_id": self.related_car_id,
            "session_id": self.session_id,
            "parent_message_id": self.parent_message_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @staticmethod
    def create_message(
        message_id: str,
        from_user_id: int,
        to_user_id: int,
        intent: str,
        payload: dict = None,
        content: str = None,
        from_agent: str = None,
        to_agent: str = None,
        related_car_id: str = None,
        session_id: str = None
    ):
        """
        创建消息的工厂方法
        """
        return Conversation(
            message_id=message_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            intent=intent,
            payload=payload or {},
            content=content,
            from_agent=from_agent,
            to_agent=to_agent,
            related_car_id=related_car_id,
            session_id=session_id
        )
