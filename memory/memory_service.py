"""
记忆服务
提供所有记忆层的 CRUD 操作
包括：用户、车辆、社交图谱、需求池、对话历史、生命周期记录
"""

from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from models.database import SessionLocal
from models.user import User, UserPersona
from models.car import CarMemory
from models.conversation import Conversation
from models.social_graph import SocialGraph
from models.demand import DemandPool


class MemoryService:
    """
    记忆服务
    封装所有数据库操作
    """
    
    def __init__(self, db: Session = None):
        """
        初始化记忆服务
        
        Args:
            db: 数据库会话（可选）
        """
        self.db = db or SessionLocal()
    
    def close(self):
        """关闭数据库会话"""
        if self.db:
            self.db.close()
    
    # ==================== 用户操作 ====================
    
    def create_user(
        self,
        name: str,
        email: str,
        phone: str = None,
        is_dealer: bool = False,
        buyer_persona: Dict = None,
        seller_persona: Dict = None
    ) -> Dict[str, Any]:
        """
        创建用户
        
        Args:
            name: 用户名
            email: 邮箱
            phone: 手机号
            is_dealer: 是否车商
            buyer_persona: 买家画像
            seller_persona: 卖家画像
        
        Returns:
            用户数据
        """
        # 检查邮箱是否已存在
        existing = self.db.query(User).filter(User.email == email).first()
        if existing:
            return existing.to_dict()
        
        # 创建用户
        user = User(
            name=name,
            email=email,
            phone=phone,
            is_dealer=is_dealer
        )
        self.db.add(user)
        self.db.flush()
        
        # 创建用户画像
        persona = UserPersona(
            user_id=user.id,
            buyer_persona=buyer_persona or UserPersona.create_default_buyer_persona(),
            seller_persona=seller_persona or UserPersona.create_default_seller_persona()
        )
        self.db.add(persona)
        
        # 创建社交图谱
        social_graph = SocialGraph(user_id=user.id)
        self.db.add(social_graph)
        
        self.db.commit()
        self.db.refresh(user)
        
        return user.to_dict()
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        获取用户
        
        Args:
            user_id: 用户 ID
        
        Returns:
            用户数据
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        return user.to_dict() if user else None
    
    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """
        通过邮箱获取用户
        
        Args:
            email: 邮箱
        
        Returns:
            用户数据
        """
        user = self.db.query(User).filter(User.email == email).first()
        return user.to_dict() if user else None
    
    def get_user_profile(self, user_id: int) -> Dict[str, Any]:
        """
        获取用户画像（简化版）
        
        Args:
            user_id: 用户 ID
        
        Returns:
            用户画像
        """
        user = self.get_user(user_id)
        if not user:
            return {}
        
        persona = self.get_user_persona(user_id)
        if persona:
            user["buyer_persona"] = persona.get("buyer_persona", {})
            user["seller_persona"] = persona.get("seller_persona", {})
        
        return user
    
    def get_user_persona(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        获取用户画像
        
        Args:
            user_id: 用户 ID
        
        Returns:
            用户画像
        """
        persona = self.db.query(UserPersona).filter(UserPersona.user_id == user_id).first()
        return persona.to_dict() if persona else None
    
    def update_user_persona(
        self,
        user_id: int,
        buyer_persona: Dict = None,
        seller_persona: Dict = None
    ) -> Optional[Dict[str, Any]]:
        """
        更新用户画像
        
        Args:
            user_id: 用户 ID
            buyer_persona: 买家画像
            seller_persona: 卖家画像
        
        Returns:
            更新后的用户画像
        """
        persona = self.db.query(UserPersona).filter(UserPersona.user_id == user_id).first()
        if not persona:
            return None
        
        if buyer_persona:
            persona.buyer_persona = buyer_persona
        if seller_persona:
            persona.seller_persona = seller_persona
        
        persona.updated_at = datetime.utcnow()
        self.db.commit()
        self.db.refresh(persona)
        
        return persona.to_dict()
    
    def list_users(self, is_dealer: bool = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        列出用户
        
        Args:
            is_dealer: 筛选车商
            limit: 数量限制
        
        Returns:
            用户列表
        """
        query = self.db.query(User)
        if is_dealer is not None:
            query = query.filter(User.is_dealer == is_dealer)
        
        users = query.limit(limit).all()
        return [u.to_dict() for u in users]
    
    # ==================== 车辆操作 ====================
    
    async def create_car_memory(self, car_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        创建车辆档案
        
        Args:
            car_data: 车辆数据
        
        Returns:
            车辆数据
        """
        car = CarMemory(
            car_id=car_data["car_id"],
            plate_number=car_data.get("plate_number"),
            brand=car_data["brand"],
            series=car_data.get("series", car_data["brand"]),
            model=car_data["model"],
            year=car_data["year"],
            color=car_data.get("color"),
            price=car_data["price"],
            original_price=car_data.get("original_price"),
            target_price=car_data.get("target_price"),
            mileage=car_data["mileage"],
            engine=car_data.get("engine"),
            transmission=car_data.get("transmission"),
            fuel_type=car_data.get("fuel_type"),
            configuration=car_data.get("configuration", {}),
            # 历史记录字段已移除，现在使用 CarLifecycleRecord 表
            condition_assessment=car_data.get("condition_assessment", {}),
            owner_id=car_data["owner_id"],
            region=car_data.get("region"),
            city=car_data.get("city"),
            image_descriptions=car_data.get("image_descriptions", []),
            is_listed=car_data.get("is_listed", True),
            current_status=car_data.get("current_status", "上架中"),
            listed_at=datetime.utcnow()
        )
        
        self.db.add(car)
        self.db.commit()
        self.db.refresh(car)
        
        return car.to_dict()
    
    async def get_car_memory(self, car_id: str) -> Optional[Dict[str, Any]]:
        """
        获取车辆档案
        
        Args:
            car_id: 车辆 ID
        
        Returns:
            车辆数据
        """
        car = self.db.query(CarMemory).filter(CarMemory.car_id == car_id).first()
        return car.to_dict() if car else None
    
    async def get_cars_by_owner(self, owner_id: int) -> List[Dict[str, Any]]:
        """
        获取某用户的所有车辆
        
        Args:
            owner_id: 车主 ID
        
        Returns:
            车辆列表
        """
        cars = self.db.query(CarMemory).filter(CarMemory.owner_id == owner_id).all()
        return [c.to_dict() for c in cars]
    
    async def list_listed_cars(
        self,
        brand: str = None,
        min_price: float = None,
        max_price: float = None,
        region: str = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        列出上架的车辆
        
        Args:
            brand: 品牌筛选
            min_price: 最低价格
            max_price: 最高价格
            region: 地区筛选
            limit: 数量限制
        
        Returns:
            车辆列表
        """
        query = self.db.query(CarMemory).filter(CarMemory.is_listed == True)
        
        if brand:
            query = query.filter(CarMemory.brand == brand)
        if min_price:
            query = query.filter(CarMemory.price >= min_price)
        if max_price:
            query = query.filter(CarMemory.price <= max_price)
        if region:
            query = query.filter(CarMemory.region == region)
        
        cars = query.order_by(
            CarMemory.is_boosted.desc(),
            CarMemory.listed_at.desc(),
        ).limit(limit).all()
        return [c.to_dict() for c in cars]
    
    async def update_car_status(self, car_id: str, status: str) -> Dict[str, Any]:
        """
        更新车辆状态
        
        Args:
            car_id: 车辆 ID
            status: 新状态
        
        Returns:
            更新结果
        """
        car = self.db.query(CarMemory).filter(CarMemory.car_id == car_id).first()
        if not car:
            return {"success": False, "error": "车辆不存在"}
        
        car.current_status = status
        if status == "已售出":
            car.sold_at = datetime.utcnow()
            car.is_listed = False
        car.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(car)
        
        return {
            "success": True,
            "car_id": car_id,
            "status": status
        }
    
    async def update_car_price(self, car_id: str, new_price: float) -> Dict[str, Any]:
        """
        更新车辆价格（会创建价格变更记录）
        
        Args:
            car_id: 车辆 ID
            new_price: 新价格
        
        Returns:
            更新结果
        """
        car = self.db.query(CarMemory).filter(CarMemory.car_id == car_id).first()
        if not car:
            return {"success": False, "error": "车辆不存在"}
        
        old_price = car.price
        car.price = new_price
        car.updated_at = datetime.utcnow()
        
        # 创建价格变更记录（不可篡改 + 自动发积分）
        from models.car_lifecycle_record import create_lifecycle_record
        result = create_lifecycle_record(
            db=self.db,
            car_id=car_id,
            record_type="price",
            data={
                "old_price": old_price,
                "new_price": new_price,
                "change_type": "price_update"
            },
            signed_by=str(car.owner_id),
            remark="价格更新"
        )
        # result 包含 {"record": CarLifecycleRecord, "reward": dict}
        
        self.db.commit()
        self.db.refresh(car)
        
        return {
            "success": True,
            "car_id": car_id,
            "old_price": old_price,
            "new_price": new_price,
            "record_created": True,
            "reward": result.get("reward")
        }
    
    # ==================== 生命周期记录操作 ====================
    
    async def add_lifecycle_record(
        self,
        car_id: str,
        record_type: str,
        data: dict,
        signed_by: str,
        remark: str = None
    ) -> Dict[str, Any]:
        """
        添加车辆生命周期记录（不可篡改 + 自动发积分）
        
        Args:
            car_id: 车辆ID
            record_type: 记录类型（maintenance/accident/price/ownership）
            data: 记录内容
            signed_by: 录入者
            remark: 备注
        
        Returns:
            {"record": dict, "reward": dict, "success": True}
        """
        from models.car_lifecycle_record import create_lifecycle_record
        
        # create_lifecycle_record 现在返回 {"record": CarLifecycleRecord, "reward": dict}
        result = create_lifecycle_record(
            db=self.db,
            car_id=car_id,
            record_type=record_type,
            data=data,
            signed_by=signed_by,
            remark=remark,
            auto_reward=True  # 默认自动发积分
        )
        
        return {
            "record": result["record"].to_dict(),
            "reward": result.get("reward"),
            "success": True
        }
    
    async def get_lifecycle_records(
        self,
        car_id: str,
        record_type: str = None
    ) -> List[Dict[str, Any]]:
        """
        获取车辆生命周期记录
        
        Args:
            car_id: 车辆ID
            record_type: 记录类型筛选
        
        Returns:
            记录列表
        """
        from models.car_lifecycle_record import CarLifecycleRecord
        
        query = self.db.query(CarLifecycleRecord).filter(
            CarLifecycleRecord.car_id == car_id
        )
        
        if record_type:
            query = query.filter(CarLifecycleRecord.record_type == record_type)
        
        records = query.order_by(CarLifecycleRecord.created_at.desc()).all()
        return [r.to_dict() for r in records]
    
    async def verify_car_chain(self, car_id: str) -> Dict[str, Any]:
        """
        验证车辆链式记录
        
        Args:
            car_id: 车辆ID
        
        Returns:
            验证结果
        """
        from models.car_lifecycle_record import verify_car_chain
        
        return verify_car_chain(self.db, car_id)
    
    # ==================== 促活钩子相关方法 ====================
    
    def get_user_record_count(self, user_id: int) -> int:
        """
        获取用户的档案记录数量
        
        Args:
            user_id: 用户ID
        
        Returns:
            记录数量
        """
        from models.car_lifecycle_record import CarLifecycleRecord
        
        count = self.db.query(CarLifecycleRecord).filter(
            CarLifecycleRecord.signed_by == str(user_id)
        ).count()
        
        return count
    
    def check_first_record_bonus(self, user_id: int) -> bool:
        """
        检查是否是首录奖励
        
        Args:
            user_id: 用户ID
        
        Returns:
            是否是首录（用户尚未领取过首录奖励）
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        # 如果已经领取过首录奖励，返回 False
        if user.has_first_record_bonus:
            return False
        
        # 检查用户是否有任何 CarLifecycleRecord
        from models.car_lifecycle_record import CarLifecycleRecord
        
        count = self.db.query(CarLifecycleRecord).filter(
            CarLifecycleRecord.signed_by == str(user_id)
        ).count()
        
        return count == 0
    
    def grant_first_record_bonus(self, user_id: int) -> Dict[str, Any]:
        """
        发放首录奖励
        
        Args:
            user_id: 用户ID
        
        Returns:
            奖励结果
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "用户不存在"}
        
        # 检查是否已经领取过
        if user.has_first_record_bonus:
            return {"success": False, "error": "已领取过首录奖励"}
        
        # 发放奖励
        # 1. 额外 +10 积分
        user.behavior_points = (user.behavior_points or 0) + 10
        user.reputation_score = min(100.0, user.reputation_score + 1)
        
        # 2. 发放免费估价券 1 张
        user.free_evaluation_count = (user.free_evaluation_count or 0) + 1
        
        # 3. 标记已领取
        user.has_first_record_bonus = True
        
        # 4. 更新档案记录数
        user.record_count = self.get_user_record_count(user_id)
        
        self.db.commit()
        self.db.refresh(user)
        
        return {
            "success": True,
            "is_first_record": True,
            "points_earned": 10,
            "bonus": {
                "free_evaluation": 1,
                "message": "恭喜！您获得 1 次免费估价"
            },
            "total_points": user.behavior_points,
            "total_free_evaluations": user.free_evaluation_count
        }
    
    def check_complete_profile_bonus(self, user_id: int) -> bool:
        """
        检查是否满足完整档案奖励条件（≥5条记录）
        
        Args:
            user_id: 用户ID
        
        Returns:
            是否满足条件
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        # 如果已经领取过奖励，返回 False
        if user.has_listing_boost:
            return False
        
        # 检查记录数
        record_count = self.get_user_record_count(user_id)
        
        return record_count >= 5
    
    def grant_complete_profile_bonus(self, user_id: int) -> Dict[str, Any]:
        """
        发放完整档案奖励
        
        Args:
            user_id: 用户ID
        
        Returns:
            奖励结果
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {"success": False, "error": "用户不存在"}
        
        # 检查是否已经领取过
        if user.has_listing_boost:
            return {"success": False, "error": "已领取过完整档案奖励"}
        
        record_count = self.get_user_record_count(user_id)
        
        # 检查是否满足条件
        if record_count < 5:
            return {
                "success": False,
                "error": f"档案数量不足，当前 {record_count}/5",
                "record_count": record_count
            }
        
        # 发放置顶奖励
        user.has_listing_boost = True
        
        self.db.commit()
        self.db.refresh(user)
        
        return {
            "success": True,
            "record_count": record_count,
            "completeness": "80%",
            "bonus": {
                "listing_boost": "7天",
                "message": "您的车辆将自动置顶展示"
            }
        }
    
    def activate_boost_for_car(self, car_id: str, user_id: int) -> Dict[str, Any]:
        """
        为车辆激活置顶
        
        Args:
            car_id: 车辆ID
            user_id: 用户ID
        
        Returns:
            激活结果
        """
        from datetime import timedelta
        
        user = self.db.query(User).filter(User.id == user_id).first()
        car = self.db.query(CarMemory).filter(CarMemory.car_id == car_id).first()
        
        if not user:
            return {"success": False, "error": "用户不存在"}
        
        if not car:
            return {"success": False, "error": "车辆不存在"}
        
        # 检查用户是否有置顶奖励
        if not user.has_listing_boost:
            return {"success": False, "error": "用户没有置顶奖励"}
        
        # 检查车辆是否已经置顶
        if car.is_boosted and car.boost_expiry:
            if car.boost_expiry > datetime.utcnow():
                return {
                    "success": False,
                    "error": "车辆已在置顶中",
                    "boost_expiry": car.boost_expiry.isoformat()
                }
        
        # 激活置顶（7天）
        car.is_boosted = True
        car.boost_expiry = datetime.utcnow() + timedelta(days=7)
        
        # 消耗奖励（标记为已使用）
        user.has_listing_boost = False
        
        self.db.commit()
        self.db.refresh(car)
        
        return {
            "success": True,
            "message": "置顶已激活，有效期 7 天",
            "boost_expiry": car.boost_expiry.isoformat()
        }
    
    def use_free_evaluation(self, user_id: int, car_id: str) -> Dict[str, Any]:
        """
        使用免费估价券
        
        Args:
            user_id: 用户ID
            car_id: 车辆ID
        
        Returns:
            使用结果
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return {"success": False, "error": "用户不存在"}
        
        # 检查是否有免费估价券
        if user.free_evaluation_count <= 0:
            return {"success": False, "error": "没有免费估价券"}
        
        # 消耗一张
        user.free_evaluation_count -= 1
        
        self.db.commit()
        self.db.refresh(user)
        
        return {
            "success": True,
            "remaining": user.free_evaluation_count,
            "message": "免费估价券已使用"
        }
    
    def get_loan_recall_users(self, months_before: int = 6, months_after: int = 7) -> List[Dict[str, Any]]:
        """
        获取需要贷款召回的用户
        
        Args:
            months_before: 提前多少个月开始召回
            months_after: 召回截止月份
        
        Returns:
            符合召回条件的用户列表
        """
        from datetime import timedelta
        from dateutil.relativedelta import relativedelta
        
        now = datetime.utcnow()
        
        # 计算时间范围
        start_date = now + relativedelta(months=months_before)
        end_date = now + relativedelta(months=months_after)
        
        # 查询符合条件的用户
        users = self.db.query(User).filter(
            User.loan_end_date != None,
            User.loan_end_date >= start_date,
            User.loan_end_date <= end_date
        ).all()
        
        results = []
        for user in users:
            # 计算剩余月份
            remaining = relativedelta(user.loan_end_date, now).months
            if user.loan_end_date.day < now.day:
                remaining -= 1
            
            # 检查是否已经召回过（避免重复）
            can_recall = True
            if user.last_recall_at:
                days_since_recall = (now - user.last_recall_at).days
                if days_since_recall < 30:  # 30天内不重复召回
                    can_recall = False
            
            results.append({
                "user_id": user.id,
                "user_name": user.name,
                "loan_end_date": user.loan_end_date.isoformat(),
                "remaining_months": max(0, remaining),
                "can_recall": can_recall
            })
        
        return results
    
    def record_loan_recall(self, user_id: int) -> Dict[str, Any]:
        """
        记录贷款召回
        
        Args:
            user_id: 用户ID
        
        Returns:
            记录结果
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return {"success": False, "error": "用户不存在"}
        
        user.last_recall_at = datetime.utcnow()
        user.recall_count = (user.recall_count or 0) + 1
        
        self.db.commit()
        self.db.refresh(user)
        
        return {
            "success": True,
            "recall_count": user.recall_count,
            "last_recall_at": user.last_recall_at.isoformat()
        }
    
    def set_user_loan_date(self, user_id: int, loan_end_date: datetime) -> Dict[str, Any]:
        """
        设置用户贷款结束日期
        
        Args:
            user_id: 用户ID
            loan_end_date: 贷款结束日期
        
        Returns:
            设置结果
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            return {"success": False, "error": "用户不存在"}
        
        user.loan_end_date = loan_end_date
        self.db.commit()
        self.db.refresh(user)
        
        return {
            "success": True,
            "loan_end_date": user.loan_end_date.isoformat()
        }
    
    def get_platform_stats(self) -> Dict[str, Any]:
        """
        获取平台统计数据（用于熔断判断）
        
        Returns:
            平台统计
        """
        from models.car_lifecycle_record import CarLifecycleRecord
        
        total_users = self.db.query(User).count()
        total_records = self.db.query(CarLifecycleRecord).count()
        
        # 获取活跃需求数（简化版）
        from models.demand import DemandPool
        active_demands = self.db.query(DemandPool).filter(
            DemandPool.status == "active"
        ).count()
        
        return {
            "total_users": total_users,
            "total_records": total_records,
            "active_demands": active_demands
        }
    
    # ==================== 社交图谱操作 ====================
    
    def get_social_graph(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        获取用户社交图谱
        
        Args:
            user_id: 用户 ID
        
        Returns:
            社交图谱数据
        """
        graph = self.db.query(SocialGraph).filter(SocialGraph.user_id == user_id).first()
        return graph.to_dict() if graph else None
    
    def add_collaboration(
        self,
        user_id: int,
        other_user_id: int,
        other_user_name: str = None,
        deal_price: float = None,
        car_id: str = None
    ) -> Dict[str, Any]:
        """
        添加协作记录
        
        Args:
            user_id: 用户 ID
            other_user_id: 对方用户 ID
            other_user_name: 对方用户名
            deal_price: 成交价格
            car_id: 关联车辆ID
        
        Returns:
            结果
        """
        graph = self.db.query(SocialGraph).filter(SocialGraph.user_id == user_id).first()
        if not graph:
            return {"success": False, "error": "社交图谱不存在"}
        
        graph.add_collaboration(other_user_id, other_user_name, deal_price, car_id)
        self.db.commit()
        
        return {
            "success": True,
            "message": "协作记录已添加"
        }
    
    def add_agent_skill(self, user_id: int, skill: str) -> Dict[str, Any]:
        """
        添加 Agent 技能标签
        
        Args:
            user_id: 用户 ID
            skill: 技能标签
        
        Returns:
            结果
        """
        graph = self.db.query(SocialGraph).filter(SocialGraph.user_id == user_id).first()
        if not graph:
            return {"success": False, "error": "社交图谱不存在"}
        
        graph.add_skill(skill)
        self.db.commit()
        
        return {
            "success": True,
            "message": f"技能 '{skill}' 已添加"
        }
    
    def add_car_circle_preference(
        self,
        user_id: int,
        car_type: str,
        traits: List[str]
    ) -> Dict[str, Any]:
        """
        添加车辆社交圈偏好
        
        Args:
            user_id: 用户 ID
            car_type: 车型
            traits: 偏好特征
        
        Returns:
            结果
        """
        graph = self.db.query(SocialGraph).filter(SocialGraph.user_id == user_id).first()
        if not graph:
            return {"success": False, "error": "社交图谱不存在"}
        
        graph.add_car_circle(car_type, traits)
        self.db.commit()
        
        return {
            "success": True,
            "message": "车辆圈偏好已更新"
        }
    
    # ==================== 需求池操作 ====================
    
    def create_demand(
        self,
        user_id: int,
        demand_id: str,
        car_type: str,
        budget_min: float,
        budget_max: float,
        region: str = None,
        preferences: Dict = None,
        brand_preference: str = None,
        series_preference: str = None,
        city: str = None,
        year_min: int = None,
        year_max: int = None,
        mileage_max: float = None,
        priority: int = 5,
        notes: str = None,
        notify_enabled: bool = True,
    ) -> Dict[str, Any]:
        """
        创建购车需求
        
        Args:
            user_id: 用户 ID
            demand_id: 需求 ID
            car_type: 车型
            budget_min: 最低预算
            budget_max: 最高预算
            region: 期望地区
            preferences: 其他偏好
        
        Returns:
            需求数据
        """
        demand = DemandPool(
            demand_id=demand_id,
            user_id=user_id,
            car_type=car_type,
            brand_preference=brand_preference,
            series_preference=series_preference,
            budget_min=budget_min,
            budget_max=budget_max,
            region=region,
            city=city,
            year_min=year_min,
            year_max=year_max,
            mileage_max=mileage_max,
            priority=priority,
            preferences=preferences or {},
            notes=notes,
            status="active"
        )
        demand.notify_enabled = 1 if notify_enabled else 0
        
        self.db.add(demand)
        self.db.commit()
        self.db.refresh(demand)
        
        return demand.to_dict()

    def get_demand(self, demand_id: str) -> Optional[Dict[str, Any]]:
        """
        通过 demand_id 获取单个需求
        """
        demand = self.db.query(DemandPool).filter(DemandPool.demand_id == demand_id).first()
        return demand.to_dict() if demand else None
    
    def get_demands_by_user(self, user_id: int, status: str = None) -> List[Dict[str, Any]]:
        """
        获取用户的需求列表
        
        Args:
            user_id: 用户 ID
            status: 状态筛选
        
        Returns:
            需求列表
        """
        query = self.db.query(DemandPool).filter(DemandPool.user_id == user_id)
        if status:
            query = query.filter(DemandPool.status == status)
        
        demands = query.order_by(DemandPool.created_at.desc()).all()
        return [d.to_dict() for d in demands]

    def find_demand_matches(self, demand_id: str, limit: int = 20) -> Dict[str, Any]:
        """
        查找某个需求当前可匹配的真实车源
        """
        demand = self.db.query(DemandPool).filter(DemandPool.demand_id == demand_id).first()
        if not demand:
            return {"success": False, "error": "需求不存在"}

        query = self.db.query(CarMemory).filter(
            CarMemory.is_listed == True,
            CarMemory.current_status == "上架中",
            CarMemory.price >= demand.budget_min,
            CarMemory.price <= demand.budget_max,
        )

        if demand.brand_preference:
            query = query.filter(CarMemory.brand == demand.brand_preference)
        if demand.region:
            query = query.filter(CarMemory.region == demand.region)
        if demand.city:
            query = query.filter(CarMemory.city == demand.city)
        if demand.year_min:
            query = query.filter(CarMemory.year >= demand.year_min)
        if demand.year_max:
            query = query.filter(CarMemory.year <= demand.year_max)
        if demand.mileage_max:
            query = query.filter(CarMemory.mileage <= demand.mileage_max)
        if demand.series_preference:
            query = query.filter(CarMemory.series.like(f"%{demand.series_preference}%"))

        cars = query.order_by(CarMemory.listed_at.desc()).limit(limit).all()

        matches = []
        demand_keywords = [kw for kw in [demand.car_type, demand.series_preference, demand.brand_preference] if kw]
        for car in cars:
            score = 0.6
            if demand.brand_preference and car.brand == demand.brand_preference:
                score += 0.15
            if demand.region and car.region == demand.region:
                score += 0.1
            if demand.city and car.city == demand.city:
                score += 0.05
            if demand.series_preference and demand.series_preference in (car.series or ""):
                score += 0.05
            if any(keyword in f"{car.brand} {car.series} {car.model}" for keyword in demand_keywords):
                score += 0.05

            matches.append({
                "car_id": car.car_id,
                "brand": car.brand,
                "series": car.series,
                "model": car.model,
                "year": car.year,
                "price": car.price,
                "mileage": car.mileage,
                "region": car.region,
                "city": car.city,
                "owner_id": car.owner_id,
                "match_score": round(min(score, 1.0), 2),
                "chain_verified": bool(car.chain_verified),
                "listed_at": car.listed_at.isoformat() if car.listed_at else None,
            })

        return {
            "success": True,
            "demand": demand.to_dict(),
            "total": len(matches),
            "matches": matches,
            "searched_at": datetime.utcnow().isoformat(),
        }
    
    # ==================== 对话历史操作 ====================
    
    def get_conversation_history(
        self,
        user_id: int,
        other_user_id: int = None,
        session_id: str = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        获取对话历史
        
        Args:
            user_id: 用户 ID
            other_user_id: 对方用户 ID
            session_id: 会话 ID
            limit: 数量限制
        
        Returns:
            对话历史列表
        """
        query = self.db.query(Conversation)
        
        if session_id:
            query = query.filter(Conversation.session_id == session_id)
        else:
            query = query.filter(
                (Conversation.from_user_id == user_id) |
                (Conversation.to_user_id == user_id)
            )
            if other_user_id:
                query = query.filter(
                    (Conversation.from_user_id == other_user_id) |
                    (Conversation.to_user_id == other_user_id)
                )
        
        conversations = query.order_by(Conversation.created_at.desc()).limit(limit).all()
        return [c.to_dict() for c in conversations]
    
    def add_conversation(
        self,
        from_user_id: int,
        to_user_id: int,
        intent: str,
        payload: dict,
        response: str = None
    ) -> Dict[str, Any]:
        """
        添加对话记录
        
        Args:
            from_user_id: 发送方
            to_user_id: 接收方
            intent: 意图
            payload: 消息内容
            response: 响应
        
        Returns:
            对话记录
        """
        from a2a.message import MessageBuilder
        
        message = MessageBuilder.create_message(
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            content=payload.get("content", ""),
            intent=intent
        )
        message.related_car_id = payload.get("car_id")
        
        conversation = Conversation(
            message_id=message.id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            from_agent=f"user_{from_user_id}",
            to_agent=f"user_{to_user_id}",
            intent=intent,
            payload=payload,
            content=payload.get("content"),
            related_car_id=message.related_car_id,
            session_id=message.session_id,
            status="completed"
        )
        
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        return conversation.to_dict()
    
    def get_recent_conversations(self, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """
        获取最近的对话
        
        Args:
            user_id: 用户 ID
            limit: 返回数量
        
        Returns:
            最近对话列表
        """
        return self.get_conversation_history(user_id, limit=limit)
    
    # ==================== 议价历史操作 ====================
    
    def add_negotiation_record(
        self,
        user_id: int,
        car_id: str,
        proposed_price: float,
        outcome: str = "pending"
    ) -> Dict[str, Any]:
        """
        添加议价记录
        
        Args:
            user_id: 用户ID
            car_id: 车辆ID
            proposed_price: 报价
            outcome: 结果（pending/accepted/rejected/counter_offered）
        
        Returns:
            议价记录
        """
        from models.negotiation import NegotiationHistory
        
        record = NegotiationHistory(
            user_id=user_id,
            car_id=car_id,
            proposed_price=proposed_price,
            outcome=outcome
        )
        
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        
        return record.to_dict()
    
    def get_negotiation_history(
        self,
        user_id: int,
        car_id: str = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        获取议价历史
        
        Args:
            user_id: 用户ID
            car_id: 车辆ID（可选）
            limit: 返回数量
        
        Returns:
            议价历史列表
        """
        from models.negotiation import NegotiationHistory
        
        query = self.db.query(NegotiationHistory).filter(
            NegotiationHistory.user_id == user_id
        )
        
        if car_id:
            query = query.filter(NegotiationHistory.car_id == car_id)
        
        records = query.order_by(NegotiationHistory.created_at.desc()).limit(limit).all()
        return [r.to_dict() for r in records]
    
    def get_transaction_stats(self, user_id: int) -> Dict[str, Any]:
        """
        获取交易统计
        
        Args:
            user_id: 用户ID
        
        Returns:
            交易统计
        """
        user = self.get_user(user_id)
        if not user:
            return {}
        
        from models.negotiation import NegotiationHistory
        
        # 统计成交次数
        successful_count = self.db.query(NegotiationHistory).filter(
            NegotiationHistory.user_id == user_id,
            NegotiationHistory.outcome == "accepted"
        ).count()
        
        # 统计总成交金额
        total_amount = self.db.query(NegotiationHistory).filter(
            NegotiationHistory.user_id == user_id,
            NegotiationHistory.outcome == "accepted"
        ).with_entities(
            NegotiationHistory.proposed_price
        ).all()
        
        return {
            "successful_deals": user.get("successful_deals", 0),
            "negotiation_count": successful_count,
            "reputation_score": user.get("reputation_score", 0),
            "behavior_points": user.get("behavior_points", 0)
        }


# 创建 NegotiationHistory 模型（如果不存在）
def _ensure_negotiation_model():
    """确保 NegotiationHistory 模型存在"""
    from models.database import Base
    from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey
    from datetime import datetime as dt
    
    # 检查是否已存在
    from models import negotiation
    if hasattr(negotiation, 'NegotiationHistory'):
        return
    
    # 动态创建
    class NegotiationHistory(Base):
        __tablename__ = "negotiation_history"
        
        id = Column(Integer, primary_key=True, index=True, autoincrement=True)
        user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
        car_id = Column(String(50), nullable=True, index=True)
        proposed_price = Column(Float, nullable=False)
        outcome = Column(String(20), default="pending")
        created_at = Column(DateTime, default=dt.utcnow)
        
        def to_dict(self):
            return {
                "id": self.id,
                "user_id": self.user_id,
                "car_id": self.car_id,
                "proposed_price": self.proposed_price,
                "outcome": self.outcome,
                "created_at": self.created_at.isoformat() if self.created_at else None
            }
    
    # 注入到模块
    negotiation.NegotiationHistory = NegotiationHistory


# 全局服务实例
_global_service = None

def get_memory_service(db: Session = None) -> MemoryService:
    """获取记忆服务实例"""
    global _global_service
    if _global_service is None or db is not None:
        _global_service = MemoryService(db)
    return _global_service
