from __future__ import annotations

import os
import sys
import uuid
import time
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
        try:
            health = client.get("/health")
            if health.status_code == 503:
                print("⚠️  Received 503 (Service Temporarily Unavailable). This is likely a CloudRun cold start. Retrying in 10s...")
                time.sleep(10)
                health = client.get("/health")
            
            assert health.status_code == 200, f"Health check failed: {health.status_code} {health.text}"
            assert health.json()["status"] == "healthy"
            print("Health check passed.")
        except httpx.ConnectError as e:
            print(f"❌ Connection error: {e}. Check if the URL is correct and the service is up.")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Unexpected error during health check: {e}")
            sys.exit(1)

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
        print(f"✅ Created car {car_id}")

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
            print(f"✅ Session run completed. Final state: {summary['final_state']}")

        # 验证详情 (增加重试逻辑以应对线上可能的微小延迟)
        print("Waiting for session summary to be indexed...")
        time.sleep(2)
        
        detail = assert_ok(client.get(f"/api/v1/agent/sessions/{session_id}"), "get agent session")
        data = detail["data"]
        
        # 1. 验证摘要持久化 (P0)
        summary = data.get("summary")
        if summary is None:
             print("⚠️ Summary not found on first try, retrying after 3s...")
             time.sleep(3)
             detail = assert_ok(client.get(f"/api/v1/agent/sessions/{session_id}"), "get agent session retry")
             data = detail["data"]
             summary = data.get("summary")
             
        assert summary is not None, f"Online: Summary should be persisted in GET session. Data: {data}"
        assert summary["final_state"] in {"deal_ready", "deal_intent_created", "needs_human_review"}, summary
        assert "agreed_price" in summary, "Online: agreed_price should be in summary"
        assert "rounds" in summary, "Online: rounds should be in summary"
        
        # 2. 验证是否过滤了内部指令 (is_system=1)
        conversations = data["conversations"]
        events = data["events"]
        assert len(conversations) >= 2, data
        
        for conv in conversations:
            content = conv.get("content", "")
            assert content != "", "Content should not be empty"
            blacklist = ["请作为买家 Agent", "请作为卖家 Agent", "判断是否继续议价", "调度器"]
            for word in blacklist:
                assert word not in content, f"Leakage detected online: {word} found in public conversation: {content}"
        
        # 3. 验证 events 是否已脱敏
        for event in events:
            assert "input_snapshot" not in event or event["input_snapshot"] == {}, f"Leakage online: input_snapshot"
            assert "output_snapshot" not in event or event["output_snapshot"] == {}, f"Leakage online: output_snapshot"
            
        print(f"✅ Verified session details: state={summary['final_state']}, price={summary.get('agreed_price')}")

    try:
        # 4. 专项测试：Qclaw 买家 9-10万卡罗拉场景
        print("🚀 Running Qclaw Buyer Scenario (Corolla, 9-10万)...")
        qclaw_session = assert_ok(client.post("/api/v1/agent/sessions", json={
            "buyer_id": buyer_id,
            "seller_id": seller_id,
            "car_id": car_id,
            "config": {
                "buyer_goal": "想买个卡罗拉，9.5万以内",
                "buyer_target_price": 9.2,
                "buyer_budget_max": 9.8,
                "max_rounds": 2,
                "buyer_agent_name": "Qclaw-Buyer"
            }
        }), "create Qclaw session")
        q_session_id = qclaw_session["data"]["session_id"]
        
        # 5. 专项测试：WorkBuddy 车商 13.8万雅阁场景 (P0 修复验证)
        print("🚀 Running WorkBuddy Seller Scenario (Accord 2020, 13.8万)...")
        # 使用 138000 测试价格归一化
        wb_seller = assert_ok(client.post("/api/v1/users", json={
            "name": "北京鼎诚车行",
            "email": f"wb_seller_{uuid.uuid4().hex[:4]}@example.com",
            "role": "seller",
            "region": "北京",
            "is_dealer": True
        }), "create WB seller")
        wb_seller_id = wb_seller["data"]["id"]
        
        wb_car = assert_ok(client.post("/api/v1/cars", json={
            "brand": "本田",
            "model": "雅阁",
            "year": 2020,
            "mileage": 4.5,
            "price": 138000, # 测试归一化
            "target_price": 133000, # 测试归一化
            "region": "北京",
            "owner_id": wb_seller_id
        }), "create WB car")
        wb_car_id = wb_car["data"]["car_id"]
        
        wb_session = assert_ok(client.post("/api/v1/agent/sessions", json={
            "buyer_id": buyer_id,
            "seller_id": wb_seller_id,
            "car_id": wb_car_id,
            "config": {
                "buyer_goal": "找个雅阁，家用，价格13万左右",
                "buyer_target_price": 13.0,
                "buyer_budget_max": 13.5,
                "max_rounds": 2,
                "buyer_agent_name": "Qclaw-Buyer",
                "seller_agent_name": "WorkBuddy-Seller"
            }
        }), "create WB session")
        wb_session_id = wb_session["data"]["session_id"]
        
        # 并行/连续运行两个 Session
        print(f"Running sessions: {q_session_id} and {wb_session_id}")
        with httpx.Client(base_url=base_url, timeout=150.0) as run_client:
             print("Running Qclaw...")
             assert_ok(run_client.post(f"/api/v1/agent/sessions/{q_session_id}/run"), "run Qclaw")
             print("Running WorkBuddy...")
             assert_ok(run_client.post(f"/api/v1/agent/sessions/{wb_session_id}/run"), "run WorkBuddy")
             
        # 验证 Qclaw
        q_detail = assert_ok(client.get(f"/api/v1/agent/sessions/{q_session_id}"), "get Qclaw detail")
        assert q_detail["data"].get("summary") is not None, "Qclaw summary is null"
        print(f"✅ Qclaw Passed: {q_detail['data']['summary']['final_state']}")

        # 验证 WorkBuddy
        wb_detail = assert_ok(client.get(f"/api/v1/agent/sessions/{wb_session_id}"), "get WB detail")
        wb_data = wb_detail["data"]
        assert wb_data.get("summary") is not None, "WorkBuddy summary is null"
        
        # 验证价格归一化 (P0)
        # 13.8万车，50% 应该是 6.9万。如果出现 69000 则失败。
        summary = wb_data["summary"]
        last_price = wb_data["conversations"][-1].get("payload", {}).get("proposed_price", 0)
        print(f"WorkBuddy final price: {last_price}")
        assert last_price < 1000, f"Price normalization failed: {last_price}"
        assert last_price >= 13.8 * 0.5, f"Price too low: {last_price}"
        
        # 验证中文 (P0)
        assert "本田" in str(wb_data), "Encoding error: '本田' not found"
        
        print(f"✅ WorkBuddy Passed: {summary['final_state']}")

        # 6. Admin check
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
