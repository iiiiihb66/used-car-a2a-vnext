"""
Hermes-lite Growth Engine.

把 Agent 事件压缩成可复盘的管理者视图，并从重复模式中生成技能候选。
当前使用确定性规则，后续可在这里接入腾讯混元做更强总结。
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy.orm import Session

from models.agent_event import AgentEvent
from models.growth import GrowthReview, SkillCandidate


class GrowthEngine:
    DEFAULT_INTERVAL = 10

    def __init__(self, db: Session):
        self.db = db

    def maybe_auto_review(self, interval: int = DEFAULT_INTERVAL) -> Dict[str, Any]:
        latest_event = self.db.query(AgentEvent).order_by(AgentEvent.id.desc()).first()
        if not latest_event:
            return {"success": True, "triggered": False, "reason": "no_events"}

        last_review = self.db.query(GrowthReview).order_by(GrowthReview.id.desc()).first()
        last_event_id = last_review.window_end_event_id if last_review else 0
        pending_count = (
            self.db.query(AgentEvent)
            .filter(AgentEvent.id > (last_event_id or 0))
            .count()
        )
        if pending_count < interval:
            return {
                "success": True,
                "triggered": False,
                "reason": "not_enough_events",
                "pending_events": pending_count,
                "interval": interval,
            }

        return self.run_review(
            trigger="auto",
            after_event_id=last_event_id or 0,
            limit=interval,
            min_events=interval,
        )

    def run_review(
        self,
        trigger: str = "manual",
        after_event_id: Optional[int] = None,
        limit: int = 30,
        min_events: int = 1,
    ) -> Dict[str, Any]:
        query = self.db.query(AgentEvent)
        if after_event_id is None:
            last_review = self.db.query(GrowthReview).order_by(GrowthReview.id.desc()).first()
            after_event_id = last_review.window_end_event_id if last_review else 0
        if after_event_id:
            query = query.filter(AgentEvent.id > after_event_id)

        events = query.order_by(AgentEvent.id.asc()).limit(limit).all()
        if len(events) < min_events:
            return {
                "success": True,
                "triggered": False,
                "reason": "not_enough_events",
                "events_count": len(events),
                "min_events": min_events,
            }

        review_id = f"GR-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}"
        agent_summary = self._summarize_agents(events)
        event_summary = self._summarize_events(events)
        observations = self._collect_observations(events)
        memory_updates = self._build_memory_updates(events, event_summary)
        next_actions = self._build_next_actions(event_summary)

        review = GrowthReview(
            review_id=review_id,
            trigger=trigger,
            status="completed",
            window_start_event_id=events[0].id,
            window_end_event_id=events[-1].id,
            events_count=len(events),
            agent_summary=agent_summary,
            event_summary=event_summary,
            observations=observations,
            memory_updates=memory_updates,
            next_actions=next_actions,
            skill_candidate_ids=[],
            summary=self._build_summary(events, event_summary, next_actions),
        )
        self.db.add(review)
        self.db.flush()

        skill_candidates = self._create_skill_candidates(review_id, events, event_summary)
        review.skill_candidate_ids = [candidate.candidate_id for candidate in skill_candidates]

        self.db.commit()
        self.db.refresh(review)

        return {
            "success": True,
            "triggered": True,
            "review": review.to_dict(),
            "skill_candidates": [candidate.to_dict() for candidate in skill_candidates],
        }

    def list_reviews(self, limit: int = 50) -> List[Dict[str, Any]]:
        rows = (
            self.db.query(GrowthReview)
            .order_by(GrowthReview.created_at.desc())
            .limit(limit)
            .all()
        )
        return [row.to_dict() for row in rows]

    def list_skill_candidates(self, status: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        query = self.db.query(SkillCandidate)
        if status:
            query = query.filter(SkillCandidate.status == status)
        rows = query.order_by(SkillCandidate.created_at.desc()).limit(limit).all()
        return [row.to_dict() for row in rows]

    def _summarize_agents(self, events: List[AgentEvent]) -> Dict[str, Any]:
        agents = Counter(event.actor_agent for event in events)
        roles = Counter(event.actor_role for event in events)
        statuses = Counter(event.status for event in events)
        return {
            "agents": dict(agents),
            "roles": dict(roles),
            "statuses": dict(statuses),
            "most_active_agent": agents.most_common(1)[0][0] if agents else None,
        }

    def _summarize_events(self, events: List[AgentEvent]) -> Dict[str, Any]:
        event_types = Counter(event.event_type for event in events)
        failures = [
            event for event in events
            if event.status == "failed"
            or "fail" in event.event_type
            or "empty" in event.event_type
            or "error" in event.event_type
        ]
        successes = [event for event in events if event.status == "succeeded"]
        return {
            "event_types": dict(event_types),
            "failed_or_empty_count": len(failures),
            "succeeded_count": len(successes),
            "failure_event_ids": [event.id for event in failures],
            "success_event_ids": [event.id for event in successes],
        }

    def _collect_observations(self, events: List[AgentEvent]) -> List[Dict[str, Any]]:
        observations = []
        for event in events:
            if event.observation:
                observations.append({
                    "event_id": event.id,
                    "actor_agent": event.actor_agent,
                    "event_type": event.event_type,
                    "observation": event.observation,
                })
        return observations[-12:]

    def _build_memory_updates(
        self,
        events: List[AgentEvent],
        event_summary: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        updates = []
        event_types = event_summary["event_types"]
        if event_types.get("match_empty", 0) or event_summary["failed_or_empty_count"] > 0:
            updates.append({
                "memory_type": "demand_failure_pattern",
                "content": "出现匹配为空或失败事件，需要记录预算、品牌、城市与车源供给缺口。",
                "source_event_ids": event_summary["failure_event_ids"],
            })
        if event_types.get("car_published", 0):
            updates.append({
                "memory_type": "supply_growth",
                "content": "车商 Agent 正在补充车源，应继续检查车档完整度与需求命中率。",
                "source_event_ids": [event.id for event in events if event.event_type == "car_published"],
            })
        if event_types.get("inquiry_sent", 0) or event_types.get("price_negotiate", 0):
            updates.append({
                "memory_type": "negotiation_trace",
                "content": "询价或议价事件可用于沉淀买卖双方沟通风格和合理价格区间。",
                "source_event_ids": [
                    event.id for event in events
                    if event.event_type in {"inquiry_sent", "price_negotiate"}
                ],
            })
        return updates

    def _build_next_actions(self, event_summary: Dict[str, Any]) -> List[str]:
        event_types = event_summary["event_types"]
        actions = []
        if event_types.get("match_empty", 0) or event_summary["failed_or_empty_count"] > 0:
            actions.append("让平台调度 Agent 汇总未匹配需求，并提醒车商 Agent 补充对应预算/城市/车型车源。")
            actions.append("让买家 Agent 给出可放宽项：预算、品牌、车龄、城市或里程。")
        if event_types.get("car_published", 0):
            actions.append("对新增车源触发车档完整度检查，缺失维保/事故/价格记录时提醒卖家补档。")
        if event_types.get("inquiry_sent", 0) or event_types.get("price_negotiate", 0):
            actions.append("把询价和议价结果写回 Agent 事件，用于下一轮价格区间建议。")
        if not actions:
            actions.append("继续记录 Qclaw / WorkBuddy 事件，累计更多样本后生成更可靠的技能候选。")
        return actions

    def _build_summary(
        self,
        events: List[AgentEvent],
        event_summary: Dict[str, Any],
        next_actions: List[str],
    ) -> str:
        event_type_text = ", ".join(
            f"{name}={count}" for name, count in event_summary["event_types"].items()
        )
        return (
            f"本轮复盘覆盖 {len(events)} 条 Agent 事件，事件分布：{event_type_text or '无'}。"
            f"建议优先动作：{next_actions[0]}"
        )

    def _create_skill_candidates(
        self,
        review_id: str,
        events: List[AgentEvent],
        event_summary: Dict[str, Any],
    ) -> List[SkillCandidate]:
        candidates = []
        event_types = event_summary["event_types"]

        if event_types.get("match_empty", 0) or event_summary["failed_or_empty_count"] >= 2:
            candidates.append(self._upsert_skill_candidate(
                review_id=review_id,
                name="unmatched-demand-followup",
                title="未匹配需求跟进 Skill",
                confidence=75,
                trigger_reason="多次出现匹配为空或失败事件，需要标准化买家放宽建议与车商补车流程。",
                suggested_steps=[
                    "读取未匹配需求的预算、品牌、城市、车型和里程约束。",
                    "生成买家可放宽项建议。",
                    "生成车商补车提示，并记录是否响应。",
                    "24 小时后复查是否新增匹配。",
                ],
                source_event_ids=event_summary["failure_event_ids"],
            ))

        if event_types.get("car_published", 0):
            car_event_ids = [event.id for event in events if event.event_type == "car_published"]
            candidates.append(self._upsert_skill_candidate(
                review_id=review_id,
                name="car-profile-completeness-check",
                title="车档完整度检查 Skill",
                confidence=70,
                trigger_reason="车源发布后需要固定检查维保、事故、价格、图片和链式记录完整度。",
                suggested_steps=[
                    "读取新发布车源基础字段。",
                    "检查是否缺少生命周期记录。",
                    "生成卖家补档清单。",
                    "补档后触发 record-and-reward。",
                ],
                source_event_ids=car_event_ids,
            ))

        if event_types.get("inquiry_sent", 0) or event_types.get("price_negotiate", 0):
            negotiation_event_ids = [
                event.id for event in events
                if event.event_type in {"inquiry_sent", "price_negotiate"}
            ]
            candidates.append(self._upsert_skill_candidate(
                review_id=review_id,
                name="transparent-negotiation-brief",
                title="透明议价摘要 Skill",
                confidence=68,
                trigger_reason="询价和议价事件需要统一沉淀为双方都能理解的沟通摘要。",
                suggested_steps=[
                    "读取车源价格、车况档案和买家预算。",
                    "生成合理价格区间和差距说明。",
                    "记录买家让步、卖家让步和未解决问题。",
                    "输出下一步沟通建议。",
                ],
                source_event_ids=negotiation_event_ids,
            ))

        return candidates

    def _upsert_skill_candidate(
        self,
        review_id: str,
        name: str,
        title: str,
        confidence: int,
        trigger_reason: str,
        suggested_steps: List[str],
        source_event_ids: List[int],
    ) -> SkillCandidate:
        existing = (
            self.db.query(SkillCandidate)
            .filter(SkillCandidate.name == name, SkillCandidate.status == "draft")
            .order_by(SkillCandidate.created_at.desc())
            .first()
        )
        if existing:
            existing.review_id = review_id
            existing.confidence = max(existing.confidence or 0, confidence)
            existing.trigger_reason = trigger_reason
            existing.suggested_steps = suggested_steps
            existing.source_event_ids = sorted(set((existing.source_event_ids or []) + source_event_ids))
            existing.updated_at = datetime.utcnow()
            self.db.add(existing)
            return existing

        candidate = SkillCandidate(
            candidate_id=f"SC-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:8].upper()}",
            review_id=review_id,
            name=name,
            title=title,
            status="draft",
            confidence=confidence,
            trigger_reason=trigger_reason,
            suggested_steps=suggested_steps,
            source_event_ids=source_event_ids,
            safety_notes=[
                "仅作为技能草稿，不自动发布。",
                "不包含支付、托管、贷款或金融推荐能力。",
                "发布前需要管理者审核。",
            ],
        )
        self.db.add(candidate)
        return candidate
