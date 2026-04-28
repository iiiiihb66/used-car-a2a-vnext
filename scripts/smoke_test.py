from __future__ import annotations

import os
import uuid
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token")

from app import app


def assert_ok(response, label: str) -> dict:
    assert response.status_code == 200, f"{label}: {response.status_code} {response.text}"
    data = response.json()
    assert data.get("success", True) is True, f"{label}: {data}"
    return data


def main() -> None:
    with TestClient(app) as client:
        health = client.get("/health")
        root = client.get("/")
        assert health.status_code == 200, health.text
        assert health.json()["status"] == "healthy"
        assert root.status_code == 200, root.text
        assert root.json()["mode"] == "tool"

        token = uuid.uuid4().hex[:8]
        buyer = assert_ok(
            client.post(
                "/api/v1/users",
                json={
                    "name": f"buyer-{token}",
                    "email": f"buyer-{token}@example.com",
                    "is_dealer": False,
                    "buyer_persona": {
                        "preferred_brands": ["丰田", "比亚迪"],
                        "budget_range": {"min": 9, "max": 15},
                        "negotiation_style": "理性",
                    },
                },
            ),
            "create buyer",
        )
        seller = assert_ok(
            client.post(
                "/api/v1/users",
                json={
                    "name": f"seller-{token}",
                    "email": f"seller-{token}@example.com",
                    "is_dealer": True,
                    "seller_persona": {
                        "city": "北京",
                        "style": "透明专业",
                        "negotiation_flexibility": "中等",
                    },
                },
            ),
            "create seller",
        )
        buyer_id = buyer["data"]["id"]
        seller_id = seller["data"]["id"]

        car = assert_ok(
            client.post(
                f"/api/v1/cars?user_id={seller_id}",
                json={
                    "brand": "丰田",
                    "model": "卡罗拉",
                    "year": 2021,
                    "price": 9.8,
                    "target_price": 9.5,
                    "mileage": 3.2,
                    "region": "北京",
                    "city": "北京",
                },
            ),
            "create car",
        )
        car_id = car["data"]["car_id"]

        demand = assert_ok(
            client.post(
                "/api/v1/demands",
                json={
                    "user_id": buyer_id,
                    "car_type": "紧凑型轿车",
                    "brand_preference": "丰田",
                    "budget_min": 9,
                    "budget_max": 10,
                    "region": "北京",
                    "city": "北京",
                    "year_min": 2020,
                    "mileage_max": 5,
                },
            ),
            "create demand",
        )
        demand_id = demand["data"]["demand_id"]

        matches = assert_ok(client.get(f"/api/v1/demands/{demand_id}/matches"), "match demand")
        assert matches["total"] >= 1, matches

        session = assert_ok(
            client.post(
                "/api/v1/agent/sessions",
                json={
                    "buyer_id": buyer_id,
                    "seller_id": seller_id,
                    "car_id": car_id,
                    "buyer_goal": "北京家用车，预算9到10万，要求车况透明并有合理议价空间",
                    "buyer_budget_min": 9,
                    "buyer_budget_max": 10,
                    "buyer_target_price": 9.5,
                    "max_rounds": 2,
                    "auto_deal": False,
                },
            ),
            "create agent session",
        )
        session_id = session["data"]["session_id"]

        run = assert_ok(
            client.post(f"/api/v1/agent/sessions/{session_id}/run", json={"max_rounds": 2}),
            "run agent session",
        )
        summary = run["data"]["summary"]
        assert summary["session_id"] == session_id, summary
        assert summary["rounds"] >= 1, summary
        assert summary["final_state"] in {
            "deal_ready",
            "deal_intent_created",
            "needs_human_review",
        }, summary
        assert len(run["data"]["turns"]) >= 2, run["data"]

        detail = assert_ok(client.get(f"/api/v1/agent/sessions/{session_id}"), "get agent session")
        # 1. 验证摘要持久化 (P0)
        summary = detail["data"].get("summary")
        assert summary is not None, "Summary should be persisted in GET session"
        assert summary["final_state"] in {"deal_ready", "deal_intent_created"}, f"Unexpected final state: {summary['final_state']}"
        assert summary["agreed_price"] >= 9.5, f"Floor price protection failed: {summary['agreed_price']}"
        
        # 2. 验证成交确认消息进入对话历史 (P1)
        conversations = detail["data"]["conversations"]
        has_confirm = any("成交确认" in c.get("content", "") or "确认接受" in c.get("content", "") for c in conversations)
        assert has_confirm, "Final confirmation message not found in conversations"
        
        # 3. 验证是否过滤了内部指令 (is_system=1)
        assert len(conversations) >= 5, detail["data"] # 增加确认消息后，对话数应增加
        
        for conv in conversations:
            content = conv.get("content", "")
            # 关键词黑名单：不应出现任何调度器/Agent 指令
            blacklist = ["请作为买家 Agent", "请作为卖家 Agent", "判断是否继续议价", "调度器"]
            for word in blacklist:
                assert word not in content, f"Leakage detected: {word} found in public conversation: {content}"
        
        # 4. 验证 events 是否已脱敏 (不包含 input_snapshot/output_snapshot)
        assert len(detail["data"]["events"]) >= 3, detail["data"]
        for event in detail["data"]["events"]:
            assert "input_snapshot" not in event or event["input_snapshot"] == {}, f"Leakage detected: input_snapshot found in public events: {event}"
            assert "output_snapshot" not in event or event["output_snapshot"] == {}, f"Leakage detected: output_snapshot found in public events: {event}"
            
        print("✅ Agent session run and verification passed (Summary & Consistency OK)")

        backup = client.get(
            "/api/v1/admin/database/backup",
            headers={"X-Admin-Token": os.environ["ADMIN_TOKEN"]},
        )
        assert backup.status_code == 200, backup.text
        assert backup.content.startswith(b"SQLite format 3"), "admin database backup is not SQLite"
        print("✅ Admin backup test passed")

        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200, openapi.text
        assert "/api/v1/agent/sessions" in openapi.json()["paths"]
        assert "/api/v1/admin/database/backup" in openapi.json()["paths"]


if __name__ == "__main__":
    main()
