from __future__ import annotations

import os
import sys
import uuid
import argparse
import httpx

DEFAULT_BASE_URL = "https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com"

def assert_ok(response: httpx.Response, label: str) -> dict:
    assert response.status_code == 200, f"{label}: {response.status_code} {response.text}"
    data = response.json()
    assert data.get("success", True) is True, f"{label}: {data}"
    return data

def main():
    parser = argparse.ArgumentParser(description="Run smoke tests against the online MVP API.")
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help="Base URL of the online API.")
    args = parser.parse_args()

    base_url = args.url.rstrip("/")

    print(f"Starting online smoke test against {base_url} ...")

    with httpx.Client(base_url=base_url, timeout=90.0) as client:
        # Health Check
        health = client.get("/health")
        assert health.status_code == 200, health.text
        assert health.json()["status"] == "healthy"
        print("Health check passed.")

        # Root Check
        root = client.get("/")
        assert root.status_code == 200, root.text
        assert root.json()["mode"] == "tool"
        print("Root tool mode check passed.")

        # OpenAPI Check
        openapi = client.get("/openapi.json")
        assert openapi.status_code == 200, openapi.text
        assert "/api/v1/agent/sessions" in openapi.json()["paths"]
        print("OpenAPI spec check passed.")

        # Create buyer & seller
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
        print(f"Created buyer {buyer_id} and seller {seller_id}")

        # Create car
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
        print(f"Created car {car_id}")

        # Create session
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
                    "buyer_agent_name": "OnlineSmokeTest-Buyer",
                    "seller_agent_name": "OnlineSmokeTest-Seller",
                },
            ),
            "create agent session",
        )
        session_id = session["data"]["session_id"]
        print(f"Created session {session_id}")

        print("Running agent session, this may take a while (hitting Hunyuan)...")
        with httpx.Client(base_url=base_url, timeout=120.0) as run_client:
            run = assert_ok(
                run_client.post(f"/api/v1/agent/sessions/{session_id}/run", json={"max_rounds": 1}),
                "run agent session",
            )
            summary = run["data"]["summary"]
            assert summary["session_id"] == session_id, summary
            assert summary["rounds"] >= 1, summary
            print(f"Session run completed. Final state: {summary['final_state']}")

        # Verify detail
        detail = assert_ok(client.get(f"/api/v1/agent/sessions/{session_id}"), "get agent session")
        assert len(detail["data"]["conversations"]) >= 1, detail["data"]
        print(f"Verified session details, {len(detail['data']['conversations'])} conversations found.")

        # Test event emission
        event = assert_ok(
            client.post(
                "/api/v1/agent/events",
                json={
                    "session_id": session_id,
                    "actor_agent": "OnlineSmokeTest",
                    "actor_role": "observer",
                    "event_type": "smoke_test_observation",
                    "content": "Automated online smoke test completed successfully.",
                }
            ),
            "create agent event"
        )
        print("Created agent event successfully.")

        # Admin check
        admin_token = os.environ.get("ADMIN_TOKEN")
        if admin_token:
            backup = client.get(
                "/api/v1/admin/database/backup",
                headers={"X-Admin-Token": admin_token},
            )
            assert backup.status_code == 200, backup.text
            assert backup.content.startswith(b"SQLite format 3"), "admin database backup is not SQLite"
            print("Admin backup check passed.")
        else:
            print("Skipped admin backup check (ADMIN_TOKEN not set).")

        print("All online smoke tests passed! 🎉")

if __name__ == "__main__":
    main()
