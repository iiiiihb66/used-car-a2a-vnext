from __future__ import annotations

import uuid
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

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
        assert len(detail["data"]["conversations"]) >= 4, detail["data"]
        assert len(detail["data"]["events"]) >= 3, detail["data"]

        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200, openapi.text
        assert "/api/v1/agent/sessions" in openapi.json()["paths"]


if __name__ == "__main__":
    main()
