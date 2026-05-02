from __future__ import annotations

import argparse
import os
import sys
import uuid

import httpx


DEFAULT_BASE_URL = "https://used-car-a2a-vnext-249890-8-1407936127.sh.run.tcloudbase.com"


def assert_ok(response: httpx.Response, label: str) -> dict:
    assert response.status_code == 200, f"{label}: {response.status_code} {response.text}"
    data = response.json()
    assert data.get("success", True) is True, f"{label}: {data}"
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate online match -> A2A session flow.")
    parser.add_argument("--url", default=DEFAULT_BASE_URL, help="Base URL of the online API.")
    parser.add_argument(
        "--admin-token",
        default=os.getenv("ADMIN_TOKEN"),
        help="Admin token for protected match creation; defaults to ADMIN_TOKEN.",
    )
    args = parser.parse_args()

    if not args.admin_token:
        print("[error] Missing admin token. Set ADMIN_TOKEN or pass --admin-token.")
        return 1

    base_url = args.url.rstrip("/")
    token = uuid.uuid4().hex[:6]
    headers = {"X-Admin-Token": args.admin_token}

    print(f"Starting online match validation against {base_url} (token={token})")

    with httpx.Client(base_url=base_url, timeout=180.0) as client:
        health = client.get("/health")
        assert health.status_code == 200, health.text
        assert health.json()["status"] == "healthy"

        buyer = assert_ok(
            client.post(
                "/api/v1/users",
                json={
                    "name": f"match-buyer-{token}",
                    "email": f"match-buyer-{token}@example.com",
                    "is_dealer": False,
                },
            ),
            "create buyer",
        )
        seller = assert_ok(
            client.post(
                "/api/v1/users",
                json={
                    "name": f"match-seller-{token}",
                    "email": f"match-seller-{token}@example.com",
                    "is_dealer": True,
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
                    "brand": "本田",
                    "model": "思域",
                    "year": 2021,
                    "price": 10.5,
                    "target_price": 10.2,
                    "mileage": 2.5,
                    "region": "北京",
                    "city": "北京",
                    "report_url": "https://example.com/online-report",
                    "image_urls": ["online_img1.jpg"],
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
                    "car_type": "轿车",
                    "budget_min": 10,
                    "budget_max": 11,
                    "brand_preference": "本田",
                    "region": "北京",
                    "city": "北京",
                },
            ),
            "create demand",
        )
        demand_id = demand["data"]["demand_id"]

        match = assert_ok(
            client.post(
                "/api/v1/matches",
                headers=headers,
                json={
                    "demand_id": demand_id,
                    "car_id": car_id,
                    "match_score": 98.5,
                    "match_reason": "在线测试匹配理由",
                },
            ),
            "create match",
        )
        match_id = match["data"]["match_id"]

        patched = assert_ok(
            client.patch(f"/api/v1/matches/{match_id}", json={"status": "interested"}),
            "patch match status",
        )
        assert patched["data"]["status"] == "interested", patched

        session = assert_ok(
            client.post(
                f"/api/v1/matches/{match_id}/session",
                json={"buyer_agent_name": "Online-Match-Tester", "max_rounds": 2},
            ),
            "create session from match",
        )
        session_id = session["data"]["session_id"]

        run = assert_ok(client.post(f"/api/v1/agent/sessions/{session_id}/run"), "run session")
        summary = run["data"]["summary"]
        assert summary["session_id"] == session_id, summary

        detail = assert_ok(client.get(f"/api/v1/agent/sessions/{session_id}"), "get session detail")
        assert detail["data"].get("summary") is not None, detail["data"]
        assert len(detail["data"].get("conversations", [])) >= 2, detail["data"]
        assert len(detail["data"].get("events", [])) >= 2, detail["data"]

        print("Online match validation passed.")
        print(f"match_id={match_id}")
        print(f"session_id={session_id}")
        print(f"final_state={summary.get('final_state')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
