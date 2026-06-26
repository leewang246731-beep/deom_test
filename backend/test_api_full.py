"""
全量 API 端点测试 (94 endpoints)
运行: python test_api_full.py [--base http://localhost:8012]
"""
import sys
import json
import urllib.request
import urllib.error
import time

BASE = "http://localhost:8012/api/v1"
PASS = FAIL = SKIP = 0
RESULTS = []
TOKEN = PTOKEN = ""


def req(method, path, data=None, token=None, expect=None):
    url = f"{BASE}{path}"
    body = json.dumps(data).encode("utf-8") if data else None
    r = urllib.request.Request(url, data=body, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    start = time.time()
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            ms = int((time.time() - start) * 1000)
            return resp.status, json.loads(raw) if raw else {}, ms
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else "{}"
        ms = int((time.time() - start) * 1000)
        return e.code, json.loads(raw) if raw else {}, ms
    except Exception as e:
        ms = int((time.time() - start) * 1000)
        return 0, {"error": str(e)}, ms


def test(label, status, expected=200, note=""):
    global PASS, FAIL
    if status == expected:
        PASS += 1
        RESULTS.append(f"  ✅ {label}")
    else:
        FAIL += 1
        msg = f"  ❌ {label} (HTTP {status}, expected {expected}) {note}"
        print(msg)
        RESULTS.append(msg)


def skip(label, reason=""):
    global SKIP
    SKIP += 1
    RESULTS.append(f"  ⏭ {label} ({reason})")


def run():
    global TOKEN, PTOKEN, BASE
    if "--base" in sys.argv:
        idx = sys.argv.index("--base")
        BASE = sys.argv[idx + 1].rstrip("/") + "/api/v1"

    print("=" * 60)
    print(f"Full API Test — {BASE}")
    print("=" * 60)

    # ===== 1. Health (2) =====
    print("\n── 1. Health ──")
    s, r, ms = req("GET", "/health")
    test("1.1 Service health", s, note=f"{ms}ms")
    s, r, ms = req("GET", "/health/db")
    test("1.2 DB health", s, note=f"{ms}ms")

    # ===== 2. Auth (4) =====
    print("\n── 2. Auth ──")
    s, r, ms = req("POST", "/auth/login", {"username": "admin", "password": "123456", "merchant_id": 11})
    TOKEN = r.get("data", {}).get("access_token", "")
    test("2.1 Merchant login", s, note=f"{ms}ms" if TOKEN else "NO TOKEN")

    s, r, ms = req("POST", "/auth/platform/login", {"username": "super_admin", "password": "123456"})
    PTOKEN = r.get("data", {}).get("access_token", "")
    test("2.2 Platform login", s, note=f"{ms}ms" if PTOKEN else "NO PTOKEN")

    refresh = r.get("data", {}).get("refresh_token", "")
    if not refresh:
        _, rr, _ = req("POST", "/auth/login", {"username": "admin", "password": "123456", "merchant_id": 11})
        refresh = rr.get("data", {}).get("refresh_token", "")
    s, r, ms = req("POST", "/auth/refresh", {"refresh_token": refresh})
    test("2.3 Token refresh", s, note=f"{ms}ms")

    s, _, ms = req("POST", "/auth/logout")
    test("2.4 Logout", s, note=f"{ms}ms")

    if not TOKEN:
        print("⚠️  No merchant token — remaining tests will fail")
        skip("Remaining", "no token")
        print_results()
        return

    # ===== 3. Shops (9) =====
    print("\n── 3. Shops ──")
    s, r, ms = req("GET", "/shops", token=TOKEN)
    shops = r.get("data", [])
    shop_id = shops[0]["id"] if shops else None
    test("3.1 List shops", s, note=f"total={len(shops)} {ms}ms")

    s, r, ms = req("GET", "/shops/scheduler-status", token=TOKEN)
    test("3.2 Scheduler status", s, note=f"{ms}ms")

    s, r, ms = req("GET", "/shops/connectors", token=TOKEN)
    test("3.3 Connectors", s, note=f"{ms}ms")

    if shop_id:
        s, _, ms = req("GET", f"/shops/{shop_id}/status", token=TOKEN)
        test("3.4 Shop status", s, note=f"{ms}ms")

    s, r, ms = req("POST", "/shops", {"platform_type": "mock", "shop_name": "API_Test_Shop"}, token=TOKEN)
    test_shop = r.get("data", {}).get("id")
    test("3.5 Bind shop", s, note=f"id={test_shop} {ms}ms")

    s, _, ms = req("POST", "/shops/trigger-sync", token=TOKEN)
    test("3.6 Trigger sync", s, note=f"{ms}ms")

    if test_shop:
        s, r, ms = req("POST", f"/shops/{test_shop}/bind-token", {}, token=TOKEN)
        test("3.7 Bind token (non-vmall→400)", s, 400, f"{ms}ms")

        s, _, ms = req("POST", f"/shops/{test_shop}/sync", token=TOKEN)
        test("3.8 Sync shop", s, note=f"{ms}ms")

        s, _, ms = req("DELETE", f"/shops/{test_shop}", token=TOKEN)
        test("3.9 Unbind shop", s, note=f"{ms}ms")

    # ===== 4. Products (7) =====
    print("\n── 4. Products ──")
    s, r, ms = req("GET", "/products?page=1&page_size=5", token=TOKEN)
    items = r.get("data", {}).get("items", [])
    pid = items[0]["id"] if items else None
    test("4.1 List products", s, note=f"total={r.get('data',{}).get('total',0)} {ms}ms")

    s, r, ms = req("GET", "/products/search?q=phone", token=TOKEN)
    test("4.2 Semantic search", s, note=f"mode={r.get('data',{}).get('mode','?')} {ms}ms")

    if pid:
        s, _, ms = req("GET", f"/products/{pid}", token=TOKEN)
        test("4.3 Product detail", s, note=f"{ms}ms")

    s, r, ms = req("POST", "/products", {"shop_id": 50, "title": "API_Test_Product", "price": 9.99, "stock": 5}, token=TOKEN)
    new_pid = r.get("data", {}).get("id")
    test("4.4 Create product", s, note=f"id={new_pid} {ms}ms")

    if new_pid:
        s, _, ms = req("PUT", f"/products/{new_pid}", {"price": 19.99}, token=TOKEN)
        test("4.5 Update product", s, note=f"{ms}ms")
        s, _, ms = req("DELETE", f"/products/{new_pid}", token=TOKEN)
        test("4.6 Delete product", s, note=f"{ms}ms")

    s, _, ms = req("POST", f"/products/sync/50", token=TOKEN)
    test("4.7 Sync products", s, note=f"{ms}ms")

    # ===== 5. Orders (5) =====
    print("\n── 5. Orders ──")
    s, r, ms = req("GET", "/orders?page=1&page_size=3", token=TOKEN)
    oid = r["data"]["items"][0]["id"] if r.get("data", {}).get("items") else None
    test("5.1 List orders", s, note=f"total={r.get('data',{}).get('total',0)} {ms}ms")

    if oid:
        s, _, ms = req("GET", f"/orders/{oid}", token=TOKEN)
        test("5.2 Order detail", s, note=f"{ms}ms")

    s, r, ms = req("GET", "/orders/pending-payment", token=TOKEN)
    test("5.3 Pending payment", s, note=f"{ms}ms")

    s, _, ms = req("POST", "/orders/pending-payment/remind", {"shop_id": 50, "limit": 3}, token=TOKEN)
    test("5.4 AI remind", s, note=f"{ms}ms")

    if oid:
        s, _, ms = req("POST", f"/orders/{oid}/refund", {"reason": "test"}, token=TOKEN)
        test("5.5 Refund", s, note=f"{ms}ms")

    # ===== 6. Conversations (5) =====
    print("\n── 6. Conversations ──")
    s, r, ms = req("GET", "/conversations?page=1&page_size=3", token=TOKEN)
    citems = r.get("data", {}).get("items", [])
    cid = citems[0]["id"] if citems else None
    test("6.1 List conversations", s, note=f"total={r.get('data',{}).get('total',0)} {ms}ms")

    if cid:
        s, _, ms = req("GET", f"/conversations/{cid}", token=TOKEN)
        test("6.2 Detail", s, note=f"{ms}ms")
        s, _, ms = req("POST", f"/conversations/{cid}/assign", token=TOKEN)
        test("6.3 Assign", s, note=f"{ms}ms")
        s, _, ms = req("POST", f"/conversations/{cid}/messages", {"content": "API test"}, token=TOKEN)
        test("6.4 Send message", s, note=f"{ms}ms")
        s, _, ms = req("POST", f"/conversations/{cid}/close", token=TOKEN)
        test("6.5 Close", s, note=f"{ms}ms")

    # ===== 7. Tickets (15+) =====
    print("\n── 7. Tickets ──")
    s, r, ms = req("GET", "/tickets?page=1&page_size=3", token=TOKEN)
    test("7.1 List tickets", s, note=f"{ms}ms")

    s, r, ms = req("GET", "/tickets/categories", token=TOKEN)
    test("7.2 Categories", s, note=f"{ms}ms")

    s, r, ms = req("POST", "/tickets/categories", {"name": "API_Test_Cat"}, token=TOKEN)
    cat_id = r.get("data", {}).get("id")
    test("7.3 Create category", s, note=f"{ms}ms")

    s, r, ms = req("POST", "/tickets", {"title": "API_Full_Test", "priority": "P2"}, token=TOKEN)
    tid = r.get("data", {}).get("id")
    test("7.4 Create ticket", s, note=f"{ms}ms")

    s, _, ms = req("POST", "/tickets/auto-classify", {"title": "Test", "description": "desc"}, token=TOKEN)
    test("7.5 Auto-classify (pre)", s, note=f"{ms}ms")

    if tid:
        s, _, ms = req("GET", f"/tickets/{tid}", token=TOKEN)
        test("7.6 Ticket detail", s, note=f"{ms}ms")
        s, _, ms = req("PUT", f"/tickets/{tid}", {"priority": "P1"}, token=TOKEN)
        test("7.7 Update ticket", s, note=f"{ms}ms")
        s, _, ms = req("POST", f"/tickets/{tid}/claim", token=TOKEN)
        test("7.8 Claim", s, note=f"{ms}ms")
        s, _, ms = req("POST", f"/tickets/{tid}/status", {"status": "waiting_customer"}, token=TOKEN)
        test("7.9 Status transition", s, note=f"{ms}ms")
        s, _, ms = req("POST", f"/tickets/{tid}/comments", {"content": "API test comment"}, token=TOKEN)
        test("7.10 Add comment", s, note=f"{ms}ms")
        s, _, ms = req("GET", f"/tickets/{tid}/comments", token=TOKEN)
        test("7.11 List comments", s, note=f"{ms}ms")
        s, _, ms = req("POST", f"/tickets/{tid}/auto-classify", token=TOKEN)
        test("7.12 AI classify", s, note=f"{ms}ms")
        s, _, ms = req("POST", f"/tickets/{tid}/auto-summarize", token=TOKEN)
        test("7.13 AI summarize", s, note=f"{ms}ms")
        s, _, ms = req("POST", f"/tickets/{tid}/ai-suggest", token=TOKEN)
        test("7.14 AI suggest reply", s, note=f"{ms}ms")

    if cat_id:
        s, _, ms = req("PUT", f"/tickets/categories/{cat_id}", {"name": "API_Test_Renamed"}, token=TOKEN)
        test("7.15 Update category", s, note=f"{ms}ms")
        s, _, ms = req("DELETE", f"/tickets/categories/{cat_id}", token=TOKEN)
        test("7.16 Delete category", s, note=f"{ms}ms")

    # ===== 8. AI (8) =====
    print("\n── 8. AI Engine ──")
    s, _, ms = req("POST", "/ai/suggest", {"shop_id": 50, "buyer_question": "when will it ship?"}, token=TOKEN)
    test("8.1 AI suggest", s, note=f"{ms}ms")
    s, _, ms = req("POST", "/ai/campaign/pending-payment", {"shop_id": 50, "limit": 3}, token=TOKEN)
    test("8.2 AI campaign", s, note=f"{ms}ms")
    s, _, ms = req("POST", "/ai/search", {"query": "shipping", "top_k": 3}, token=TOKEN)
    test("8.3 AI search", s, note=f"{ms}ms")
    s, r, ms = req("GET", "/ai/styles", token=TOKEN)
    test("8.4 AI styles", s, note=f"{ms}ms")
    s, r, ms = req("POST", "/ai/styles", {"name": "API_Test_Style", "prompt_template": "You are helpful."}, token=TOKEN)
    style_id = r.get("data", {}).get("id")
    test("8.5 Create style", s, note=f"{ms}ms")
    if style_id:
        s, _, ms = req("PUT", f"/ai/styles/{style_id}", {"name": "API_Test_Updated"}, token=TOKEN)
        test("8.6 Update style", s, note=f"{ms}ms")
        s, _, ms = req("DELETE", f"/ai/styles/{style_id}", token=TOKEN)
        test("8.7 Delete style", s, note=f"{ms}ms")

    # ===== 9. Dashboard (6) =====
    print("\n── 9. Dashboard ──")
    for label, path in [
        ("9.1 Metrics", "/dashboard/metrics"),
        ("9.2 Order trend", "/dashboard/order-trend?range=week"),
        ("9.3 Service stats", "/dashboard/service-stats"),
        ("9.4 Ticket stats", "/dashboard/ticket-stats"),
        ("9.5 Live monitor", "/dashboard/live-monitor"),
        ("9.6 Ticket trend", "/dashboard/ticket-trend?range=week"),
    ]:
        s, _, ms = req("GET", path, token=TOKEN)
        test(label, s, note=f"{ms}ms")

    # ===== 10. Service Mode (5) =====
    print("\n── 10. Service Mode ──")
    s, _, ms = req("GET", "/service-mode/config", token=TOKEN)
    test("10.1 Get config", s, note=f"{ms}ms")
    s, _, ms = req("PUT", "/service-mode/config", {"default_mode": "copilot"}, token=TOKEN)
    test("10.2 Update config", s, note=f"{ms}ms")
    s, _, ms = req("GET", "/service-mode/auto-reply-logs", token=TOKEN)
    test("10.3 Auto-reply logs", s, note=f"{ms}ms")
    s, _, ms = req("GET", "/service-mode/stats", token=TOKEN)
    test("10.4 Stats", s, note=f"{ms}ms")

    # ===== 11. Users (4) =====
    print("\n── 11. Users ──")
    s, r, ms = req("GET", "/users", token=TOKEN)
    test("11.1 List users", s, note=f"{ms}ms")
    s, r, ms = req("POST", "/users", {"username": "api_test_user", "password": "Test123!", "role": "service"}, token=TOKEN)
    uid = r.get("data", {}).get("id")
    test("11.2 Create user", s, note=f"{ms}ms")
    if uid:
        s, _, ms = req("PUT", f"/users/{uid}", {"display_name": "API Tester"}, token=TOKEN)
        test("11.3 Update user", s, note=f"{ms}ms")
        s, _, ms = req("DELETE", f"/users/{uid}", token=TOKEN)
        test("11.4 Delete user", s, note=f"{ms}ms")

    # ===== 12. SLA (4) =====
    print("\n── 12. SLA ──")
    s, r, ms = req("GET", "/sla/policies", token=TOKEN)
    test("12.1 List policies", s, note=f"{ms}ms")
    s, r, ms = req("POST", "/sla/policies", {"name": "API_Test", "priority": "P3", "response_minutes": 30, "resolve_minutes": 240}, token=TOKEN)
    sla_id = r.get("data", {}).get("id")
    test("12.2 Create SLA", s, note=f"{ms}ms")
    if sla_id:
        s, _, ms = req("PUT", f"/sla/policies/{sla_id}", {"resolve_minutes": 480}, token=TOKEN)
        test("12.3 Update SLA", s, note=f"{ms}ms")
        s, _, ms = req("DELETE", f"/sla/policies/{sla_id}", token=TOKEN)
        test("12.4 Delete SLA", s, note=f"{ms}ms")

    # ===== 13. Skill Groups (5) =====
    print("\n── 13. Skill Groups ──")
    s, r, ms = req("GET", "/skill-groups", token=TOKEN)
    test("13.1 List groups", s, note=f"{ms}ms")
    s, r, ms = req("POST", "/skill-groups", {"name": "API_Test_Group"}, token=TOKEN)
    gid = r.get("data", {}).get("id")
    test("13.2 Create group", s, note=f"{ms}ms")
    if gid:
        s, _, ms = req("PUT", f"/skill-groups/{gid}", {"description": "test"}, token=TOKEN)
        test("13.3 Update group", s, note=f"{ms}ms")
        s, _, ms = req("DELETE", f"/skill-groups/{gid}", token=TOKEN)
        test("13.4 Delete group", s, note=f"{ms}ms")
        skip("13.5 Members", "need valid user+group")

    # ===== 14. Categories (4) =====
    print("\n── 14. Categories ──")
    s, _, ms = req("GET", "/categories", token=TOKEN)
    test("14.1 List", s, note=f"{ms}ms")
    s, r, ms = req("POST", "/categories", {"name": "API_Cat"}, token=TOKEN)
    cid2 = r.get("data", {}).get("id")
    test("14.2 Create", s, note=f"{ms}ms")
    if cid2:
        s, _, ms = req("PUT", f"/categories/{cid2}", {"name": "API_Renamed"}, token=TOKEN)
        test("14.3 Update", s, note=f"{ms}ms")
        s, _, ms = req("DELETE", f"/categories/{cid2}", token=TOKEN)
        test("14.4 Delete", s, note=f"{ms}ms")

    # ===== 15. Recommendations (7) =====
    print("\n── 15. Recommendations ──")
    s, _, ms = req("GET", "/recommendations/hot?top_k=5", token=TOKEN)
    test("15.1 Hot products", s, note=f"{ms}ms")
    s, _, ms = req("GET", "/recommendations/rules", token=TOKEN)
    test("15.2 Rules", s, note=f"{ms}ms")
    s, _, ms = req("POST", "/recommendations/similar", {"shop_id": 50, "top_k": 5}, token=TOKEN)
    test("15.3 Similar products", s, note=f"{ms}ms")
    s, r, ms = req("POST", "/recommendations/rules", {"product_id": 1, "recommended_product_id": 2}, token=TOKEN)
    rid = r.get("data", {}).get("id")
    test("15.4 Create rule", s, note=f"{ms}ms")
    if rid:
        s, _, ms = req("PUT", f"/recommendations/rules/{rid}", {"priority": 5}, token=TOKEN)
        test("15.5 Update rule", s, note=f"{ms}ms")
        s, _, ms = req("DELETE", f"/recommendations/rules/{rid}", token=TOKEN)
        test("15.6 Delete rule", s, note=f"{ms}ms")
    s, _, ms = req("POST", "/recommendations/rebuild-co-purchase", token=TOKEN)
    test("15.7 Rebuild", s, note=f"{ms}ms")

    # ===== 16. Knowledge Base (7) =====
    print("\n── 16. Knowledge Base ──")
    s, _, ms = req("GET", "/kb/stats", token=TOKEN)
    test("16.1 KB stats", s, note=f"{ms}ms")
    s, _, ms = req("GET", "/kb/documents", token=TOKEN)
    test("16.2 KB documents", s, note=f"{ms}ms")
    s, _, ms = req("GET", "/kb/conversations", token=TOKEN)
    test("16.3 KB conversations", s, note=f"{ms}ms")
    s, r, ms = req("POST", "/kb/conversations", {"title": "API Test Conv"}, token=TOKEN)
    kcid = r.get("data", {}).get("id")
    test("16.4 Create KB conv", s, note=f"{ms}ms")
    if kcid:
        s, _, ms = req("GET", f"/kb/conversations/{kcid}/messages", token=TOKEN)
        test("16.5 KB messages", s, note=f"{ms}ms")
    s, r, ms = req("POST", "/kb/documents", {"title": "API_Doc", "content": "Test content for KB"}, token=TOKEN)
    kdid = r.get("data", {}).get("id")
    test("16.6 Create document", s, note=f"{ms}ms")
    if kdid:
        s, _, ms = req("DELETE", f"/kb/documents/{kdid}", token=TOKEN)
        test("16.7 Delete document", s, note=f"{ms}ms")

    # ===== 17. Audit + Webhook (3) =====
    print("\n── 17. Audit & Webhook ──")
    s, _, ms = req("GET", "/audit-logs", token=PTOKEN or TOKEN)
    test("17.1 Audit logs", s, note=f"{ms}ms")
    s, _, ms = req("GET", "/webhook-logs", token=PTOKEN or TOKEN)
    test("17.2 Webhook logs", s, note=f"{ms}ms")
    s, _, ms = req("POST", "/webhooks/vmall", {"event": "ORDER_PAID", "data": {"order_no": "T-001"}})
    test("17.3 Webhook receive", s, note=f"{ms}ms")

    print_results()


def print_results():
    total = PASS + FAIL + SKIP
    rate = 100 * PASS // total if total > 0 else 0
    print("\n" + "=" * 60)
    print(f"Results: {PASS} pass, {FAIL} fail, {SKIP} skip ({rate}%)")
    print("=" * 60)
    if FAIL > 0:
        print("\nFailures:")
        for r in RESULTS:
            if "❌" in r:
                print(r)


if __name__ == "__main__":
    run()
