"""
Agent 事件记忆表
记录外部 Agent 和平台调度器的关键动作、观察与结果。
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, JSON, String, Text

from models.database import Base


class AgentEvent(Base):
    """
    Agent 事件记忆。

    这不是聊天记录，而是结构化的执行轨迹，用于管理者复盘和后续调度器学习。
    """

    __tablename__ = "agent_events"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    actor_agent = Column(String(100), nullable=False, index=True, comment="Agent 名称")
    actor_role = Column(String(30), nullable=False, index=True, comment="buyer/seller/platform/admin")
    event_type = Column(String(50), nullable=False, index=True, comment="事件类型")
    status = Column(String(30), default="observed", nullable=False, index=True)

    user_id = Column(Integer, nullable=True, index=True)
    related_user_id = Column(Integer, nullable=True, index=True)
    related_car_id = Column(String(50), nullable=True, index=True)
    related_demand_id = Column(String(50), nullable=True, index=True)
    related_conversation_id = Column(String(100), nullable=True, index=True)

    input_snapshot = Column(JSON, default=dict, comment="输入/触发条件")
    output_snapshot = Column(JSON, default=dict, comment="输出/执行结果")
    observation = Column(Text, nullable=True, comment="自然语言观察")
    score = Column(Float, nullable=True, comment="可选评分")

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "actor_agent": self.actor_agent,
            "actor_role": self.actor_role,
            "event_type": self.event_type,
            "status": self.status,
            "user_id": self.user_id,
            "related_user_id": self.related_user_id,
            "related_car_id": self.related_car_id,
            "related_demand_id": self.related_demand_id,
            "related_conversation_id": self.related_conversation_id,
            "input_snapshot": self.input_snapshot,
            "output_snapshot": self.output_snapshot,
            "observation": self.observation,
            "score": self.score,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
