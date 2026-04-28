"""
A2A 消息格式定义
定义 Agent 之间的通信协议
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import uuid


class Intent(str, Enum):
    """
    A2A 消息意图类型
    """
    # 车辆上架
    SELL_LISTING = "sell_listing"
    # 询价
    PRICE_INQUIRY = "price_inquiry"
    # 议价
    PRICE_NEGOTIATE = "price_negotiate"
    # 达成交易意向
    DEAL_INTENT = "deal_intent"
    # 反向团购
    REVERSE_GROUP_BUY = "reverse_group_buy"
    # 消息传递
    MESSAGE = "message"
    # 协作请求
    COLLABORATION = "collaboration"
    # 信任验证
    TRUST_VERIFY = "trust_verify"


class Action(str, Enum):
    """
    消息动作类型
    """
    # 发送
    SEND = "send"
    # 回复
    REPLY = "reply"
    # 转发
    FORWARD = "forward"
    # 确认
    CONFIRM = "confirm"
    # 拒绝
    REJECT = "reject"
    # 取消
    CANCEL = "cancel"


@dataclass
class A2AMessage:
    """
    A2A 消息格式
    平台路由和记忆查询的基础数据结构
    """
    # 消息唯一标识
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    # 发送方 Agent ID
    from_agent: str = ""
    # 接收方 Agent ID
    to_agent: str = ""
    # 发送方用户 ID
    from_user_id: int = 0
    # 接收方用户 ID
    to_user_id: int = 0
    
    # 消息意图
    intent: str = Intent.MESSAGE.value
    # 动作类型
    action: str = Action.SEND.value
    
    # 消息载荷
    payload: Dict[str, Any] = field(default_factory=dict)
    
    # 相关车辆 ID
    related_car_id: Optional[str] = None
    
    # 会话 ID（用于消息关联）
    session_id: Optional[str] = None
    # 父消息 ID（用于回复链）
    parent_message_id: Optional[str] = None
    
    # 时间戳
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    
    # 消息状态
    status: str = "pending"
    # 是否为系统内部消息（不展示在公开对话流中）
    is_system: bool = False
    # 错误信息
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "A2AMessage":
        """从字典创建"""
        return cls(**data)
    
    def create_reply(self, payload: Dict[str, Any] = None, content: str = None) -> "A2AMessage":
        """创建回复消息"""
        return A2AMessage(
            from_agent=self.to_agent,
            to_agent=self.from_agent,
            from_user_id=self.to_user_id,
            to_user_id=self.from_user_id,
            intent=self.intent,
            action=Action.REPLY.value,
            payload=payload or {},
            related_car_id=self.related_car_id,
            session_id=self.session_id,
            parent_message_id=self.id,
            is_system=self.is_system
        )


class MessageBuilder:
    """
    A2A 消息构建器
    便捷创建各类意图的消息
    """
    
    @staticmethod
    def create_sell_listing(
        from_user_id: int,
        to_user_id: int,
        car_data: Dict[str, Any],
        from_agent: str = None,
        to_agent: str = None
    ) -> A2AMessage:
        """创建车辆上架消息"""
        return A2AMessage(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            from_agent=from_agent or f"user_{from_user_id}",
            to_agent=to_agent or f"user_{to_user_id}",
            intent=Intent.SELL_LISTING.value,
            payload={
                "action": "listing",
                "car": car_data
            }
        )
    
    @staticmethod
    def create_price_inquiry(
        from_user_id: int,
        to_user_id: int,
        car_id: str,
        inquiry_price: float = None,
        message: str = None
    ) -> A2AMessage:
        """创建询价消息"""
        return A2AMessage(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            from_agent=f"user_{from_user_id}",
            to_agent=f"user_{to_user_id}",
            intent=Intent.PRICE_INQUIRY.value,
            payload={
                "car_id": car_id,
                "inquiry_price": inquiry_price,
                "message": message
            },
            related_car_id=car_id
        )
    
    @staticmethod
    def create_price_negotiate(
        from_user_id: int,
        to_user_id: int,
        car_id: str,
        current_price: float,
        proposed_price: float,
        reason: str = None
    ) -> A2AMessage:
        """创建议价消息"""
        return A2AMessage(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            from_agent=f"user_{from_user_id}",
            to_agent=f"user_{to_user_id}",
            intent=Intent.PRICE_NEGOTIATE.value,
            payload={
                "car_id": car_id,
                "current_price": current_price,
                "proposed_price": proposed_price,
                "reason": reason
            },
            related_car_id=car_id
        )
    
    @staticmethod
    def create_deal_intent(
        from_user_id: int,
        to_user_id: int,
        car_id: str,
        agreed_price: float,
        conditions: Dict[str, Any] = None
    ) -> A2AMessage:
        """创建成交意向消息"""
        return A2AMessage(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            from_agent=f"user_{from_user_id}",
            to_agent=f"user_{to_user_id}",
            intent=Intent.DEAL_INTENT.value,
            payload={
                "car_id": car_id,
                "agreed_price": agreed_price,
                "conditions": conditions or {}
            },
            related_car_id=car_id
        )
    
    @staticmethod
    def create_reverse_group_buy(
        from_user_id: int,
        car_type: str,
        target_price: float,
        min_participants: int = 3
    ) -> A2AMessage:
        """创建反向团购消息"""
        return A2AMessage(
            from_user_id=from_user_id,
            to_user_id=0,  # 广播消息
            from_agent=f"user_{from_user_id}",
            to_agent="platform",
            intent=Intent.REVERSE_GROUP_BUY.value,
            payload={
                "car_type": car_type,
                "target_price": target_price,
                "min_participants": min_participants,
                "current_participants": 1
            }
        )
    
    @staticmethod
    def create_message(
        from_user_id: int,
        to_user_id: int,
        content: str,
        intent: str = Intent.MESSAGE.value
    ) -> A2AMessage:
        """创建普通消息"""
        return A2AMessage(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            from_agent=f"user_{from_user_id}",
            to_agent=f"user_{to_user_id}",
            intent=intent,
            payload={"content": content}
        )
