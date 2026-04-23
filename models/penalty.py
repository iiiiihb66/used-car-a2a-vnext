"""
惩罚引擎
负责处理各种违规行为的惩罚逻辑
"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from models.user import User
from models.seller_report import SellerReport
from models.point_transaction import PointTransaction


class PenaltyEngine:
    """
    惩罚引擎
    
    提供三种惩罚机制：
    1. audit_penalty: 审计自动惩罚（档案不完整）
    2. report_penalty: 用户举报惩罚
    3. complaint_penalty: 成交纠纷惩罚
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def _get_user(self, user_id: int) -> Optional[User]:
        """获取用户"""
        return self.db.query(User).filter(User.id == user_id).first()
    
    def _update_risk_level(self, user: User) -> str:
        """
        根据信誉分更新风险等级
        
        风险等级规则：
        - >= 70: normal (正常)
        - 50-69: warning (警告)
        - 30-49: danger (危险)
        - < 30: banned (封禁)
        """
        if user.reputation_score < 30:
            user.risk_level = "banned"
        elif user.reputation_score < 50:
            user.risk_level = "danger"
        elif user.reputation_score < 70:
            user.risk_level = "warning"
        else:
            user.risk_level = "normal"
        return user.risk_level
    
    def _record_transaction(
        self,
        user_id: int,
        transaction_type: str,
        points_change: int,
        balance_after: int,
        remark: str,
        related_type: str = None,
        related_id: str = None
    ) -> PointTransaction:
        """记录积分流水"""
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
    
    def audit_penalty(self, user_id: int, trust_score: float) -> Dict[str, Any]:
        """
        审计自动惩罚
        
        根据哈希链审计发现的档案完整度自动惩罚
        
        Args:
            user_id: 用户ID
            trust_score: 审计信任分（0-100）
        
        Returns:
            {
                "penalty_applied": True/False, 
                "reputation_change": -10,
                "old_reputation": 60,
                "new_reputation": 50,
                "risk_level": "warning",
                "reason": "档案不完整"
            }
        """
        user = self._get_user(user_id)
        if not user:
            return {"error": "用户不存在", "penalty_applied": False}
        
        # 信任分 >= 50 不惩罚
        if trust_score >= 50:
            return {"penalty_applied": False, "reason": "档案完整，无需惩罚"}
        
        old_score = user.reputation_score
        
        # 根据信任分确定惩罚力度
        if trust_score < 30:
            # 严重问题：信誉分 -10
            reputation_change = -10
            reason = "档案严重不完整"
        elif trust_score < 40:
            # 较大问题：信誉分 -7
            reputation_change = -7
            reason = "档案严重不完整"
        else:
            # 一般问题：信誉分 -5
            reputation_change = -5
            reason = "档案不完整"
        
        # 应用惩罚
        user.reputation_score = max(0, user.reputation_score + reputation_change)
        old_points = user.behavior_points
        user.behavior_points = max(0, user.behavior_points + reputation_change * 10)
        
        # 更新风险等级
        risk_level = self._update_risk_level(user)
        
        # 检查是否需要禁止上架
        can_list = True
        if risk_level in ["danger", "banned"]:
            can_list = False
        
        # 记录惩罚流水
        self._record_transaction(
            user_id=user_id,
            transaction_type="penalty",
            points_change=reputation_change * 10,
            balance_after=user.behavior_points,
            remark=f"惩罚：{reason}（审计信任分 {trust_score}）",
            related_type="audit"
        )
        self.db.commit()
        
        return {
            "penalty_applied": True,
            "reputation_change": reputation_change,
            "old_reputation": old_score,
            "new_reputation": user.reputation_score,
            "risk_level": risk_level,
            "can_list": can_list,
            "reason": reason
        }
    
    def report_penalty(self, seller_id: int, verified: bool) -> Dict[str, Any]:
        """
        举报惩罚
        
        用户举报核实后对卖家进行惩罚
        
        Args:
            seller_id: 被举报卖家ID
            verified: 举报是否核实
        
        Returns:
            {
                "penalty_applied": True/False,
                "reputation_change": -20,
                "old_reputation": 60,
                "new_reputation": 40,
                "risk_level": "danger",
                "banned": True,
                "banned_until": "2024-12-01T00:00:00"
            }
        """
        if not verified:
            return {"penalty_applied": False, "reason": "举报未核实"}
        
        user = self._get_user(seller_id)
        if not user:
            return {"error": "用户不存在", "penalty_applied": False}
        
        old_score = user.reputation_score
        
        # 举报核实：信誉分 -20
        user.reputation_score = max(0, user.reputation_score - 20)
        user.behavior_points = max(0, user.behavior_points - 200)
        
        # 增加警告次数
        user.warning_count = (user.warning_count or 0) + 1
        
        # 更新风险等级
        risk_level = self._update_risk_level(user)
        
        result = {
            "penalty_applied": True,
            "reputation_change": -20,
            "old_reputation": old_score,
            "new_reputation": user.reputation_score,
            "risk_level": risk_level,
            "warning_count": user.warning_count,
            "reason": "用户举报核实"
        }
        
        # 检查是否需要封禁
        if user.reputation_score < 30:
            user.risk_level = "banned"
            user.banned_until = datetime.utcnow() + timedelta(days=30)
            risk_level = "banned"
            result["banned"] = True
            result["banned_until"] = user.banned_until.isoformat()
        elif user.reputation_score < 50:
            user.risk_level = "danger"
            user.banned_until = datetime.utcnow() + timedelta(days=7)
            result["listing_blocked"] = True
            result["blocked_until"] = user.banned_until.isoformat()
        
        # 检查是否禁止上架新车
        if user.reputation_score < 50:
            result["can_list"] = False
        
        # 记录惩罚流水
        self._record_transaction(
            user_id=seller_id,
            transaction_type="penalty",
            points_change=-200,
            balance_after=user.behavior_points,
            remark="惩罚：用户举报核实",
            related_type="report"
        )
        self.db.commit()
        
        return result
    
    def complaint_penalty(self, seller_id: int, buyer_id: int, deal_id: str, complaint_type: str) -> Dict[str, Any]:
        """
        成交纠纷惩罚
        
        成交后发现问题，对卖家惩罚并补偿买家
        
        Args:
            seller_id: 卖家ID
            buyer_id: 买家ID（获得补偿）
            deal_id: 交易ID
            complaint_type: 投诉类型
        
        Returns:
            惩罚和补偿结果
        """
        seller = self._get_user(seller_id)
        buyer = self._get_user(buyer_id)
        
        if not seller or not buyer:
            return {"error": "用户不存在", "penalty_applied": False}
        
        old_seller_score = seller.reputation_score
        old_buyer_points = buyer.behavior_points
        
        # 卖家惩罚：信誉分 -30
        seller.reputation_score = max(0, seller.reputation_score - 30)
        seller.behavior_points = max(0, seller.behavior_points - 300)
        
        # 更新卖家风险等级
        seller_risk_level = self._update_risk_level(seller)
        
        # 买家补偿：积分 +50
        buyer.behavior_points = buyer.behavior_points + 50
        
        # 记录卖家惩罚流水
        self._record_transaction(
            user_id=seller_id,
            transaction_type="penalty",
            points_change=-300,
            balance_after=seller.behavior_points,
            remark=f"惩罚：{complaint_type}（交易 {deal_id}）",
            related_type="complaint",
            related_id=deal_id
        )
        
        # 记录买家补偿流水
        self._record_transaction(
            user_id=buyer_id,
            transaction_type="compensate",
            points_change=50,
            balance_after=buyer.behavior_points,
            remark=f"补偿：{complaint_type}（交易 {deal_id}）",
            related_type="complaint",
            related_id=deal_id
        )
        
        self.db.commit()
        
        return {
            "penalty_applied": True,
            "seller_result": {
                "reputation_change": -30,
                "old_reputation": old_seller_score,
                "new_reputation": seller.reputation_score,
                "risk_level": seller_risk_level
            },
            "buyer_compensation": {
                "points_change": 50,
                "old_points": old_buyer_points,
                "new_points": buyer.behavior_points
            },
            "reason": complaint_type,
            "deal_id": deal_id
        }
    
    def lift_ban(self, user_id: int, admin_id: str) -> Dict[str, Any]:
        """
        解除封禁（管理员操作）
        
        Args:
            user_id: 用户ID
            admin_id: 管理员ID
        
        Returns:
            解除结果
        """
        user = self._get_user(user_id)
        if not user:
            return {"error": "用户不存在", "success": False}
        
        old_status = user.risk_level
        user.risk_level = "warning"
        user.banned_until = None
        
        self.db.commit()
        
        return {
            "success": True,
            "old_status": old_status,
            "new_status": user.risk_level,
            "message": f"封禁已解除（管理员 {admin_id} 操作）"
        }
    
    def get_user_risk_status(self, user_id: int) -> Dict[str, Any]:
        """
        获取用户风险状态
        
        Args:
            user_id: 用户ID
        
        Returns:
            用户风险详情
        """
        user = self._get_user(user_id)
        if not user:
            return {"error": "用户不存在"}
        
        # 判断是否可以上架
        can_list = True
        if user.risk_level in ["danger", "banned"]:
            can_list = False
        if user.banned_until and user.banned_until > datetime.utcnow():
            can_list = False
        
        # 计算剩余封禁时间
        ban_remaining = None
        if user.banned_until and user.banned_until > datetime.utcnow():
            remaining = user.banned_until - datetime.utcnow()
            ban_remaining = f"{remaining.days}天{remaining.seconds // 3600}小时"
        
        return {
            "user_id": user_id,
            "reputation_score": user.reputation_score,
            "behavior_points": user.behavior_points,
            "risk_level": user.risk_level or "normal",
            "warning_count": user.warning_count or 0,
            "banned_until": user.banned_until.isoformat() if user.banned_until else None,
            "ban_remaining": ban_remaining,
            "can_list": can_list,
            "is_banned": user.risk_level == "banned" or (user.banned_until and user.banned_until > datetime.utcnow())
        }
