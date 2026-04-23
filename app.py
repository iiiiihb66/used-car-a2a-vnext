"""
二手车 A2A 档案协商工具

面向微信小程序/CloudBase 的精简后端入口。
仅保留适合工具型产品的能力：
- 用户与信誉
- 车辆档案与链式校验
- Agent 询价/议价/达成意向
- 举报与人工审核
"""

from __future__ import annotations

import os
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a2a.bus import get_a2a_bus
from memory.memory_service import get_memory_service
from mcp.tools import init_tool_registry
from models.database import SessionLocal, get_db, init_database
from models.penalty import PenaltyEngine
from models.reputation import ReputationEngine
from models.seller_report import SellerReport


APP_TITLE = "二手车 A2A 档案协商工具"
APP_VERSION = "0.1.0"
APP_DESCRIPTION = """
工具型二手车协作后端，聚焦车况档案、Agent 协商和信誉治理。

不提供支付、托管、贷款或金融服务，仅作为信息整理与协商辅助工具。
"""


def _cors_origins() -> List[str]:
    raw = os.getenv("CORS_ORIGINS", "*")
    if raw.strip() == "*":
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]


app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event() -> None:
    init_database()
    init_tool_registry()
    bus = get_a2a_bus()
    bus.set_db_session(SessionLocal())


def require_admin_token(
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
) -> None:
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        raise HTTPException(status_code=503, detail="管理员能力尚未配置")
    if x_admin_token != expected:
        raise HTTPException(status_code=401, detail="管理员令牌无效")


class UserCreate(BaseModel):
    name: str = Field(..., description="用户名称")
    email: str = Field(..., description="邮箱")
    phone: Optional[str] = Field(None, description="手机号")
    is_dealer: bool = Field(False, description="是否车商")
    buyer_persona: Optional[Dict[str, Any]] = Field(None, description="买家画像")
    seller_persona: Optional[Dict[str, Any]] = Field(None, description="卖家画像")


class CarCreate(BaseModel):
    brand: str = Field(..., description="品牌")
    model: str = Field(..., description="车型")
    year: int = Field(..., description="年份")
    price: float = Field(..., description="展示价格")
    mileage: float = Field(..., description="里程")
    color: Optional[str] = Field(None, description="颜色")
    region: Optional[str] = Field(None, description="地区")
    city: Optional[str] = Field(None, description="城市")
    transmission: Optional[str] = Field("自动", description="变速箱")
    fuel_type: Optional[str] = Field("汽油", description="燃料类型")
    series: Optional[str] = Field(None, description="车系")
    original_price: Optional[float] = Field(None, description="新车价")
    target_price: Optional[float] = Field(None, description="目标成交价")


class LifecycleRecordCreate(BaseModel):
    record_type: str = Field(..., description="maintenance/accident/price/ownership")
    data: Dict[str, Any] = Field(..., description="记录内容")
    remark: Optional[str] = Field(None, description="备注")


class InquiryRequest(BaseModel):
    buyer_id: int = Field(..., description="买家用户ID")
    seller_id: int = Field(..., description="卖家用户ID")
    car_id: str = Field(..., description="车辆ID")
    message: Optional[str] = Field(None, description="询价内容")


class NegotiateRequest(BaseModel):
    buyer_id: int = Field(..., description="买家用户ID")
    seller_id: int = Field(..., description="卖家用户ID")
    car_id: str = Field(..., description="车辆ID")
    proposed_price: float = Field(..., description="报价")
    reason: Optional[str] = Field(None, description="说明")


class DealIntentRequest(BaseModel):
    buyer_id: int = Field(..., description="买家用户ID")
    seller_id: int = Field(..., description="卖家用户ID")
    car_id: str = Field(..., description="车辆ID")
    agreed_price: float = Field(..., description="双方协商价格")


class SellerReportCreate(BaseModel):
    reporter_id: int = Field(..., description="举报者")
    seller_id: int = Field(..., description="被举报卖家")
    car_id: Optional[str] = Field(None, description="关联车辆ID")
    reason: str = Field(..., description="举报原因")
    evidence: Optional[str] = Field(None, description="证据描述或文件 URL")


class ReviewReportRequest(BaseModel):
    report_id: int = Field(..., description="举报ID")
    approved: bool = Field(..., description="是否通过")
    admin_id: str = Field(..., description="管理员ID")
    remark: Optional[str] = Field(None, description="审核备注")


class DemandCreate(BaseModel):
    user_id: int = Field(..., description="需求发布用户ID")
    car_type: str = Field(..., description="目标车型类别")
    budget_min: float = Field(..., description="最低预算")
    budget_max: float = Field(..., description="最高预算")
    brand_preference: Optional[str] = Field(None, description="品牌偏好")
    series_preference: Optional[str] = Field(None, description="车系偏好")
    region: Optional[str] = Field(None, description="地区偏好")
    city: Optional[str] = Field(None, description="城市偏好")
    year_min: Optional[int] = Field(None, description="最早接受年份")
    year_max: Optional[int] = Field(None, description="最晚接受年份")
    mileage_max: Optional[float] = Field(None, description="可接受最大里程")
    priority: int = Field(5, ge=1, le=10, description="需求优先级")
    preferences: Optional[Dict[str, Any]] = Field(None, description="额外偏好")
    notes: Optional[str] = Field(None, description="备注")
    notify_enabled: bool = Field(True, description="是否开启提醒")


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "name": APP_TITLE,
        "version": APP_VERSION,
        "mode": "tool",
        "docs": "/docs",
        "message": "服务在线。当前版本仅提供档案协商与信誉治理能力。",
    }


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "healthy",
        "service": APP_TITLE,
        "version": APP_VERSION,
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/api/v1/users")
async def create_user(user_data: UserCreate, db=Depends(get_db)) -> Dict[str, Any]:
    memory = get_memory_service(db)
    user = memory.create_user(
        name=user_data.name,
        email=user_data.email,
        phone=user_data.phone,
        is_dealer=user_data.is_dealer,
        buyer_persona=user_data.buyer_persona,
        seller_persona=user_data.seller_persona,
    )
    return {"success": True, "data": user}


@app.get("/api/v1/users")
async def list_users(
    is_dealer: Optional[bool] = Query(None),
    db=Depends(get_db),
) -> Dict[str, Any]:
    memory = get_memory_service(db)
    users = memory.list_users(is_dealer=is_dealer)
    return {"success": True, "total": len(users), "data": users}


@app.get("/api/v1/users/{user_id}")
async def get_user(user_id: int, db=Depends(get_db)) -> Dict[str, Any]:
    memory = get_memory_service(db)
    user = memory.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"success": True, "data": user}


@app.get("/api/v1/users/{user_id}/reputation")
async def get_user_reputation(user_id: int, db=Depends(get_db)) -> Dict[str, Any]:
    engine = ReputationEngine(db)
    result = engine.get_user_reputation(user_id)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "用户不存在"))
    return result


@app.get("/api/v1/reputation/leaderboard")
async def get_reputation_leaderboard(
    limit: int = Query(10, ge=1, le=100),
    db=Depends(get_db),
) -> Dict[str, Any]:
    engine = ReputationEngine(db)
    return engine.get_leaderboard(limit=limit)


@app.post("/api/v1/demands")
async def create_demand(request: DemandCreate, db=Depends(get_db)) -> Dict[str, Any]:
    memory = get_memory_service(db)
    user = memory.get_user(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")

    demand = memory.create_demand(
        user_id=request.user_id,
        demand_id=f"DMD-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}",
        car_type=request.car_type,
        budget_min=request.budget_min,
        budget_max=request.budget_max,
        brand_preference=request.brand_preference,
        series_preference=request.series_preference,
        region=request.region,
        city=request.city,
        year_min=request.year_min,
        year_max=request.year_max,
        mileage_max=request.mileage_max,
        priority=request.priority,
        preferences=request.preferences,
        notes=request.notes,
        notify_enabled=request.notify_enabled,
    )
    return {"success": True, "message": "需求已进入意向大厅", "data": demand}


@app.get("/api/v1/users/{user_id}/demands")
async def get_user_demands(
    user_id: int,
    status: Optional[str] = Query(None),
    db=Depends(get_db),
) -> Dict[str, Any]:
    memory = get_memory_service(db)
    demands = memory.get_demands_by_user(user_id=user_id, status=status)
    return {"success": True, "total": len(demands), "data": demands}


@app.get("/api/v1/demands/{demand_id}")
async def get_demand(demand_id: str, db=Depends(get_db)) -> Dict[str, Any]:
    memory = get_memory_service(db)
    demand = memory.get_demand(demand_id)
    if not demand:
        raise HTTPException(status_code=404, detail="需求不存在")
    return {"success": True, "data": demand}


@app.get("/api/v1/demands/{demand_id}/matches")
async def get_demand_matches(
    demand_id: str,
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
) -> Dict[str, Any]:
    memory = get_memory_service(db)
    result = memory.find_demand_matches(demand_id=demand_id, limit=limit)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "需求不存在"))
    return result


@app.post("/api/v1/cars")
async def create_car(
    car_data: CarCreate,
    user_id: int = Query(..., description="车主用户ID"),
    db=Depends(get_db),
) -> Dict[str, Any]:
    memory = get_memory_service(db)
    user = memory.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="车主不存在")

    payload = {
        "car_id": f"CAR-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}",
        "brand": car_data.brand,
        "series": car_data.series or car_data.brand,
        "model": car_data.model,
        "year": car_data.year,
        "price": car_data.price,
        "original_price": car_data.original_price,
        "target_price": car_data.target_price or car_data.price,
        "mileage": car_data.mileage,
        "color": car_data.color,
        "region": car_data.region,
        "city": car_data.city,
        "transmission": car_data.transmission,
        "fuel_type": car_data.fuel_type,
        "owner_id": user_id,
        "is_listed": True,
        "current_status": "上架中",
    }
    car = await memory.create_car_memory(payload)
    return {"success": True, "data": car}


@app.get("/api/v1/cars")
async def list_cars(
    brand: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None),
    max_price: Optional[float] = Query(None),
    region: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    db=Depends(get_db),
) -> Dict[str, Any]:
    memory = get_memory_service(db)
    cars = await memory.list_listed_cars(
        brand=brand,
        min_price=min_price,
        max_price=max_price,
        region=region,
        limit=limit,
    )
    return {"success": True, "total": len(cars), "data": cars}


@app.get("/api/v1/cars/{car_id}")
async def get_car(car_id: str, db=Depends(get_db)) -> Dict[str, Any]:
    memory = get_memory_service(db)
    car = await memory.get_car_memory(car_id)
    if not car:
        raise HTTPException(status_code=404, detail="车辆不存在")
    return {"success": True, "data": car}


@app.get("/api/v1/users/{user_id}/cars")
async def get_user_cars(user_id: int, db=Depends(get_db)) -> Dict[str, Any]:
    memory = get_memory_service(db)
    cars = await memory.get_cars_by_owner(user_id)
    return {"success": True, "total": len(cars), "data": cars}


@app.post("/api/v1/cars/{car_id}/records")
async def add_car_record(
    car_id: str,
    request: LifecycleRecordCreate,
    user_id: int = Query(..., description="录入者用户ID"),
    db=Depends(get_db),
) -> Dict[str, Any]:
    memory = get_memory_service(db)
    car = await memory.get_car_memory(car_id)
    if not car:
        raise HTTPException(status_code=404, detail="车辆不存在")

    result = await memory.add_lifecycle_record(
        car_id=car_id,
        record_type=request.record_type,
        data=request.data,
        signed_by=str(user_id),
        remark=request.remark,
    )
    return {"success": True, "data": result}


@app.get("/api/v1/cars/{car_id}/records")
async def get_car_records(
    car_id: str,
    record_type: Optional[str] = Query(None),
    db=Depends(get_db),
) -> Dict[str, Any]:
    memory = get_memory_service(db)
    records = await memory.get_lifecycle_records(car_id, record_type=record_type)
    return {"success": True, "total": len(records), "data": records}


@app.get("/api/v1/cars/{car_id}/verify")
async def verify_car_chain(car_id: str, db=Depends(get_db)) -> Dict[str, Any]:
    memory = get_memory_service(db)
    result = await memory.verify_car_chain(car_id)
    return {"success": True, "data": result}


@app.post("/api/v1/agent/inquiry")
async def send_inquiry(request: InquiryRequest, db=Depends(get_db)) -> Dict[str, Any]:
    bus = get_a2a_bus()
    bus.set_db_session(db)
    result = await bus.send_price_inquiry(
        from_user_id=request.buyer_id,
        to_user_id=request.seller_id,
        car_id=request.car_id,
        message=request.message,
    )
    return {"success": True, "data": result}


@app.post("/api/v1/agent/negotiate")
async def send_negotiate(request: NegotiateRequest, db=Depends(get_db)) -> Dict[str, Any]:
    memory = get_memory_service(db)
    car = await memory.get_car_memory(request.car_id)
    if not car:
        raise HTTPException(status_code=404, detail="车辆不存在")

    bus = get_a2a_bus()
    bus.set_db_session(db)
    result = await bus.send_price_negotiate(
        from_user_id=request.buyer_id,
        to_user_id=request.seller_id,
        car_id=request.car_id,
        current_price=car.get("price", 0),
        proposed_price=request.proposed_price,
        reason=request.reason,
    )
    return {"success": True, "data": result}


@app.post("/api/v1/agent/deal-intent")
async def send_deal_intent(
    request: DealIntentRequest,
    db=Depends(get_db),
) -> Dict[str, Any]:
    bus = get_a2a_bus()
    bus.set_db_session(db)
    result = await bus.send_deal_intent(
        from_user_id=request.buyer_id,
        to_user_id=request.seller_id,
        car_id=request.car_id,
        agreed_price=request.agreed_price,
    )
    return {"success": True, "data": result}


@app.get("/api/v1/conversations/{user_id}")
async def get_conversations(
    user_id: int,
    other_user_id: Optional[int] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
) -> Dict[str, Any]:
    bus = get_a2a_bus()
    bus.set_db_session(db)
    history = await bus.get_conversation_history(
        user_id=user_id,
        other_user_id=other_user_id,
        limit=limit,
    )
    return {"success": True, "total": len(history), "data": history}


@app.post("/api/v1/reports/seller")
async def report_seller(
    request: SellerReportCreate,
    db=Depends(get_db),
) -> Dict[str, Any]:
    report = SellerReport(
        reporter_id=request.reporter_id,
        seller_id=request.seller_id,
        car_id=request.car_id,
        reason=request.reason,
        evidence=request.evidence,
        status="pending",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return {
        "success": True,
        "message": "举报已提交，等待人工审核",
        "data": report.to_dict(),
    }


@app.get("/api/v1/admin/reports")
async def list_reports(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    _: None = Depends(require_admin_token),
) -> Dict[str, Any]:
    query = db.query(SellerReport)
    if status:
        query = query.filter(SellerReport.status == status)
    reports = query.order_by(SellerReport.created_at.desc()).limit(limit).all()
    return {"success": True, "total": len(reports), "data": [r.to_dict() for r in reports]}


@app.post("/api/v1/admin/reports/review")
async def review_report(
    request: ReviewReportRequest,
    db=Depends(get_db),
    _: None = Depends(require_admin_token),
) -> Dict[str, Any]:
    report = db.query(SellerReport).filter(SellerReport.id == request.report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="举报不存在")
    if report.status != "pending":
        raise HTTPException(status_code=400, detail="举报已处理")

    report.status = "approved" if request.approved else "rejected"
    report.reviewed_by = request.admin_id
    report.reviewed_at = datetime.utcnow()
    report.review_remark = request.remark

    penalty_result: Dict[str, Any] = {"penalty_applied": False}
    if request.approved:
        report.penalty_applied = True
        engine = PenaltyEngine(db)
        penalty_result = engine.report_penalty(seller_id=report.seller_id, verified=True)

    db.commit()
    db.refresh(report)

    return {
        "success": True,
        "message": "审核完成",
        "data": report.to_dict(),
        "penalty_result": penalty_result,
    }
