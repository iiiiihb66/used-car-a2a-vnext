"""
MCP 工具实现
包含所有可用的工具函数
所有工具返回结果中包含 mock 标记，用于区分真实数据和模拟数据
"""

from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import uuid
import random
import os

from mcp.tool_registry import MCPTool, get_tool_registry


def create_evaluate_car_tool() -> MCPTool:
    """创建车辆估价工具"""
    async def handler(
        brand: str,
        model: str,
        year: int,
        mileage: float,
        condition: str = "良好",
        _context: Dict = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        车辆估价工具
        基于品牌、车型、年份、里程进行估价
        
        Returns:
            包含 mock 标记的估价结果
        """
        # 模拟估价逻辑
        base_prices = {
            "宝马": 250000,
            "奔驰": 280000,
            "奥迪": 220000,
            "丰田": 150000,
            "本田": 140000,
            "大众": 120000,
            "特斯拉": 280000,
            "蔚来": 350000,
            "比亚迪": 180000,
        }
        
        base = base_prices.get(brand, 100000)
        
        # 年份折旧
        age = datetime.now().year - year
        age_depreciation = 0.85 ** age
        
        # 里程折旧
        mileage_factor = max(0.5, 1 - (mileage - 50000) / 200000 * 0.3)
        
        # 车况调整
        condition_factor = {
            "优秀": 1.1,
            "良好": 1.0,
            "一般": 0.85,
            "较差": 0.7
        }.get(condition, 1.0)
        
        estimated_price = base * age_depreciation * mileage_factor * condition_factor
        
        return {
            "mock": True,  # TODO: 接入真实车辆估价 API
            "car_id": kwargs.get("car_id", str(uuid.uuid4())),
            "brand": brand,
            "model": model,
            "year": year,
            "mileage": mileage,
            "estimated_price": round(estimated_price, 2),
            "price_range": {
                "low": round(estimated_price * 0.9, 2),
                "high": round(estimated_price * 1.1, 2)
            },
            "market_trend": random.choice(["上涨", "稳定", "下跌"]),
            "evaluated_at": datetime.utcnow().isoformat(),
            "tips": "此价格为参考价，实际成交价需双方协商"
        }
    
    return MCPTool(
        name="evaluate_car",
        description="对二手车进行估价，基于品牌、车型、年份、里程等信息",
        parameters={
            "brand": {"type": "string", "required": True, "description": "车辆品牌"},
            "model": {"type": "string", "required": True, "description": "车辆型号"},
            "year": {"type": "integer", "required": True, "description": "车辆年份"},
            "mileage": {"type": "number", "required": True, "description": "行驶里程（公里）"},
            "condition": {"type": "string", "required": False, "default": "良好", "description": "车况"}
        },
        handler=handler,
        category="valuation"
    )


def create_escrow_create_tool() -> MCPTool:
    """创建资金托管工具"""
    async def handler(
        car_id: str,
        amount: float,
        buyer_id: int,
        seller_id: int,
        _context: Dict = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        创建资金托管
        模拟资金托管创建流程
        
        Returns:
            包含 mock 标记的托管结果
        """
        escrow_id = f"ESC-{uuid.uuid4().hex[:12].upper()}"
        
        return {
            "mock": True,  # TODO: 接入真实支付托管 API（如支付宝/微信托管）
            "escrow_id": escrow_id,
            "car_id": car_id,
            "amount": amount,
            "buyer_id": buyer_id,
            "seller_id": seller_id,
            "status": "created",
            "created_at": datetime.utcnow().isoformat(),
            "escrow_account": "平台托管账户",
            "protection_period": 7,
            "instructions": [
                "1. 买家将款项转入托管账户",
                "2. 卖家安排验车",
                "3. 验车通过后确认过户",
                "4. 款项自动转入卖家账户"
            ],
            "fee": round(amount * 0.003, 2) if amount > 0 else 0,
            "tips": "资金托管可有效保障交易安全，建议使用"
        }
    
    return MCPTool(
        name="escrow_create",
        description="创建资金托管，保障交易安全",
        parameters={
            "car_id": {"type": "string", "required": True, "description": "车辆ID"},
            "amount": {"type": "number", "required": True, "description": "托管金额"},
            "buyer_id": {"type": "integer", "required": True, "description": "买家用户ID"},
            "seller_id": {"type": "integer", "required": True, "description": "卖家用户ID"}
        },
        handler=handler,
        category="transaction"
    )


def create_match_cars_tool() -> MCPTool:
    """创建车源匹配工具（查询真实数据库）"""
    async def handler(
        brand: str = None,
        model: str = None,
        budget_min: float = 0,
        budget_max: float = 1000000,
        region: str = None,
        year_min: int = None,
        year_max: int = None,
        _context: Dict = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        车源匹配工具
        查询数据库中真实上架的车辆
        
        Returns:
            包含 mock 标记的匹配结果
        """
        from models.car import CarMemory
        from models.database import SessionLocal
        
        db = SessionLocal()
        
        try:
            # 查询真实数据
            query = db.query(CarMemory).filter(
                CarMemory.is_listed == True,
                CarMemory.current_status == "上架中"
            )
            
            # 价格筛选
            query = query.filter(
                CarMemory.price >= budget_min,
                CarMemory.price <= budget_max
            )
            
            # 品牌筛选 (支持批量匹配)
            if brand:
                brands = [b.strip() for b in brand.split(",") if b.strip()]
                if len(brands) > 1:
                    query = query.filter(CarMemory.brand.in_(brands))
                else:
                    query = query.filter(CarMemory.brand == brands[0])
            
            # 车型筛选
            if model:
                query = query.filter(CarMemory.model.like(f"%{model}%"))
            
            # 地区筛选
            if region:
                query = query.filter(CarMemory.region == region)
            
            # 年份筛选
            if year_min:
                query = query.filter(CarMemory.year >= year_min)
            if year_max:
                query = query.filter(CarMemory.year <= year_max)
            
            cars = query.order_by(CarMemory.listed_at.desc()).limit(20).all()
            
            results = []
            for car in cars:
                # 计算匹配分数
                match_score = 0.8
                if brand and car.brand == brand:
                    match_score += 0.1
                if region and car.region == region:
                    match_score += 0.05
                
                results.append({
                    "car_id": car.car_id,
                    "brand": car.brand,
                    "model": car.model,
                    "series": car.series,
                    "year": car.year,
                    "price": car.price,
                    "mileage": car.mileage,
                    "region": car.region,
                    "city": car.city,
                    "owner_id": car.owner_id,
                    "current_status": car.current_status,
                    "match_score": round(min(1.0, match_score), 2),
                    "listed_at": car.listed_at.isoformat() if car.listed_at else None
                })
            
            return {
                "mock": False,  # 真实数据库查询
                "total": len(results),
                "cars": results,
                "query_params": {
                    "brand": brand,
                    "model": model,
                    "budget_min": budget_min,
                    "budget_max": budget_max,
                    "region": region,
                    "year_min": year_min,
                    "year_max": year_max
                },
                "searched_at": datetime.utcnow().isoformat()
            }
        
        except Exception as e:
            return {
                "mock": False,
                "error": str(e),
                "total": 0,
                "cars": []
            }
        finally:
            db.close()
    
    return MCPTool(
        name="match_cars",
        description="根据用户需求匹配车源，查询真实数据库",
        parameters={
            "brand": {"type": "string", "required": False, "description": "品牌偏好"},
            "model": {"type": "string", "required": False, "description": "车型偏好"},
            "budget_min": {"type": "number", "required": False, "default": 0, "description": "最低预算"},
            "budget_max": {"type": "number", "required": False, "default": 1000000, "description": "最高预算"},
            "region": {"type": "string", "required": False, "description": "地区偏好"},
            "year_min": {"type": "integer", "required": False, "description": "最早上牌年份"},
            "year_max": {"type": "integer", "required": False, "description": "最晚上牌年份"}
        },
        handler=handler,
        category="matching"
    )


def create_submit_demand_tool() -> MCPTool:
    """创建需求提交工具"""
    async def handler(
        user_id: int,
        car_type: str,
        budget_min: float,
        budget_max: float,
        region: str = None,
        preferences: Dict = None,
        _context: Dict = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        提交购车需求
        将用户需求添加到需求池
        
        Returns:
            包含 mock 标记的需求结果
        """
        demand_id = f"DMD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
        
        return {
            "mock": True,  # TODO: 接入真实需求池系统
            "demand_id": demand_id,
            "user_id": user_id,
            "car_type": car_type,
            "budget_range": {"min": budget_min, "max": budget_max},
            "region": region,
            "preferences": preferences or {},
            "status": "active",
            "created_at": datetime.utcnow().isoformat(),
            "notification_enabled": True,
            "message": "需求已加入匹配池，有合适车源时会通知您"
        }
    
    return MCPTool(
        name="submit_demand",
        description="提交购车需求，加入匹配池等待车源匹配",
        parameters={
            "user_id": {"type": "integer", "required": True, "description": "用户ID"},
            "car_type": {"type": "string", "required": True, "description": "想要的车型"},
            "budget_min": {"type": "number", "required": True, "description": "最低预算"},
            "budget_max": {"type": "number", "required": True, "description": "最高预算"},
            "region": {"type": "string", "required": False, "description": "期望地区"},
            "preferences": {"type": "object", "required": False, "description": "其他偏好"}
        },
        handler=handler,
        category="matching"
    )


def create_verify_identity_tool() -> MCPTool:
    """创建身份验证工具"""
    async def handler(
        user_id: int,
        id_card: str = None,
        phone: str = None,
        _context: Dict = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        身份验证工具
        验证用户身份信息，返回验证状态和信任分
        
        Returns:
            包含 mock 标记的验证结果
        """
        # 模拟验证
        verified = bool(id_card or phone)
        trust_score = 0.95 if verified else 0.5
        
        return {
            "mock": True,  # TODO: 接入真实身份验证 API（如阿里云实人认证）
            "user_id": user_id,
            "verified": verified,
            "trust_score": trust_score,
            "verification_level": "中级" if verified else "基础",
            "verified_fields": ["phone"] if phone else [],
            "id_card_verified": bool(id_card),
            "verified_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(days=365)).isoformat(),
            "tips": ["完成实名认证可提升信任分"] if not id_card else []
        }
    
    return MCPTool(
        name="verify_identity",
        description="验证用户身份信息，返回验证状态和信任分",
        parameters={
            "user_id": {"type": "integer", "required": True, "description": "用户ID"},
            "id_card": {"type": "string", "required": False, "description": "身份证号"},
            "phone": {"type": "string", "required": False, "description": "手机号"}
        },
        handler=handler,
        category="identity"
    )


def create_schedule_inspection_tool() -> MCPTool:
    """创建验车预约工具"""
    async def handler(
        car_id: str,
        inspector_id: int = None,
        preferred_date: str = None,
        preferred_location: str = None,
        _context: Dict = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        安排验车
        预约专业验车师对车辆进行检测
        
        Returns:
            包含 mock 标记的预约结果
        """
        inspection_id = f"INS-{uuid.uuid4().hex[:12].upper()}"
        
        # 计算预约时间
        if preferred_date:
            scheduled_time = preferred_date
        else:
            # 默认3天后
            scheduled_time = (datetime.utcnow() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M")
        
        return {
            "mock": True,  # TODO: 接入真实验车预约系统
            "inspection_id": inspection_id,
            "car_id": car_id,
            "scheduled_time": scheduled_time,
            "location": preferred_location or "卖家所在地",
            "inspector_id": inspector_id,
            "status": "scheduled",
            "created_at": datetime.utcnow().isoformat(),
            "inspection_items": [
                "外观检测",
                "内饰检测",
                "发动机检测",
                "底盘检测",
                "电气系统检测",
                "试驾体验"
            ],
            "report_delivery": "完成后2小时内出具报告",
            "fee": 299.00,
            "fee_payer": "买家",
            "tips": "建议成交前进行专业验车，可有效避免交易风险"
        }
    
    return MCPTool(
        name="schedule_inspection",
        description="预约专业验车师对车辆进行检测",
        parameters={
            "car_id": {"type": "string", "required": True, "description": "车辆ID"},
            "inspector_id": {"type": "integer", "required": False, "description": "指定验车师ID"},
            "preferred_date": {"type": "string", "required": False, "description": "期望日期"},
            "preferred_location": {"type": "string", "required": False, "description": "期望地点"}
        },
        handler=handler,
        category="transaction"
    )


def create_transfer_ownership_tool() -> MCPTool:
    """创建过户流程工具"""
    async def handler(
        car_id: str,
        seller_id: int,
        buyer_id: int,
        transfer_type: str = "local",
        _context: Dict = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        过户流程
        返回过户流程状态和步骤
        
        Returns:
            包含 mock 标记的过户结果
        """
        transfer_id = f"TRF-{uuid.uuid4().hex[:12].upper()}"
        
        return {
            "mock": True,  # TODO: 接入真实车管所过户系统
            "transfer_id": transfer_id,
            "car_id": car_id,
            "seller_id": seller_id,
            "buyer_id": buyer_id,
            "status": "initiated",
            "transfer_type": transfer_type,
            "created_at": datetime.utcnow().isoformat(),
            "estimated_completion": (datetime.utcnow() + timedelta(days=2)).isoformat(),
            "steps": [
                {"step": 1, "name": "准备材料", "status": "pending", "description": "买卖双方准备身份证、行驶证等"},
                {"step": 2, "name": "车辆检测", "status": "pending", "description": "车管所验车"},
                {"step": 3, "name": "签署协议", "status": "pending", "description": "签署二手车交易合同"},
                {"step": 4, "name": "办理过户", "status": "pending", "description": "前往车管所办理过户"},
                {"step": 5, "name": "交付车辆", "status": "pending", "description": "交付车辆及钥匙"}
            ],
            "required_materials": [
                "买方身份证原件",
                "卖方身份证原件",
                "车辆行驶证原件",
                "车辆登记证原件",
                "二手车交易发票"
            ],
            "estimated_fee": 300,
            "tips": "不同城市流程可能有差异，请提前咨询当地车管所"
        }
    
    return MCPTool(
        name="transfer_ownership",
        description="获取过户流程和状态",
        parameters={
            "car_id": {"type": "string", "required": True, "description": "车辆ID"},
            "seller_id": {"type": "integer", "required": True, "description": "卖家ID"},
            "buyer_id": {"type": "integer", "required": True, "description": "买家ID"},
            "transfer_type": {"type": "string", "required": False, "default": "local", "description": "过户类型"}
        },
        handler=handler,
        category="transaction"
    )


def create_verify_chain_tool() -> MCPTool:
    """创建链式记录验证工具"""
    async def handler(
        car_id: str,
        _context: Dict = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        验证车辆链式记录完整性
        
        Returns:
            包含 mock 标记的验证结果
        """
        from models.car_lifecycle_record import verify_car_chain
        from models.database import SessionLocal
        
        db = SessionLocal()
        
        try:
            result = verify_car_chain(db, car_id)
            
            return {
                "mock": False,  # 真实数据库查询
                "car_id": car_id,
                "valid": result["valid"],
                "records_count": result["records"],
                "details": result.get("details", []),
                "verified_at": datetime.utcnow().isoformat(),
                "message": "链式记录验证通过" if result["valid"] else "链式记录存在异常"
            }
        except Exception as e:
            return {
                "mock": False,
                "car_id": car_id,
                "valid": False,
                "error": str(e),
                "verified_at": datetime.utcnow().isoformat()
            }
        finally:
            db.close()
    
    return MCPTool(
        name="verify_chain",
        description="验证车辆链式记录的完整性",
        parameters={
            "car_id": {"type": "string", "required": True, "description": "车辆ID"}
        },
        handler=handler,
        category="verification"
    )


# ==================== 工具导出 ====================

def init_tool_registry():
    """初始化工具注册表"""
    registry = get_tool_registry()

    app_mode = os.getenv("APP_MODE", "tool").lower()

    registry.register(create_evaluate_car_tool())
    registry.register(create_match_cars_tool())
    registry.register(create_submit_demand_tool())
    registry.register(create_verify_identity_tool())
    registry.register(create_schedule_inspection_tool())
    registry.register(create_verify_chain_tool())

    if app_mode == "full":
        registry.register(create_escrow_create_tool())
        registry.register(create_transfer_ownership_tool())
    
    print(f"✅ MCP 工具注册完成，共 {len(registry._tools)} 个工具")


# 导出所有工具创建函数
__all__ = [
    "create_evaluate_car_tool",
    "create_escrow_create_tool",
    "create_match_cars_tool",
    "create_submit_demand_tool",
    "create_verify_identity_tool",
    "create_schedule_inspection_tool",
    "create_transfer_ownership_tool",
    "create_verify_chain_tool",
    "init_tool_registry"
]
