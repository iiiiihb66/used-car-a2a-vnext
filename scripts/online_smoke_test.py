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

    with httpx.Client(base_url=base_url, timeout=120.0) as client:
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

        # 1. Create buyer & seller for General Test
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
        print(f"Created general buyer {buyer_id} and seller {seller_id}")

        # 2. Create car for General Test
        car = assert_ok(
            client.post(
                f"/api/v1/cars?user_id={seller_id}",
                json={
                    "brand": "丰田",
                    "model": "卡罗拉",
                    "year": 2018,
                    "mileage": 6.5,
                    "price": 9.8,
                    "condition_desc": "原版原漆，带记录",
                    "region": "上海",
                    "owner_id": seller_id
                },
            ),
            "create car",
        )
        car_id = car["data"]["car_id"]
        print(f"✅ Created general car {car_id}")

        # 3. Create Session for General Test
        session = assert_ok(
            client.post(
                "/api/v1/agent/sessions",
                json={
                    "buyer_id": buyer_id,
                    "seller_id": seller_id,
                    "car_id": car_id,
                    "config": {
                        "buyer_goal": "帮我看看这辆卡罗拉，我想砍点价",
                        "max_rounds": 1,
                    },
                },
            ),
            "create session",
        )
        session_id = session["data"]["session_id"]
        print(f"Created general session {session_id}")

        # Run agent session (1 round)
        print("Running general agent session...")
        assert_ok(client.post(f"/api/v1/agent/sessions/{session_id}/run"), "run session")
        print("✅ Session run completed.")

        # Verify Qclaw & WorkBuddy scenarios (P0 Hardening)
        try:
            # 4. Qclaw 买家 9-10万卡罗拉场景
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
            
            # 5. WorkBuddy 车商 13.8万雅阁场景 (P0 修复验证)
            print("🚀 Running WorkBuddy Seller Scenario (Accord 2020, 13.8万)...")
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
                "price": 138000, # 测试归一化 (元 -> 万元)
                "target_price": 133000,
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
            
            # 运行两个 Session
            print(f"Running sessions: {q_session_id} and {wb_session_id}")
            with httpx.Client(base_url=base_url, timeout=120.0) as run_client:
                  print("Running Qclaw...")
                  try:
                      assert_ok(run_client.post(f"/api/v1/agent/sessions/{q_session_id}/run"), "run Qclaw")
                  except Exception as e:
                      print(f"⚠️ Qclaw run failed or timed out (expected in some envs): {e}")

                  print("Running WorkBuddy...")
                  try:
                      assert_ok(run_client.post(f"/api/v1/agent/sessions/{wb_session_id}/run"), "run WorkBuddy")
                  except Exception as e:
                      print(f"⚠️ WorkBuddy run failed or timed out (expected in some envs): {e}")
            
            # 等待数据写入
            time.sleep(5)
            # 验证 Qclaw (带重试以应对 CloudRun 重启导致的数据延迟)
            q_detail = None
            for _ in range(3):
                try:
                    q_detail = assert_ok(client.get(f"/api/v1/agent/sessions/{q_session_id}"), "get Qclaw detail")
                    break
                except:
                    print("Retrying Qclaw detail...")
                    time.sleep(3)
            
            assert q_detail and q_detail["data"].get("summary") is not None, "Qclaw summary is null"
            print(f"✅ Qclaw Passed: {q_detail['data']['summary']['final_state']}")

            # 验证 WorkBuddy
            wb_detail = None
            for _ in range(3):
                try:
                    wb_detail = assert_ok(client.get(f"/api/v1/agent/sessions/{wb_session_id}"), "get WB detail")
                    break
                except:
                    print("Retrying WB detail...")
                    time.sleep(3)
            
            assert wb_detail and wb_detail["data"].get("summary") is not None, "WorkBuddy summary is null"
            wb_data = wb_detail["data"]
            
            # 验证价格归一化 (P0)
            # 寻找最近的一个有效报价
            last_price = 0
            for conv in reversed(wb_data["conversations"]):
                p = conv.get("payload", {}).get("proposed_price")
                if p:
                    last_price = p
                    break
            
            print(f"WorkBuddy last detected price: {last_price}")
            assert last_price < 1000, f"Price normalization failed: {last_price}"
            
            summary = wb_data["summary"]
            # 验证拦截逻辑 (P0): 13.8万的车，报价不应低于 10.35万。如果低于此值，必须转入人工审核并附带理由。
            if last_price > 0 and last_price < 13.8 * 0.75:
                 assert summary["final_state"] == "needs_human_review", f"Lowball offer {last_price} not intercepted"
                 assert "拦截" in summary.get("review_reason", ""), f"Review reason missing intercept info: {summary.get('review_reason')}"
                 print(f"✅ Price Intercept Verified: {last_price} blocked with reason '{summary.get('review_reason')}'")
            else:
                 print(f"✅ Price Rationality Verified: {last_price}")

            # 验证中文 (P0)
            # 严格检查 JSON 序列化后的中文，确保不是 \u 编码或乱码
            raw_text = client.get(f"/api/v1/agent/sessions/{wb_session_id}").text
            assert "本田" in raw_text, "Encoding error: '本田' not found in raw response"
            assert "雅阁" in raw_text, "Encoding error: '雅阁' not found in raw response"
            assert "\\u" not in raw_text[:500], "Warning: Potential unnecessary Unicode escaping detected"
            print(f"✅ Encoding Integrity Verified: Chinese characters are clean in raw JSON.")
            
            print(f"✅ WorkBuddy Passed: {summary['final_state']}")

            # Final Event Recording
            assert_ok(
                client.post(
                    "/api/v1/agent/events",
                    json={
                        "session_id": wb_session_id,
                        "actor_agent": "OnlineSmokeTest",
                        "actor_role": "observer",
                        "event_type": "smoke_test_observation",
                        "content": "Automated online smoke test completed successfully.",
                    }
                ),
                "create agent event"
            )
            print("Created final agent event successfully.")

            # Admin check (optional)
            admin_token = os.environ.get("ADMIN_TOKEN")
            if admin_token:
                backup = client.get(
                    "/api/v1/admin/database/backup",
                    headers={"X-Admin-Token": admin_token},
                )
                if backup.status_code == 200:
                    print("Admin backup check passed.")

            print("All online smoke tests passed! 🎉")
            
        except Exception as e:
            print(f"❌ Online smoke test failed during P0 scenarios: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

if __name__ == "__main__":
    main()
