"""
社交图谱模型
记录用户之间的社交关系和协作历史
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from models.database import Base


class SocialGraph(Base):
    """
    社交图谱表
    三个维度：
    1. agent_collaborations: 记录与哪些 Agent 成功交易过
    2. agent_skills: 每个 Agent 擅长的领域
    3. car_social_circle: 同款车主的群体偏好
    """
    __tablename__ = "social_graphs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # 维度1: Agent 协作历史
    # 记录与哪些 Agent 成功交易过
    agent_collaborations = Column(JSON, default=list, comment="Agent协作记录")
    # 结构: [{"agent_id": "xxx", "agent_name": "xxx", "transaction_count": 5, "last_deal": "2024-01-15", "avg_deal_price": 150000}]

    # 维度2: Agent 技能标签
    # 记录每个 Agent 擅长的领域
    agent_skills = Column(JSON, default=list, comment="Agent技能标签")
    # 结构: ["擅长谈日系车", "擅长贷款方案", "擅长验车", "价格谈判高手"]

    # 维度3: 车辆社交圈
    # 同款车主的群体偏好
    car_social_circle = Column(JSON, default=dict, comment="车辆社交圈偏好")
    # 结构: {
    #     "凯美瑞车主": {"traits": ["注重性价比", "偏好白色", "平均车龄3年"], "member_count": 50},
    #     "宝马3系车主": {"traits": ["注重驾驶体验", "偏好黑色", "平均车龄2年"], "member_count": 30}
    # }

    # 关注列表
    following = Column(JSON, default=list, comment="关注的其他用户")
    # 结构: [{"user_id": 1, "added_at": "2024-01-01"}, ...]

    # 粉丝列表
    followers = Column(JSON, default=list, comment="粉丝列表")
    # 结构: [{"user_id": 2, "added_at": "2024-01-02"}, ...]

    # 信任网络
    trusted_users = Column(JSON, default=list, comment="信任的用户")
    # 结构: [{"user_id": 3, "trust_score": 0.9}, ...]

    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关系
    user = relationship("User", back_populates="social_graph")

    def to_dict(self):
        """转换为字典"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "agent_collaborations": self.agent_collaborations,
            "agent_skills": self.agent_skills,
            "car_social_circle": self.car_social_circle,
            "following": self.following,
            "followers": self.followers,
            "trusted_users": self.trusted_users,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def add_collaboration(self, other_user_id: int, other_user_name: str = None, deal_price: float = None, car_id: str = None):
        """
        添加协作记录
        
        Args:
            other_user_id: 对方用户ID
            other_user_name: 对方用户名
            deal_price: 成交价格
            car_id: 关联车辆ID
        """
        if self.agent_collaborations is None:
            self.agent_collaborations = []
        
        # 查找是否已有记录
        existing = None
        for collab in self.agent_collaborations:
            if collab.get("user_id") == other_user_id:
                existing = collab
                break
        
        if existing:
            # 更新已有记录
            existing["transaction_count"] = existing.get("transaction_count", 0) + 1
            existing["last_deal"] = datetime.utcnow().date().isoformat()
            if deal_price:
                # 计算新的平均价
                old_total = existing.get("avg_deal_price", deal_price) * (existing["transaction_count"] - 1)
                existing["avg_deal_price"] = (old_total + deal_price) / existing["transaction_count"]
            # 添加车辆ID到交易历史
            if car_id:
                if "car_ids" not in existing:
                    existing["car_ids"] = []
                if car_id not in existing["car_ids"]:
                    existing["car_ids"].append(car_id)
        else:
            # 新增记录
            new_collab = {
                "user_id": other_user_id,
                "user_name": other_user_name,
                "transaction_count": 1,
                "last_deal": datetime.utcnow().date().isoformat(),
                "avg_deal_price": deal_price,
                "car_ids": [car_id] if car_id else []
            }
            self.agent_collaborations.append(new_collab)

    def add_skill(self, skill: str):
        """
        添加技能标签
        """
        if self.agent_skills is None:
            self.agent_skills = []
        if skill not in self.agent_skills:
            self.agent_skills.append(skill)

    def add_car_circle(self, car_type: str, traits: list):
        """
        添加车辆社交圈偏好
        """
        if self.car_social_circle is None:
            self.car_social_circle = {}
        
        if car_type in self.car_social_circle:
            # 更新已有圈子的标签
            existing_traits = set(self.car_social_circle[car_type].get("traits", []))
            existing_traits.update(traits)
            self.car_social_circle[car_type]["traits"] = list(existing_traits)
            self.car_social_circle[car_type]["member_count"] = self.car_social_circle[car_type].get("member_count", 0) + 1
        else:
            # 新增圈子
            self.car_social_circle[car_type] = {
                "traits": traits,
                "member_count": 1
            }

    def follow_user(self, user_id: int):
        """
        关注用户
        """
        if self.following is None:
            self.following = []
        
        exists = any(f.get("user_id") == user_id for f in self.following)
        if not exists:
            self.following.append({
                "user_id": user_id,
                "added_at": datetime.utcnow().date().isoformat()
            })

    def add_trusted_user(self, user_id: int, trust_score: float = 1.0):
        """
        添加信任用户
        """
        if self.trusted_users is None:
            self.trusted_users = []
        
        exists = False
        for trusted in self.trusted_users:
            if trusted.get("user_id") == user_id:
                trusted["trust_score"] = trust_score
                exists = True
                break
        
        if not exists:
            self.trusted_users.append({
                "user_id": user_id,
                "trust_score": trust_score
            })
