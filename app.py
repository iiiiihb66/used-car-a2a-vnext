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
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from tempfile import mkdtemp
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.background import BackgroundTask

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from a2a.bus import get_a2a_bus
from a2a.message import MessageBuilder
from memory.growth_engine import GrowthEngine
from memory.memory_service import get_memory_service
from mcp.tools import init_tool_registry
from models.database import DATABASE_URL, SessionLocal, engine, get_db, init_database
from models.agent_event import AgentEvent
from models.car import CarMemory
from models.car_lifecycle_record import CarLifecycleRecord
from models.conversation import Conversation
from models.demand import DemandPool
from models.growth import GrowthReview, SkillCandidate
from models.penalty import PenaltyEngine
from models.point_transaction import PointTransaction
from models.reputation import ReputationEngine
from models.seller_report import SellerReport
from models.user import User
from utils.price_tools import PriceEvaluator, ConditionTemplate


APP_TITLE = "二手车 A2A 档案协商工具"
APP_VERSION = "0.1.0"
PLATFORM_ADMIN_ID = 0 # 平台系统用户 ID
PUBLIC_BASE_URL = os.getenv(
    "PUBLIC_BASE_URL",
    "https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com",
)
APP_DESCRIPTION = """
工具型二手车协作后端，聚焦车况档案、Agent 协商和信誉治理。

不提供支付、托管、贷款或金融服务，仅作为信息整理与协商辅助工具。
"""
GROWTH_REVIEW_INTERVAL = int(os.getenv("GROWTH_REVIEW_INTERVAL", "10"))


def _cors_origins() -> List[str]:
    raw = os.getenv("CORS_ORIGINS", "*")
    if raw.strip() == "*":
        return ["*"]
    return [item.strip() for item in raw.split(",") if item.strip()]


app = FastAPI(
    title=APP_TITLE,
    description=APP_DESCRIPTION,
    version=APP_VERSION,
    servers=[{"url": PUBLIC_BASE_URL}],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_utf8_charset(request: Request, call_next):
    """
    强制所有 JSON 响应使用 UTF-8 编码，防止中文乱码。
    """
    response = await call_next(request)
    content_type = response.headers.get("Content-Type", "")
    if "application/json" in content_type and "charset" not in content_type:
        response.headers["Content-Type"] = f"{content_type}; charset=utf-8"
    return response


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


def _sqlite_database_path() -> Path:
    prefix = "sqlite:///"
    if not DATABASE_URL.startswith(prefix):
        raise HTTPException(status_code=400, detail="当前数据库不是 SQLite")
    return Path(DATABASE_URL[len(prefix):]).expanduser().resolve()


def _create_sqlite_backup(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(source) as src_conn, sqlite3.connect(target) as dst_conn:
        src_conn.backup(dst_conn)


def _assert_valid_sqlite(path: Path) -> None:
    try:
        with sqlite3.connect(path) as conn:
            result = conn.execute("PRAGMA integrity_check").fetchone()
    except sqlite3.DatabaseError as exc:
        raise HTTPException(status_code=400, detail=f"SQLite 文件无效: {exc}") from exc

    if not result or result[0] != "ok":
        detail = result[0] if result else "unknown"
        raise HTTPException(status_code=400, detail=f"SQLite 完整性检查失败: {detail}")


def public_growth_review_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """公开事件写入接口只返回复盘触发状态，完整内容仅管理员可见。"""
    public_result = {
        "success": result.get("success", False),
        "triggered": result.get("triggered", False),
    }
    if not result.get("triggered"):
        public_result["reason"] = result.get("reason")
        public_result["pending_events"] = result.get("pending_events")
        public_result["interval"] = result.get("interval")
        return public_result

    review = result.get("review") or {}
    public_result["review_id"] = review.get("review_id")
    public_result["events_count"] = review.get("events_count")
    public_result["skill_candidates_count"] = len(result.get("skill_candidates") or [])
    return public_result


def _agent_response_content(result: Dict[str, Any]) -> str:
    response = (result or {}).get("agent_response") or {}
    content = response.get("content")
    if content:
        return str(content)
    error = response.get("error")
    if error:
        return f"[Agent error] {error}"
    return ""


def _record_agent_event(
    db,
    *,
    actor_agent: str,
    actor_role: str,
    event_type: str,
    status: str,
    user_id: Optional[int] = None,
    related_user_id: Optional[int] = None,
    related_car_id: Optional[str] = None,
    related_conversation_id: Optional[str] = None,
    input_snapshot: Optional[Dict[str, Any]] = None,
    output_snapshot: Optional[Dict[str, Any]] = None,
    observation: Optional[str] = None,
    score: Optional[float] = None,
) -> Dict[str, Any]:
    event = AgentEvent(
        actor_agent=actor_agent,
        actor_role=actor_role,
        event_type=event_type,
        status=status,
        user_id=user_id,
        related_user_id=related_user_id,
        related_car_id=related_car_id,
        related_conversation_id=related_conversation_id,
        input_snapshot=input_snapshot or {},
        output_snapshot=output_snapshot or {},
        observation=observation,
        score=score,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event.to_dict()


def _get_agent_session_config(db, session_id: str) -> Dict[str, Any]:
    event = (
        db.query(AgentEvent)
        .filter(
            AgentEvent.event_type == "auto_session_created",
            AgentEvent.related_conversation_id == session_id,
        )
        .order_by(AgentEvent.id.desc())
        .first()
    )
    if not event:
        raise HTTPException(status_code=404, detail="自动协商会话不存在")
    return event.input_snapshot or {}
def _calculate_offer_price(car: CarMemory, config: Dict[str, Any], round_index: int) -> float:
    # 使用价格评估工具进行动态出价逻辑
    market_ref = PriceEvaluator.get_market_reference(
        car.brand, car.model, car.year, car.mileage
    )
    market_avg = market_ref["market_avg"]
    display_price = float(car.price or 0)
    
    # 锚点优化：不再简单取小值，而是取挂牌价和评估价的加权平均，避免买家出价过低
    # 如果挂牌价远高于评估价，买家会倾向于评估价；如果挂牌价接近评估价，买家会参考挂牌价。
    anchor_price = (display_price * 0.4) + (market_avg * 0.6)
    
    # 溢价系数：挂牌价相对于市场均价的溢价程度
    premium_ratio = display_price / market_avg if market_avg > 0 else 1.0
    
    # 初始折扣
    if premium_ratio > 1.2:
        initial_discount = 0.85 # 溢价太高，砍价狠
    elif premium_ratio < 0.95:
        initial_discount = 0.98 # 挂牌价已低，诚意还价
    else:
        initial_discount = 0.92 # 正常议价

    target_price = config.get("buyer_target_price")
    budget_max = config.get("buyer_budget_max")

    if target_price:
        # 如果用户明确了目标价，以目标价为基准
        base_offer = float(target_price)
    else:
        base_offer = anchor_price * initial_discount
        if budget_max:
            base_offer = min(base_offer, float(budget_max))

    # 动态步长 (每轮步长递减，表现出博弈诚意)
    step_factor = 0.015 if display_price > market_avg else 0.01
    
    if round_index <= 1:
        offer = base_offer
    else:
        # 非线性累加：round 2 +1.5%, round 3 +0.75%, round 4 +0.37%...
        total_increment = 0
        for i in range(1, round_index):
            total_increment += display_price * step_factor * (0.5 ** (i - 1))
        offer = base_offer + total_increment
    
    if budget_max:
        offer = min(offer, float(budget_max))
    
    # 最后兜底：出价不能低于挂牌价的 50%（除非挂牌价本身极高），防止 2.88 这种离谱报价
    floor_limit = display_price * 0.5
    final_offer = max(offer, floor_limit)
    
    return round(min(final_offer, display_price), 2)


def _is_deal_ready(car: CarMemory, proposed_price: float, seller_content: str) -> bool:
    target_price = float(car.target_price or car.price or 0)
    # 底价保护：agreed_price 不得低于 car.target_price
    # 价格达成一致：出价达到或超过目标价
    accepted_by_price = bool(target_price and proposed_price >= target_price)
    
    # 语义判断：卖家表达了接受意向
    accepted_by_text = any(
        keyword in seller_content
        for keyword in ["可以接受", "同意成交", "接受这个价格", "价格可以", "成交！", "没问题", "确定可以"]
    )
    # 排除“促成交易”、“成交价”等模糊词义
    if "促成交易" in seller_content and not accepted_by_price:
        if not any(k in seller_content for k in ["可以接受", "成交！"]):
             accepted_by_text = False
             
    # 只有当出价达到底价且卖家语义同意时，才判定为 deal_ready
    return accepted_by_price and accepted_by_text


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
    owner_id: Optional[int] = Field(None, description="车主用户ID（传此字段则忽略 Query 中的 user_id）")
    report_url: Optional[str] = Field(None, description="检测报告链接")
    image_urls: Optional[List[str]] = Field(None, description="图片链接列表")
    attachments: Optional[Dict[str, Any]] = Field(None, description="其他附件信息")


class AgentEventCreate(BaseModel):
    actor_agent: str = Field(..., description="Agent 名称，如 Qclaw/WorkBuddy/platform-scheduler")
    actor_role: str = Field(..., description="buyer/seller/platform/admin")
    event_type: str = Field(..., description="事件类型，如 match_empty/car_published/inquiry_sent")
    status: str = Field("observed", description="observed/succeeded/failed/pending")
    user_id: Optional[int] = Field(None, description="关联用户")
    related_user_id: Optional[int] = Field(None, description="关联对方用户")
    related_car_id: Optional[str] = Field(None, description="关联车辆")
    related_demand_id: Optional[str] = Field(None, description="关联需求")
    related_conversation_id: Optional[str] = Field(None, description="关联会话")
    input_snapshot: Optional[Dict[str, Any]] = Field(None, description="触发条件")
    output_snapshot: Optional[Dict[str, Any]] = Field(None, description="响应内容")
    score: Optional[float] = Field(None, description="评分/置信度")
    observation: Optional[str] = Field(None, description="观察详情")


class MatchStatusUpdate(BaseModel):
    status: str = Field(..., description="new/interested/rejected/negotiating/deal_ready/failed")


class MatchSessionRequest(BaseModel):
    buyer_agent_name: str = Field("Qclaw-buyer", description="买家 Agent 名称")
    seller_agent_name: str = Field("WorkBuddy-seller", description="卖家 Agent 名称")
    max_rounds: int = Field(5, description="最大协商轮数")


class MatchCreate(BaseModel):
    demand_id: str = Field(..., description="需求 ID")
    car_id: str = Field(..., description="车辆 ID")
    match_score: float = Field(..., description="匹配分")
    match_reason: Optional[str] = Field(None, description="匹配原因")


class LifecycleRecordCreate(BaseModel):
    record_type: str = Field(..., description="maintenance/accident/price/ownership")
    data: Dict[str, Any] = Field(..., description="记录内容")
    remark: Optional[str] = Field(None, description="备注")


class RecordAndRewardRequest(LifecycleRecordCreate):
    user_id: int = Field(..., description="录入者用户ID")


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


class AgentEventCreate(BaseModel):
    actor_agent: str = Field(..., description="Agent 名称，如 Qclaw/WorkBuddy/platform-scheduler")
    actor_role: str = Field(..., description="buyer/seller/platform/admin")
    event_type: str = Field(..., description="事件类型，如 match_empty/car_published/inquiry_sent")
    status: str = Field("observed", description="observed/succeeded/failed/pending")
    user_id: Optional[int] = Field(None, description="关联用户")
    related_user_id: Optional[int] = Field(None, description="关联对方用户")
    related_car_id: Optional[str] = Field(None, description="关联车辆")
    related_demand_id: Optional[str] = Field(None, description="关联需求")
    related_conversation_id: Optional[str] = Field(None, description="关联会话")
    input_snapshot: Optional[Dict[str, Any]] = Field(None, description="触发条件")
    output_snapshot: Optional[Dict[str, Any]] = Field(None, description="执行结果")
    observation: Optional[str] = Field(None, description="自然语言观察")
    score: Optional[float] = Field(None, description="可选评分")


class GrowthReviewRunRequest(BaseModel):
    after_event_id: Optional[int] = Field(None, description="从某个事件 ID 之后开始复盘；为空则接上次复盘")
    limit: int = Field(30, ge=1, le=200, description="本次最多复盘事件数")
    min_events: int = Field(1, ge=1, le=200, description="最少事件数，不足则跳过")


class AgentSessionCreate(BaseModel):
    buyer_id: int = Field(..., description="买家用户ID")
    seller_id: int = Field(..., description="卖家用户ID")
    car_id: str = Field(..., description="车辆ID")
    buyer_goal: str = Field(
        "家用 SUV，车况透明，价格合理，优先混动/新能源",
        description="买家目标",
    )
    initial_message: Optional[str] = Field(None, description="第一轮询价内容")
    buyer_budget_min: Optional[float] = Field(None, description="买家最低预算，单位万元")
    buyer_budget_max: Optional[float] = Field(None, description="买家最高预算，单位万元")
    buyer_target_price: Optional[float] = Field(None, description="买家目标报价，单位万元")
    max_rounds: int = Field(3, ge=1, le=6, description="自动协商最大回合数")
    auto_deal: bool = Field(False, description="达到条件时是否自动生成成交意向")
    buyer_agent_name: str = Field("buyer-agent", description="买家 Agent 名称，可填任意接入方名称")
    seller_agent_name: str = Field("seller-agent", description="卖家 Agent 名称，可填任意接入方名称")


class AgentSessionRunRequest(BaseModel):
    max_rounds: Optional[int] = Field(None, ge=1, le=6, description="覆盖最大回合数")
    auto_deal: Optional[bool] = Field(None, description="覆盖自动成交意向开关")
    buyer_target_price: Optional[float] = Field(None, description="覆盖买家目标报价，单位万元")


@app.get("/")
async def root() -> Dict[str, Any]:
    return {
        "name": APP_TITLE,
        "version": APP_VERSION,
        "mode": "tool",
        "docs": "/docs",
        "base_url": PUBLIC_BASE_URL,
        "openapi": f"{PUBLIC_BASE_URL}/openapi.json",
        "skill": f"{PUBLIC_BASE_URL}/skill.md",
        "growth_engine": "Hermes-lite",
        "message": "服务在线。当前版本提供档案协商、信誉治理和 Agent 成长复盘能力。",
    }


@app.get("/skill.md", response_class=PlainTextResponse)
async def skill_markdown() -> str:
    return f"""# 二手车 Agent 意向大厅 Skill

这是一个面向 Qclaw / OpenClaw / 通用 Agent 的二手车意向撮合工具。

## 服务入口

- Base URL: `{PUBLIC_BASE_URL}`
- OpenAPI: `{PUBLIC_BASE_URL}/openapi.json`
- 健康检查: `{PUBLIC_BASE_URL}/health`

## 业务定位

- 工具型二手车协作后端
- 帮用户发布买车需求、录入车辆档案、查询匹配结果
- 帮 Agent 执行询价、议价、达成见面/沟通意向
- 帮平台自动驱动买家 Agent 与卖家 Agent 多轮协商
- 记录任意外部 Agent 的执行轨迹，并沉淀为复盘和技能候选
- 不提供支付、托管、贷款、金融推荐

## Agent 使用方式

1. 读取 `{PUBLIC_BASE_URL}/openapi.json`
2. 使用 `{PUBLIC_BASE_URL}` 作为 API base URL
3. 先调用 `POST /api/v1/users` 创建买家或车商用户
4. 车商调用 `POST /api/v1/cars?user_id={{seller_id}}` 发布车源
5. 买家调用 `POST /api/v1/demands` 发布买车需求
6. 调用 `GET /api/v1/demands/{{demand_id}}/matches` 查看匹配车源
7. 需要单步协商时调用 `/api/v1/agent/inquiry`、`/api/v1/agent/negotiate`、`/api/v1/agent/deal-intent`
8. 需要自动协商时调用 `POST /api/v1/agent/sessions` 创建会话，再调用 `POST /api/v1/agent/sessions/{{session_id}}/run`
9. 调用 `GET /api/v1/agent/sessions/{{session_id}}` 查看完整对话、事件和复盘轨迹
10. 关键执行结果调用 `POST /api/v1/agent/events` 写入 Agent 记忆

## 接入说明

这个服务不绑定特定 Agent 客户端。任何能够读取 Skill / OpenAPI 并发起 HTTP 请求的 Agent，
都可以作为买家、卖家或运营观察员接入。`buyer_agent_name`、`seller_agent_name` 和
`actor_agent` 只是记录来源名称，可以填写 Qclaw、WorkBuddy、小龙虾、爱马仕或其他 Agent 名称。

## 推荐提示词

请安装并使用这个二手车 Agent 意向大厅 Skill：

`{PUBLIC_BASE_URL}/skill.md`

安装后，先读取 OpenAPI，并帮我完成一次测试流程：

- 创建一个买家用户
- 创建一个车商用户
- 发布一辆测试车源
- 发布一个买车需求
- 查询需求匹配结果
- 创建并运行一次自动协商会话

如果接口返回正常，再根据我的真实买车需求继续使用。
"""


@app.get("/.well-known/agent.json")
async def agent_manifest() -> Dict[str, Any]:
    return {
        "name": APP_TITLE,
        "version": APP_VERSION,
        "description": "工具型二手车 A2A 意向撮合、车辆档案与 Agent 协商服务。",
        "base_url": PUBLIC_BASE_URL,
        "openapi_url": f"{PUBLIC_BASE_URL}/openapi.json",
        "skill_url": f"{PUBLIC_BASE_URL}/skill.md",
        "constraints": [
            "不提供支付",
            "不提供托管",
            "不提供贷款",
            "不提供金融推荐",
        ],
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


@app.post("/api/v1/matches", dependencies=[Depends(require_admin_token)])
async def create_match(
    match_data: MatchCreate,
    db=Depends(get_db)
) -> Dict[str, Any]:
    memory = get_memory_service(db)
    result = memory.create_match(
        demand_id=match_data.demand_id,
        car_id=match_data.car_id,
        score=match_data.match_score,
        reason=match_data.match_reason
    )
    return {"success": True, "data": result}


@app.patch("/api/v1/matches/{match_id}")
async def update_match_status(
    match_id: str,
    status_data: MatchStatusUpdate,
    db=Depends(get_db)
) -> Dict[str, Any]:
    memory = get_memory_service(db)
    match_record = memory.update_match_status(match_id, status_data.status)
    if not match_record:
        raise HTTPException(status_code=404, detail="匹配记录不存在")
    return {"success": True, "data": match_record}


@app.post("/api/v1/matches/{match_id}/session")
async def create_session_from_match(
    match_id: str,
    req: MatchSessionRequest,
    db=Depends(get_db)
) -> Dict[str, Any]:
    memory = get_memory_service(db)
    from models.match import MatchPool
    match_record = db.query(MatchPool).filter(MatchPool.match_id == match_id).first()
    if not match_record:
        raise HTTPException(status_code=404, detail="匹配记录不存在")
    
    # 获取 Demand 和 Car
    demand = match_record.demand
    car = match_record.car
    
    if not demand or not car:
        raise HTTPException(status_code=400, detail="关联数据不完整")
        
    # 构造 Session 创建请求
    session_payload = {
        "buyer_id": demand.user_id,
        "seller_id": car.owner_id,
        "car_id": car.car_id,
        "buyer_goal": f"根据匹配建议({match_record.match_reason})发起协商",
        "buyer_agent_name": req.buyer_agent_name,
        "seller_agent_name": req.seller_agent_name,
        "max_rounds": req.max_rounds,
        "buyer_budget_max": demand.budget_max,
        "buyer_target_price": demand.budget_min if demand.budget_min > 0 else None
    }
    
    # 为了保持逻辑一致性，我们手动生成 session_id 并记录 auto_session_created
    session_id = f"match_session_{match_id}"
    
    _record_agent_event(
        db,
        actor_agent="platform-orchestrator",
        actor_role="platform",
        event_type="auto_session_created",
        status="succeeded",
        user_id=demand.user_id,
        related_user_id=car.owner_id,
        related_car_id=car.car_id,
        related_conversation_id=session_id,
        input_snapshot=session_payload,
        observation=f"基于匹配记录 {match_id} 启动自动协商"
    )
    
    # 更新匹配状态
    match_record.status = "negotiating"
    match_record.session_id = session_id
    db.commit()
    
    return {
        "success": True, 
        "data": {
            "session_id": session_id,
            "match_id": match_id,
            "status": "negotiating"
        }
    }


@app.post("/api/v1/cars")
async def create_car(
    car_data: CarCreate,
    user_id: Optional[int] = Query(None, description="车主用户ID（建议统一在 Body 中传 owner_id）"),
    db=Depends(get_db),
) -> Dict[str, Any]:
    actual_owner_id = car_data.owner_id or user_id
    if not actual_owner_id:
        raise HTTPException(status_code=400, detail="必须提供车主 ID (owner_id 或 user_id)")

    memory = get_memory_service(db)
    user = memory.get_user(actual_owner_id)
    if not user:
        raise HTTPException(status_code=404, detail="车主不存在")

    # 价格归一化 (P0): 如果输入价格 > 1000，自动判定为“元”，除以 10000 转换为“万元”
    price = car_data.price or 0
    if price > 1000:
        price = round(price / 10000.0, 2)
        
    target_price = car_data.target_price
    if target_price and target_price > 1000:
        target_price = round(target_price / 10000.0, 2)
    elif not target_price:
        target_price = price

    payload = {
        "car_id": f"CAR-{datetime.utcnow().strftime('%Y%m%d')}-{uuid4().hex[:6].upper()}",
        "brand": car_data.brand,
        "series": car_data.series or car_data.brand,
        "model": car_data.model,
        "year": car_data.year,
        "price": price,
        "original_price": car_data.original_price,
        "target_price": target_price,
        "mileage": car_data.mileage,
        "color": car_data.color,
        "region": car_data.region,
        "city": car_data.city,
        "transmission": car_data.transmission,
        "fuel_type": car_data.fuel_type,
        "owner_id": actual_owner_id,
        "is_listed": True,
        "current_status": "上架中",
        "report_url": car_data.report_url,
        "image_urls": car_data.image_urls or [],
        "attachments": car_data.attachments or {},
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


@app.post("/api/v1/cars/{car_id}/record-and-reward")
async def record_and_reward(
    car_id: str,
    request: RecordAndRewardRequest,
    db=Depends(get_db),
) -> Dict[str, Any]:
    """
    一步完成：录入车档 -> 链式存证 -> 发放积分/信誉。

    这是档案库增长的核心激励接口，不涉及支付、托管或金融权益。
    """
    memory = get_memory_service(db)
    car = await memory.get_car_memory(car_id)
    if not car:
        raise HTTPException(status_code=404, detail="车辆不存在")

    user = memory.get_user(request.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="录入用户不存在")

    should_grant_first_record_bonus = memory.check_first_record_bonus(request.user_id)

    result = await memory.add_lifecycle_record(
        car_id=car_id,
        record_type=request.record_type,
        data=request.data,
        signed_by=str(request.user_id),
        remark=request.remark,
    )

    first_record_bonus = None
    if should_grant_first_record_bonus:
        first_record_bonus = memory.grant_first_record_bonus(request.user_id)

    complete_profile_bonus = None
    if memory.check_complete_profile_bonus(request.user_id):
        complete_profile_bonus = memory.grant_complete_profile_bonus(request.user_id)

    return {
        "success": True,
        "message": "车档已链式存证，积分与信誉已更新",
        "data": {
            "record": result.get("record"),
            "reward": result.get("reward"),
            "first_record_bonus": first_record_bonus,
            "complete_profile_bonus": complete_profile_bonus,
        },
    }


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


@app.get("/api/v1/points/{user_id}")
async def get_points_balance(
    user_id: int,
    limit: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
) -> Dict[str, Any]:
    engine = ReputationEngine(db)
    result = engine.get_points_balance(user_id=user_id, limit=limit)
    if not result.get("success"):
        raise HTTPException(status_code=404, detail=result.get("error", "用户不存在"))

    # 对外只展示工具型权益，避免暴露任何金融/贷款表述。
    result.pop("points_value", None)
    result["available_tool_rights"] = {
        "listing_boost_available": result.get("behavior_points", 0) >= engine.BOOST_COST_PER_DAY,
        "listing_boost_cost_per_day": engine.BOOST_COST_PER_DAY,
        "free_evaluation_hint": "如账号有免费估价权益，可用于生成车况整理建议",
    }
    return result


@app.post("/api/v1/cars/{car_id}/boost")
async def boost_car_listing(
    car_id: str,
    user_id: int = Query(..., description="车主用户ID"),
    days: int = Query(3, ge=1, le=30, description="展示优先天数"),
    db=Depends(get_db),
) -> Dict[str, Any]:
    car = db.query(CarMemory).filter(CarMemory.car_id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="车辆不存在")
    if car.owner_id != user_id:
        raise HTTPException(status_code=403, detail="只能为自己的车辆开启展示优先")

    engine = ReputationEngine(db)
    result = engine.boost_listing(user_id=user_id, car_id=car_id, days=days)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "展示优先失败"))

    car.is_boosted = True
    car.boost_expiry = datetime.strptime(result["boost_end"], "%Y-%m-%d %H:%M:%S")
    car.updated_at = datetime.utcnow()
    db.commit()

    return {
        "success": True,
        "message": "车辆已开启展示优先",
        "data": {
            "car_id": car_id,
            "points_used": result["points_used"],
            "remaining_points": result["remaining_points"],
            "boost_expiry": car.boost_expiry.isoformat(),
        },
    }


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


@app.post("/api/v1/agent/sessions")
async def create_agent_session(
    request: AgentSessionCreate,
    db=Depends(get_db),
) -> Dict[str, Any]:
    buyer = db.query(User).filter(User.id == request.buyer_id).first()
    seller = db.query(User).filter(User.id == request.seller_id).first()
    car = db.query(CarMemory).filter(CarMemory.car_id == request.car_id).first()
    if not buyer:
        raise HTTPException(status_code=404, detail="买家不存在")
    if not seller:
        raise HTTPException(status_code=404, detail="卖家不存在")
    if not car:
        raise HTTPException(status_code=404, detail="车辆不存在")
    if car.owner_id != request.seller_id:
        raise HTTPException(status_code=400, detail="车辆不属于该卖家")

    session_id = f"auto_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid4().hex[:8]}"
    config = request.dict()
    config["session_id"] = session_id

    event = _record_agent_event(
        db,
        actor_agent="platform-orchestrator",
        actor_role="platform",
        event_type="auto_session_created",
        status="succeeded",
        user_id=request.buyer_id,
        related_user_id=request.seller_id,
        related_car_id=request.car_id,
        related_conversation_id=session_id,
        input_snapshot=config,
        output_snapshot={
            "buyer": buyer.to_dict(),
            "seller": seller.to_dict(),
            "car": car.to_dict(),
        },
        observation="自动协商会话已创建，等待平台调度买家 Agent 与卖家 Agent 多轮对话。",
    )

    return {
        "success": True,
        "data": {
            "session_id": session_id,
            "event": event,
            "run_url": f"{PUBLIC_BASE_URL}/api/v1/agent/sessions/{session_id}/run",
            "detail_url": f"{PUBLIC_BASE_URL}/api/v1/agent/sessions/{session_id}",
        },
    }


@app.post("/api/v1/agent/sessions/{session_id}/run")
async def run_agent_session(
    session_id: str,
    request: AgentSessionRunRequest = AgentSessionRunRequest(),
    db=Depends(get_db),
) -> Dict[str, Any]:
    config = _get_agent_session_config(db, session_id)
    buyer_id = int(config["buyer_id"])
    seller_id = int(config["seller_id"])
    car_id = str(config["car_id"])
    max_rounds = request.max_rounds or int(config.get("max_rounds") or 3)
    auto_deal = config.get("auto_deal", False) if request.auto_deal is None else request.auto_deal
    if request.buyer_target_price is not None:
        config["buyer_target_price"] = request.buyer_target_price

    car = db.query(CarMemory).filter(CarMemory.car_id == car_id).first()
    if not car:
        raise HTTPException(status_code=404, detail="车辆不存在")

    bus = get_a2a_bus()
    bus.set_db_session(db)

    turns: List[Dict[str, Any]] = []
    initial_message = config.get("initial_message") or (
        f"我是买家 Agent，目标是{config.get('buyer_goal')}。"
        f"请介绍 {car.brand}{car.model} 的车况、价格依据和可议价空间。"
    )

    inquiry_message = MessageBuilder.create_price_inquiry(
        from_user_id=buyer_id,
        to_user_id=seller_id,
        car_id=car_id,
        message=initial_message,
    )
    inquiry_message.session_id = session_id
    inquiry_result = await bus.send(inquiry_message)
    seller_content = _agent_response_content(inquiry_result)
    turns.append({
        "round": 0,
        "type": "inquiry",
        "from": "buyer",
        "to": "seller",
        "message": initial_message,
        "result": inquiry_result,
        "seller_response": seller_content,
    })

    _record_agent_event(
        db,
        actor_agent=config.get("buyer_agent_name", "Qclaw-buyer"),
        actor_role="buyer",
        event_type="auto_inquiry_sent",
        status="succeeded" if inquiry_result.get("success") else "failed",
        user_id=buyer_id,
        related_user_id=seller_id,
        related_car_id=car_id,
        related_conversation_id=session_id,
        input_snapshot={"message": initial_message},
        output_snapshot={"seller_response": seller_content, "raw": inquiry_result},
        observation="买家 Agent 已自动发起询价，卖家 Agent 已返回首轮说明。",
    )

    final_state = "in_progress"
    agreed_price = None
    review_reason = None
    import time
    start_time = time.time()
    max_duration = 20.0

    for round_index in range(1, max_rounds + 1):
        if time.time() - start_time > max_duration:
            print(f"⚠️ Session {session_id} reaching timeout, stopping at round {round_index}")
            final_state = "needs_human_review"
            break
        
        # 为 bus.send 增加单次调用超时，防止 LLM 卡死导致整个会话 504
        # 注意：这里的 bus.send 内部会处理具体的 Agent 逻辑
        
        buyer_prompt = (
            f"卖家上一轮回复：{seller_content}\n"
            f"车辆挂牌价 {car.price} 万元。买家目标：{config.get('buyer_goal')}。"
            "请作为买家 Agent 判断是否继续议价，并给出简短理由。"
        )
        buyer_message = MessageBuilder.create_message(
            from_user_id=seller_id,
            to_user_id=buyer_id,
            content=buyer_prompt,
        )
        buyer_message.session_id = session_id
        buyer_message.is_system = True  # 标记为系统消息，不公开展示
        buyer_result = await bus.send(buyer_message)
        buyer_content = _agent_response_content(buyer_result)

        proposed_price = _calculate_offer_price(car, config, round_index)
        
        # 2. 理性拦截 (P0): 如果出价低于挂牌价的 75%，视为非理性低价，拦截并不发送
        # 这种离谱低价通常是由于数据异常（如年份或品牌评估偏差）导致的，直接发送会损害平台信誉
        rational_floor = car.price * 0.75
        if proposed_price < rational_floor:
            _record_agent_event(
                db,
                actor_agent="platform-orchestrator",
                actor_role="platform",
                event_type="buyer_offer_irrational_intercepted",
                status="warning",
                user_id=buyer_id,
                related_car_id=car_id,
                related_conversation_id=session_id,
                input_snapshot={"proposed_price": proposed_price, "rational_floor": rational_floor},
                observation=f"买家 Agent 报价 {proposed_price} 万，显著低于合理下限 {rational_floor} 万，已拦截并自动转入人工复核。",
            )
            final_state = "needs_human_review"
            observation = f"协商中断：买家出价 {proposed_price} 万过低，已拦截。"
            # 为了 summary 能够重建原因
            db.query(AgentEvent).filter(AgentEvent.related_conversation_id == session_id).order_by(AgentEvent.id.desc()).first().score = -1.0 
            break

        negotiate_reason = (
            f"第 {round_index} 轮自动议价。买家预算/目标："
            f"{config.get('buyer_budget_min') or '未设'}-{config.get('buyer_budget_max') or '未设'} 万，"
            f"买家 Agent 判断：{buyer_content[:240]}"
        )
        negotiate_message = MessageBuilder.create_price_negotiate(
            from_user_id=buyer_id,
            to_user_id=seller_id,
            car_id=car_id,
            current_price=float(car.price or 0),
            proposed_price=proposed_price,
            reason=negotiate_reason,
        )
        negotiate_message.session_id = session_id
        negotiate_result = await bus.send(negotiate_message)
        seller_content = _agent_response_content(negotiate_result)
        deal_ready = _is_deal_ready(car, proposed_price, seller_content)

        turn = {
            "round": round_index,
            "type": "negotiate",
            "buyer_reflection": buyer_content,
            "proposed_price": proposed_price,
            "buyer_confirmed": buyer_confirmed if 'buyer_confirmed' in locals() else False,
            "seller_confirmed": deal_ready,
            "review_reason": review_reason,
            "buyer_result": buyer_result,
            "seller_result": negotiate_result,
        }
        turns.append(turn)

        _record_agent_event(
            db,
            actor_agent="platform-orchestrator",
            actor_role="platform",
            event_type="auto_negotiation_round",
            status="succeeded" if negotiate_result.get("success") else "failed",
            user_id=buyer_id,
            related_user_id=seller_id,
            related_car_id=car_id,
            related_conversation_id=session_id,
            input_snapshot={
                "round": round_index,
                "proposed_price": proposed_price,
                "buyer_reflection": buyer_content,
            },
            output_snapshot={
                "seller_response": seller_content,
                "deal_ready": deal_ready,
            },
            observation=(
                f"自动协商第 {round_index} 轮完成，报价 {proposed_price} 万，"
                f"{'已达成初步意向，等待确认' if deal_ready else '继续博弈'}。"
            ),
            score=1.0 if deal_ready else 0.6,
        )

        if deal_ready:
            # 增加一个主动确认环节
            confirm_prompt = (
                f"买家 Agent 出价 {proposed_price} 万。卖家 Agent 已表示可以考虑。\n"
                "请作为买家 Agent 最终确认：是否确认按照此方案成交？如果确认，请回复“我确认接受此方案”。"
            )
            confirm_message = MessageBuilder.create_message(
                from_user_id=seller_id,
                to_user_id=buyer_id,
                content=confirm_prompt,
            )
            confirm_message.session_id = session_id
            confirm_message.is_system = True  # 确认指令也是系统生成的
            confirm_result = await bus.send(confirm_message)
            confirm_content = _agent_response_content(confirm_result)
            
            # 判断买家是否最终确认
            buyer_confirmed = "确认接受" in confirm_content or "没问题" in confirm_content
            
            # 保存成交确认消息到 conversations，确保用户可见
            confirmation_message = MessageBuilder.create_message(
                from_user_id=buyer_id,
                to_user_id=seller_id,
                content=confirm_content,
            )
            confirmation_message.session_id = session_id
            confirmation_message.is_system = False  # 标记为非系统消息，用户可见
            await bus.send(confirmation_message)

            if buyer_confirmed:
                final_state = "deal_ready"
                agreed_price = proposed_price
                
                # 记录最终成交系统消息
                success_text = f"【系统确认】双方已达成成交意向，最终协商价格为 {agreed_price} 万元。"
                success_message = MessageBuilder.create_message(
                    from_user_id=PLATFORM_ADMIN_ID,
                    to_user_id=buyer_id,
                    content=success_text,
                )
                success_message.session_id = session_id
                success_message.is_system = False
                await bus.send(success_message)
            else:
                # 如果买家反悔或需要进一步确认，继续对话
                final_state = "in_progress"
                observation = "买家在最后确认环节表示犹豫，未达成最终一致。"
            
            if buyer_confirmed and auto_deal:
                deal_message = MessageBuilder.create_deal_intent(
                    from_user_id=buyer_id,
                    to_user_id=seller_id,
                    car_id=car_id,
                    agreed_price=agreed_price,
                    conditions={"next_step": "offline_verification"},
                )
                deal_message.session_id = session_id
                deal_result = await bus.send(deal_message)
                turn["deal_result"] = deal_result
                final_state = "deal_intent_created"
            break

    if final_state == "in_progress":
        final_state = "needs_human_review"
        if not review_reason:
            review_reason = "game_theory_deadlock"

    summary = {
        "session_id": session_id,
        "final_state": final_state,
        "agreed_price": agreed_price,
        "rounds": len([turn for turn in turns if turn["type"] == "negotiate"]),
        "latest_seller_response": seller_content,
        "next_step": (
            "建议线下复核车况并确认见面"
            if final_state in {"deal_ready", "deal_intent_created"}
            else "建议补充车况档案或调整预算后继续"
        ),
        "review_reason": review_reason,
    }

    _record_agent_event(
        db,
        actor_agent="Hermes-lite",
        actor_role="platform",
        event_type="auto_session_completed",
        status="succeeded",
        user_id=buyer_id,
        related_user_id=seller_id,
        related_car_id=car_id,
        related_conversation_id=session_id,
        input_snapshot={"config": config},
        output_snapshot={"summary": summary, "turns_count": len(turns)},
        observation=f"自动协商会话结束：{summary['final_state']}，共 {summary['rounds']} 轮议价。",
        score=1.0 if final_state in {"deal_ready", "deal_intent_created"} else 0.5,
    )

    growth_review = GrowthEngine(db).maybe_auto_review(interval=GROWTH_REVIEW_INTERVAL)

    return {
        "success": True,
        "data": {
            "summary": summary,
            "turns": turns,
            "growth_review": public_growth_review_result(growth_review),
        },
    }


@app.get("/api/v1/agent/sessions/{session_id}")
async def get_agent_session(
    session_id: str,
    db=Depends(get_db),
) -> Dict[str, Any]:
    config = _get_agent_session_config(db, session_id)
    
    # 默认只返回用户可见对话 (is_system=0)
    conversations = (
        db.query(Conversation)
        .filter(Conversation.session_id == session_id)
        .filter(Conversation.is_system == 0)
        .order_by(Conversation.created_at.asc())
        .all()
    )
    
    # 获取会话摘要（从 auto_session_completed 事件中提取）
    completed_event = (
        db.query(AgentEvent)
        .filter(
            AgentEvent.event_type == "auto_session_completed",
            AgentEvent.related_conversation_id == session_id,
        )
        .order_by(AgentEvent.id.desc())
        .first()
    )

    summary = None
    if completed_event:
        summary = completed_event.output_snapshot.get("summary")
        if summary and not summary.get("review_reason") and completed_event.status == "failed":
            summary["review_reason"] = "execution_error_or_timeout"
    
    if not summary:
        # 如果完成事件缺失（可能是超时或正在进行中），尝试从过程事件中重建摘要 (P0)
        latest_round_event = (
            db.query(AgentEvent)
            .filter(
                AgentEvent.event_type == "auto_negotiation_round",
                AgentEvent.related_conversation_id == session_id,
            )
            .order_by(AgentEvent.id.desc())
            .first()
        )
        if latest_round_event:
            out = latest_round_event.output_snapshot or {}
            inp = latest_round_event.input_snapshot or {}
            reason = "协商正在进行或因超时转入人工复核"
            if latest_round_event.score == -1.0:
                 reason = "买家报价过低，已拦截请求人工介入"
            elif latest_round_event.score == 0.0:
                 reason = "Agent 响应超时，转入人工复核"

            summary = {
                "session_id": session_id,
                "final_state": "running_or_timeout",
                "agreed_price": None,
                "rounds": inp.get("round", 0),
                "latest_seller_response": out.get("seller_response", "正在等待回复..."),
                "next_step": "协商已转入人工复核",
                "review_reason": reason,
                "is_progressive": True
            }
        else:
            # 只有初始询价事件
            summary = {
                "session_id": session_id,
                "final_state": "initializing",
                "agreed_price": None,
                "rounds": 0,
                "latest_seller_response": "正在发起初始询价...",
                "next_step": "请耐心等待 Agent 响应",
                "is_progressive": True
            }
    
    # 获取事件并脱敏（移除包含内部 Prompt 的快照）
    events = (
        db.query(AgentEvent)
        .filter(AgentEvent.related_conversation_id == session_id)
        .order_by(AgentEvent.id.asc())
        .all()
    )
    
    safe_events = []
    for e in events:
        ed = e.to_dict()
        # 外部接口移除内部调度 Prompt 快照，仅保留观察摘要
        ed.pop("input_snapshot", None)
        ed.pop("output_snapshot", None)
        safe_events.append(ed)
        
    return JSONResponse(
        content={"success": True, "data": {
            "session_id": session_id,
            "config": config,
            "conversations": [c.to_dict() for c in conversations],
            "events": safe_events,
            "summary": summary,
        }},
        headers={"Content-Type": "application/json; charset=utf-8"}
    )


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


@app.post("/api/v1/agent/events")
async def record_agent_event(
    request: AgentEventCreate,
    db=Depends(get_db),
) -> Dict[str, Any]:
    event = AgentEvent(
        actor_agent=request.actor_agent,
        actor_role=request.actor_role,
        event_type=request.event_type,
        status=request.status,
        user_id=request.user_id,
        related_user_id=request.related_user_id,
        related_car_id=request.related_car_id,
        related_demand_id=request.related_demand_id,
        related_conversation_id=request.related_conversation_id,
        input_snapshot=request.input_snapshot or {},
        output_snapshot=request.output_snapshot or {},
        observation=request.observation,
        score=request.score,
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    auto_review = GrowthEngine(db).maybe_auto_review(interval=GROWTH_REVIEW_INTERVAL)
    return {
        "success": True,
        "message": "Agent 事件已记录",
        "data": event.to_dict(),
        "growth_review": public_growth_review_result(auto_review),
    }


@app.get("/api/v1/admin/database/backup")
async def download_database_backup(
    _: None = Depends(require_admin_token),
):
    db_path = _sqlite_database_path()
    if not db_path.exists():
        raise HTTPException(status_code=404, detail="SQLite 数据库文件不存在")

    temp_dir = Path(mkdtemp(prefix="sqlite-backup-"))
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_path = temp_dir / f"{db_path.stem}_{timestamp}.db"
    _create_sqlite_backup(db_path, backup_path)

    return FileResponse(
        path=str(backup_path),
        filename=backup_path.name,
        media_type="application/octet-stream",
        background=BackgroundTask(lambda: shutil.rmtree(temp_dir, ignore_errors=True)),
    )


@app.post("/api/v1/admin/database/restore")
async def restore_database_backup(
    request: Request,
    _: None = Depends(require_admin_token),
) -> Dict[str, Any]:
    db_path = _sqlite_database_path()
    payload = await request.body()
    if not payload:
        raise HTTPException(status_code=400, detail="请求体为空，请上传 SQLite 备份文件")

    temp_dir = Path(mkdtemp(prefix="sqlite-restore-"))
    try:
        uploaded_path = temp_dir / "uploaded.db"
        uploaded_path.write_bytes(payload)
        _assert_valid_sqlite(uploaded_path)

        db_path.parent.mkdir(parents=True, exist_ok=True)
        pre_restore_backup = None
        if db_path.exists():
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            pre_restore_backup = db_path.with_name(f"{db_path.stem}.pre_restore_{timestamp}.db")
            _create_sqlite_backup(db_path, pre_restore_backup)

        replacement_path = temp_dir / "replacement.db"
        _create_sqlite_backup(uploaded_path, replacement_path)

        engine.dispose()
        replacement_path.replace(db_path)
        init_database()

        return {
            "success": True,
            "message": "SQLite 数据库已恢复",
            "data": {
                "database_path": str(db_path),
                "pre_restore_backup": str(pre_restore_backup) if pre_restore_backup else None,
            },
        }
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


@app.get("/api/v1/admin/agent-events")
async def list_agent_events(
    actor_role: Optional[str] = Query(None),
    event_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    related_conversation_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    _: None = Depends(require_admin_token),
) -> Dict[str, Any]:
    query = db.query(AgentEvent)
    if actor_role:
        query = query.filter(AgentEvent.actor_role == actor_role)
    if event_type:
        query = query.filter(AgentEvent.event_type == event_type)
    if status:
        query = query.filter(AgentEvent.status == status)
    if related_conversation_id:
        query = query.filter(AgentEvent.related_conversation_id == related_conversation_id)

    events = query.order_by(AgentEvent.created_at.desc()).limit(limit).all()
    return {"success": True, "total": len(events), "data": [event.to_dict() for event in events]}


@app.post("/api/v1/admin/growth/reviews/run")
async def run_growth_review(
    request: GrowthReviewRunRequest,
    db=Depends(get_db),
    _: None = Depends(require_admin_token),
) -> Dict[str, Any]:
    result = GrowthEngine(db).run_review(
        trigger="manual",
        after_event_id=request.after_event_id,
        limit=request.limit,
        min_events=request.min_events,
    )
    return result


@app.get("/api/v1/admin/growth/reviews")
async def list_growth_reviews(
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    _: None = Depends(require_admin_token),
) -> Dict[str, Any]:
    reviews = GrowthEngine(db).list_reviews(limit=limit)
    return {"success": True, "total": len(reviews), "data": reviews}


@app.get("/api/v1/admin/growth/skill-candidates")
async def list_skill_candidates(
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db=Depends(get_db),
    _: None = Depends(require_admin_token),
) -> Dict[str, Any]:
    candidates = GrowthEngine(db).list_skill_candidates(status=status, limit=limit)
    return {"success": True, "total": len(candidates), "data": candidates}


@app.get("/api/v1/admin/analytics/funnel")
async def get_admin_funnel(
    limit_unmatched: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    _: None = Depends(require_admin_token),
) -> Dict[str, Any]:
    memory = get_memory_service(db)

    total_users = db.query(User).count()
    dealer_users = db.query(User).filter(User.is_dealer == True).count()
    total_cars = db.query(CarMemory).count()
    listed_cars = db.query(CarMemory).filter(CarMemory.is_listed == True).count()
    total_demands = db.query(DemandPool).count()
    active_demands = db.query(DemandPool).filter(DemandPool.status == "active").count()
    lifecycle_records = db.query(CarLifecycleRecord).count()
    conversations = db.query(Conversation).count()
    inquiries = db.query(Conversation).filter(Conversation.intent == "price_inquiry").count()
    negotiations = db.query(Conversation).filter(Conversation.intent == "price_negotiate").count()
    deal_intents = db.query(Conversation).filter(Conversation.intent == "deal_intent").count()
    agent_events = db.query(AgentEvent).count()
    growth_reviews = db.query(GrowthReview).count()
    skill_candidates = db.query(SkillCandidate).count()

    unmatched_demands = []
    active_demand_rows = (
        db.query(DemandPool)
        .filter(DemandPool.status == "active")
        .order_by(DemandPool.created_at.desc())
        .limit(limit_unmatched)
        .all()
    )
    for demand in active_demand_rows:
        result = memory.find_demand_matches(demand_id=demand.demand_id, limit=1)
        if result.get("success") and result.get("total", 0) == 0:
            unmatched_demands.append(demand.to_dict())

    return {
        "success": True,
        "data": {
            "funnel": {
                "users": total_users,
                "dealers": dealer_users,
                "cars": total_cars,
                "listed_cars": listed_cars,
                "demands": total_demands,
                "active_demands": active_demands,
                "lifecycle_records": lifecycle_records,
                "conversations": conversations,
                "inquiries": inquiries,
                "negotiations": negotiations,
                "deal_intents": deal_intents,
                "agent_events": agent_events,
                "growth_reviews": growth_reviews,
                "skill_candidates": skill_candidates,
            },
            "manager_attention": {
                "unmatched_active_demands": unmatched_demands,
                "unmatched_count_in_sample": len(unmatched_demands),
                "next_actions": [
                    "让车商 Agent 补充符合预算和城市的车源",
                    "让买家 Agent 解释是否接受放宽预算或品牌",
                    "记录匹配失败原因，沉淀为后续调度规则",
                ],
            },
        },
    }


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
