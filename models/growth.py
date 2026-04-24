"""
Hermes-lite 成长引擎模型。

用于把 Qclaw / WorkBuddy / 平台调度器的执行轨迹沉淀为复盘记录和技能候选。
"""

from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, JSON, String, Text

from models.database import Base


class GrowthReview(Base):
    """
    Agent 事件复盘记录。

    每条记录对应一批 AgentEvent 的压缩总结，用于管理者观察和后续调度规则优化。
    """

    __tablename__ = "growth_reviews"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    review_id = Column(String(60), unique=True, nullable=False, index=True)
    trigger = Column(String(30), default="auto", nullable=False, index=True)
    status = Column(String(30), default="completed", nullable=False, index=True)

    window_start_event_id = Column(Integer, nullable=True, index=True)
    window_end_event_id = Column(Integer, nullable=True, index=True)
    events_count = Column(Integer, default=0, nullable=False)

    agent_summary = Column(JSON, default=dict, nullable=False)
    event_summary = Column(JSON, default=dict, nullable=False)
    observations = Column(JSON, default=list, nullable=False)
    memory_updates = Column(JSON, default=list, nullable=False)
    next_actions = Column(JSON, default=list, nullable=False)
    skill_candidate_ids = Column(JSON, default=list, nullable=False)
    summary = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def to_dict(self):
        return {
            "id": self.id,
            "review_id": self.review_id,
            "trigger": self.trigger,
            "status": self.status,
            "window_start_event_id": self.window_start_event_id,
            "window_end_event_id": self.window_end_event_id,
            "events_count": self.events_count,
            "agent_summary": self.agent_summary,
            "event_summary": self.event_summary,
            "observations": self.observations,
            "memory_updates": self.memory_updates,
            "next_actions": self.next_actions,
            "skill_candidate_ids": self.skill_candidate_ids,
            "summary": self.summary,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SkillCandidate(Base):
    """
    Agent 自动发现的技能候选。

    默认只是草稿，必须经过管理者审核后才适合发布到 skill.md 或独立 Skill 仓库。
    """

    __tablename__ = "skill_candidates"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    candidate_id = Column(String(60), unique=True, nullable=False, index=True)
    review_id = Column(String(60), nullable=True, index=True)

    name = Column(String(120), nullable=False, index=True)
    title = Column(String(160), nullable=False)
    status = Column(String(30), default="draft", nullable=False, index=True)
    confidence = Column(Integer, default=50, nullable=False)

    trigger_reason = Column(Text, nullable=True)
    suggested_steps = Column(JSON, default=list, nullable=False)
    source_event_ids = Column(JSON, default=list, nullable=False)
    safety_notes = Column(JSON, default=list, nullable=False)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "candidate_id": self.candidate_id,
            "review_id": self.review_id,
            "name": self.name,
            "title": self.title,
            "status": self.status,
            "confidence": self.confidence,
            "trigger_reason": self.trigger_reason,
            "suggested_steps": self.suggested_steps,
            "source_event_ids": self.source_event_ids,
            "safety_notes": self.safety_notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
