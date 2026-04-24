"""
积分与声誉引擎
负责奖励用户行为（录入档案、成交等）和惩罚违规行为
包含积分权益功能
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session


class ReputationEngine:
    """
    积分与声誉引擎
    
    积分规则：
    - 录入保养记录: +10 积分（验证后 +20）
    - 录入事故记录: +5 积分（验证后 +10）
    - 录入价格变更: +2 积分
    - 录入过户记录: +20 积分（验证后 +40）
    - 成交奖励: +5 信誉分（大额交易额外 +3）
    
    信誉分上限: 100
    信誉分下限: 0
    
    积分权益规则：
    - 可兑换工具型权益
    - 可用于车源展示优先
    - 不提供现金、贷款或金融权益
    """
    
    # 录入档案积分规则
    RECORD_POINTS = {
        "maintenance": 10,  # 保养记录
        "accident": 5,     # 事故记录
        "price": 2,        # 价格变更
        "ownership": 20    # 过户记录
    }
    
    # 验证后积分倍数
    VERIFIED_MULTIPLIER = 2
    
    # 成交奖励
    DEAL_REPUTATION_BONUS = 5  # 基础信誉分奖励
    HIGH_VALUE_THRESHOLD = 200000  # 大额交易门槛
    HIGH_VALUE_BONUS = 3  # 大额交易额外奖励
    
    # ==================== 积分权益配置 ====================
    # 置顶规则
    BOOST_COST_PER_DAY = 30  # 每天消耗 30 积分
    BOOST_MAX_DAYS = 30      # 最多置顶 30 天
    
    def __init__(self, db: Session):
        """
        初始化声誉引擎
        
        Args:
            db: 数据库会话
        """
        self.db = db
    
    def _get_user(self, user_id: int):
        """获取用户"""
        from models.user import User
        return self.db.query(User).filter(User.id == user_id).first()
    
    def reward_for_record(
        self,
        user_id: int,
        record_type: str,
        verified: bool = False
    ) -> Dict[str, Any]:
        """
        录入档案奖励
        
        Args:
            user_id: 用户ID
            record_type: 记录类型（maintenance/accident/price/ownership）
            verified: 是否已验证
        
        Returns:
            {"points": 获得积分, "new_reputation": 新信誉分, ...}
        """
        user = self._get_user(user_id)
        if not user:
            return {"error": "用户不存在", "success": False}
        
        base_points = self.RECORD_POINTS.get(record_type, 0)
        if not base_points:
            return {"error": f"未知记录类型: {record_type}", "success": False}
        
        # 验证后翻倍
        if verified:
            base_points *= self.VERIFIED_MULTIPLIER
        
        # 更新行为积分
        user.behavior_points = (user.behavior_points or 0) + base_points
        
        # 更新信誉分（每10积分换1信誉分，上限100）
        reputation_gain = base_points / 10
        user.reputation_score = min(100.0, user.reputation_score + reputation_gain)
        
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        
        return {
            "success": True,
            "points": base_points,
            "new_reputation": round(user.reputation_score, 2),
            "total_behavior_points": user.behavior_points,
            "verified_bonus": verified,
            "record_type": record_type
        }
    
    def reward_for_deal(
        self,
        user_id: int,
        role: str,
        deal_price: float
    ) -> Dict[str, Any]:
        """
        成交奖励
        
        Args:
            user_id: 用户ID
            role: 角色（buyer/seller）
            deal_price: 成交价格
        
        Returns:
            {"bonus": 奖励说明, "new_reputation": 新信誉分, ...}
        """
        user = self._get_user(user_id)
        if not user:
            return {"error": "用户不存在", "success": False}
        
        # 更新交易统计
        user.transaction_count = (user.transaction_count or 0) + 1
        user.successful_deals = (user.successful_deals or 0) + 1
        
        # 基础信誉分 +5
        reputation_gain = self.DEAL_REPUTATION_BONUS
        bonus_descriptions = ["基础成交奖励 +5 信誉分"]
        
        # 大额交易额外加分
        if deal_price > self.HIGH_VALUE_THRESHOLD:
            reputation_gain += self.HIGH_VALUE_BONUS
            bonus_descriptions.append(f"大额交易加成 +{self.HIGH_VALUE_BONUS} 信誉分")
        
        user.reputation_score = min(100.0, user.reputation_score + reputation_gain)
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        
        return {
            "success": True,
            "role": role,
            "deal_price": deal_price,
            "reputation_gain": reputation_gain,
            "new_reputation": round(user.reputation_score, 2),
            "total_deals": user.successful_deals,
            "bonuses": bonus_descriptions
        }
    
    def reward_for_verification(self, user_id: int, verification_type: str) -> Dict[str, Any]:
        """
        完成认证奖励
        
        Args:
            user_id: 用户ID
            verification_type: 认证类型（identity/id_card/phone）
        
        Returns:
            奖励结果
        """
        user = self._get_user(user_id)
        if not user:
            return {"error": "用户不存在", "success": False}
        
        bonus_points = 0
        bonus_reputation = 0
        
        if verification_type == "identity":
            if not user.is_identity_verified:
                user.is_identity_verified = True
                bonus_points = 50
                bonus_reputation = 5
        elif verification_type == "id_card":
            if not user.id_card_verified:
                user.id_card_verified = True
                bonus_points = 100
                bonus_reputation = 10
        elif verification_type == "phone":
            bonus_points = 20
            bonus_reputation = 2
        
        if bonus_points > 0:
            user.behavior_points = (user.behavior_points or 0) + bonus_points
            user.reputation_score = min(100.0, user.reputation_score + bonus_reputation)
            user.updated_at = datetime.utcnow()
            self.db.commit()
            self.db.refresh(user)
        
        return {
            "success": True,
            "verification_type": verification_type,
            "points_earned": bonus_points,
            "reputation_earned": bonus_reputation,
            "new_reputation": round(user.reputation_score, 2),
            "total_behavior_points": user.behavior_points
        }
    
    def penalize(
        self,
        user_id: int,
        reason: str,
        points: float
    ) -> Dict[str, Any]:
        """
        惩罚（取消交易、违规等）
        
        Args:
            user_id: 用户ID
            reason: 惩罚原因
            points: 扣除信誉分
        
        Returns:
            {"reason": 原因, "penalty": 扣除分值, "new_reputation": 新信誉分}
        """
        user = self._get_user(user_id)
        if not user:
            return {"error": "用户不存在", "success": False}
        
        old_reputation = user.reputation_score
        user.reputation_score = max(0.0, user.reputation_score - points)
        user.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(user)
        
        return {
            "success": True,
            "reason": reason,
            "penalty": points,
            "old_reputation": round(old_reputation, 2),
            "new_reputation": round(user.reputation_score, 2)
        }
    
    def penalize_cancel_deal(self, user_id: int) -> Dict[str, Any]:
        """
        惩罚取消交易
        
        Args:
            user_id: 用户ID
        
        Returns:
            惩罚结果
        """
        return self.penalize(
            user_id=user_id,
            reason="取消交易",
            points=10
        )
    
    def penalize_false_info(self, user_id: int) -> Dict[str, Any]:
        """
        惩罚虚假信息
        
        Args:
            user_id: 用户ID
        
        Returns:
            惩罚结果
        """
        return self.penalize(
            user_id=user_id,
            reason="发布虚假信息",
            points=20
        )
    
    def get_user_reputation(self, user_id: int) -> Dict[str, Any]:
        """
        获取用户信誉详情
        
        Args:
            user_id: 用户ID
        
        Returns:
            信誉详情
        """
        user = self._get_user(user_id)
        if not user:
            return {"error": "用户不存在", "success": False}
        
        return {
            "success": True,
            "user_id": user_id,
            "user_name": user.name,
            "reputation_score": round(user.reputation_score, 2),
            "trust_level": user.get_trust_level(),
            "behavior_points": user.behavior_points,
            "transaction_count": user.transaction_count,
            "successful_deals": user.successful_deals,
            "is_identity_verified": user.is_identity_verified,
            "is_id_card_verified": user.id_card_verified
        }
    
    def get_leaderboard(self, limit: int = 10) -> Dict[str, Any]:
        """
        获取信誉排行榜
        
        Args:
            limit: 返回数量
        
        Returns:
            排行榜数据
        """
        from models.user import User
        
        users = self.db.query(User).order_by(
            User.reputation_score.desc()
        ).limit(limit).all()
        
        return {
            "success": True,
            "leaderboard": [
                {
                    "rank": i + 1,
                    "user_id": u.id,
                    "user_name": u.name,
                    "reputation_score": round(u.reputation_score, 2),
                    "successful_deals": u.successful_deals,
                    "is_dealer": u.is_dealer
                }
                for i, u in enumerate(users)
            ]
        }
    
    # ==================== 积分变现功能 ====================
    
    def add_points_transaction(
        self,
        user_id: int,
        transaction_type: str,
        points_change: int,
        balance_after: int,
        related_type: str = None,
        related_id: str = None,
        remark: str = None
    ):
        """
        添加积分流水记录
        
        Args:
            user_id: 用户ID
            transaction_type: 交易类型（earn/redeem/boost/gift）
            points_change: 积分变动（正数=获得，负数=消耗）
            balance_after: 变动后余额
            related_type: 关联类型
            related_id: 关联ID
            remark: 备注
        
        Returns:
            PointTransaction 对象
        """
        from models.point_transaction import PointTransaction
        
        transaction = PointTransaction(
            user_id=user_id,
            transaction_type=transaction_type,
            points_change=points_change,
            balance_after=balance_after,
            related_type=related_type,
            related_id=related_id,
            remark=remark
        )
        self.db.add(transaction)
        return transaction
    
    def earn_points(
        self,
        user_id: int,
        points: int,
        related_type: str,
        related_id: str = None,
        remark: str = None
    ) -> Dict[str, Any]:
        """
        获得积分
        
        Args:
            user_id: 用户ID
            points: 获得积分数
            related_type: 关联类型（maintenance/deal/verification等）
            related_id: 关联ID
            remark: 备注
        
        Returns:
            {"success": True/False, "points_earned": N, "new_balance": N}
        """
        user = self._get_user(user_id)
        if not user:
            return {"success": False, "error": "用户不存在"}
        
        if points <= 0:
            return {"success": False, "error": "积分必须大于0"}
        
        # 更新余额
        user.behavior_points = (user.behavior_points or 0) + points
        
        # 记录流水
        self.add_points_transaction(
            user_id=user_id,
            transaction_type="earn",
            points_change=points,
            balance_after=user.behavior_points,
            related_type=related_type,
            related_id=related_id,
            remark=remark
        )
        
        user.updated_at = datetime.utcnow()
        self.db.commit()
        
        return {
            "success": True,
            "points_earned": points,
            "new_balance": user.behavior_points,
            "remark": remark
        }
    
    def redeem_points(
        self,
        user_id: int,
        points: int,
        purpose: str,
        related_id: str = None,
        original_fee: float = None
    ) -> Dict[str, Any]:
        """
        消耗积分兑换工具权益
        
        Args:
            user_id: 用户ID
            points: 消耗积分数
            purpose: 用途（inspection/boost/other）
            related_id: 关联ID
            original_fee: 兼容旧调用，当前不做金额换算
        
        Returns:
            {"success": True/False, "points_used": N, "remaining_points": N}
        """
        user = self._get_user(user_id)
        if not user:
            return {"success": False, "error": "用户不存在"}
        
        current_balance = user.behavior_points or 0
        
        if current_balance < points:
            return {
                "success": False, 
                "error": f"积分不足，当前余额: {current_balance}，需要: {points}"
            }
        
        # 扣除积分
        user.behavior_points = current_balance - points
        
        # 记录流水
        remark = f"积分兑换{purpose}"
        self.add_points_transaction(
            user_id=user_id,
            transaction_type="redeem",
            points_change=-points,
            balance_after=user.behavior_points,
            related_type=purpose,
            related_id=related_id,
            remark=remark
        )
        
        user.updated_at = datetime.utcnow()
        self.db.commit()
        
        return {
            "success": True,
            "points_used": points,
            "remaining_points": user.behavior_points,
            "purpose": purpose
        }
    
    def boost_listing(
        self,
        user_id: int,
        car_id: str,
        days: int = 7
    ) -> Dict[str, Any]:
        """
        置顶卖车（消耗积分）
        
        Args:
            user_id: 用户ID
            car_id: 车辆ID
            days: 置顶天数
        
        Returns:
            {"success": True/False, "points_used": N, "boost_end": "日期"}
        """
        user = self._get_user(user_id)
        if not user:
            return {"success": False, "error": "用户不存在"}
        
        if days < 1:
            return {"success": False, "error": "置顶天数最少1天"}
        
        if days > self.BOOST_MAX_DAYS:
            return {"success": False, "error": f"置顶天数最多{self.BOOST_MAX_DAYS}天"}
        
        # 计算所需积分
        points_needed = days * self.BOOST_COST_PER_DAY
        current_balance = user.behavior_points or 0
        
        if current_balance < points_needed:
            return {
                "success": False,
                "error": f"积分不足，需要 {points_needed} 积分，当前余额: {current_balance}",
                "points_needed": points_needed,
                "days_can_afford": current_balance // self.BOOST_COST_PER_DAY
            }
        
        # 扣除积分
        user.behavior_points = current_balance - points_needed
        
        # 记录流水
        boost_end = datetime.utcnow().replace(hour=23, minute=59, second=59)
        boost_end = boost_end + timedelta(days=days)
        
        self.add_points_transaction(
            user_id=user_id,
            transaction_type="boost",
            points_change=-points_needed,
            balance_after=user.behavior_points,
            related_type="boost",
            related_id=car_id,
            remark=f"车辆置顶 {days} 天"
        )
        
        user.updated_at = datetime.utcnow()
        self.db.commit()
        
        return {
            "success": True,
            "points_used": points_needed,
            "boost_days": days,
            "boost_end": boost_end.strftime("%Y-%m-%d %H:%M:%S"),
            "remaining_points": user.behavior_points,
            "message": f"您的车辆将在搜索结果中优先展示 {days} 天"
        }
    
    def get_points_balance(self, user_id: int, limit: int = 20) -> Dict[str, Any]:
        """
        获取积分余额和明细
        
        Args:
            user_id: 用户ID
            limit: 返回最近记录数
        
        Returns:
            {"user_id": N, "behavior_points": N, "reputation_score": N, "trust_level": "S", "history": [...]}
        """
        from models.point_transaction import PointTransaction
        
        user = self._get_user(user_id)
        if not user:
            return {"success": False, "error": "用户不存在"}
        
        # 获取积分流水
        transactions = self.db.query(PointTransaction).filter(
            PointTransaction.user_id == user_id
        ).order_by(
            PointTransaction.created_at.desc()
        ).limit(limit).all()
        
        # 对外只暴露工具型权益，不做现金或金融价值换算。
        points_value = {
            "boost_available": user.behavior_points >= self.BOOST_COST_PER_DAY,
            "boost_cost_per_day": self.BOOST_COST_PER_DAY
        }
        
        return {
            "success": True,
            "user_id": user_id,
            "behavior_points": user.behavior_points,
            "reputation_score": round(user.reputation_score, 2),
            "trust_level": user.get_trust_level(),
            "points_value": points_value,
            "history": [t.to_dict() for t in transactions],
            "summary": {
                "total_earned": sum(t.points_change for t in transactions if t.points_change > 0),
                "total_redeemed": abs(sum(t.points_change for t in transactions if t.points_change < 0))
            }
        }
    
    def get_transaction_history(
        self,
        user_id: int,
        transaction_type: str = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        获取积分交易历史
        
        Args:
            user_id: 用户ID
            transaction_type: 筛选类型（earn/redeem/boost/gift）
            limit: 返回数量
        
        Returns:
            交易历史列表
        """
        from models.point_transaction import PointTransaction
        
        query = self.db.query(PointTransaction).filter(
            PointTransaction.user_id == user_id
        )
        
        if transaction_type:
            query = query.filter(PointTransaction.transaction_type == transaction_type)
        
        transactions = query.order_by(
            PointTransaction.created_at.desc()
        ).limit(limit).all()
        
        return {
            "success": True,
            "user_id": user_id,
            "transaction_type": transaction_type,
            "transactions": [t.to_dict() for t in transactions],
            "total": len(transactions)
        }
