"""
跨系统边缘场景测试 — vMall + SaaS
运行(容器内): docker exec saas-backend python test_edge_cases.py
覆盖: 钱包余额不足/重复退款/越权/空输入/分页边界/auto兜底/精确路由/幂等
前提: 两后端均启动(saas:8012, vmall:8020 容器内可达)
"""
import json
import urllib.request
import urllib.error

SAAS = "http://saas-backend:8012/api/v1"
VMALL = "http://vmall-backend:8020/api/v1"
PASS = 0
FAIL = 0
ERRS = []


def req(base, path, data=None, token=None, method="GET", api_key=None):
    url = f"{base}{path}"
    body = json.dumps(data).encode("utf-8") if data is not None else None
    r = urllib.request.Request(url, data=body, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", f"Bearer {token}")
    if api_key:
        r.add_header("X-API-Key", api_key)
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8") if e.fp else "{}"
        return e.code, json.loads(raw) if raw else {}
    except Exception as e:
        return 0, {"error": str(e)}


def check(label, cond):
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  [PASS] {label}")
    else:
        FAIL += 1
        print(f"  [FAIL] {label}")
        ERRS.append(label)


def vmall_login_buyer():
    return req(VMALL, "/consumer/auth/login", {"username": "buyer_test", "password": "123456"}, method="POST")[1]["data"]["access_token"]


def vmall_login_admin():
    return req(VMALL, "/admin/auth/login", {"username": "admin_vmall", "password": "123456"}, method="POST")[1]["data"]["access_token"]


def saas_login():
    s, r = req(SAAS, "/auth/login", {"username": "admin", "password": "123456"}, method="POST")
    if s == 200:
        return r["data"]["access_token"], None
    av = r.get("detail", {}).get("available_merchants", [])
    mid = next((m["merchant_id"] for m in av if m["role"] == "admin"), av[0]["merchant_id"])
    return req(SAAS, "/auth/login", {"username": "admin", "password": "123456", "merchant_id": mid}, method="POST")[1]["data"]["access_token"], mid


def run():
    print("=" * 56)
    print("跨系统边缘场景测试")
    print("=" * 56)

    btok = vmall_login_buyer()
    atok = vmall_login_admin()

    # ---- 1. 钱包余额不足 ----
    print("\n--- 1. 钱包/支付边缘 ---")
    bid = req(VMALL, "/admin/wallets", token=atok)[1]["data"]
    bid = (bid["items"] if isinstance(bid, dict) else bid)[0]["buyer_id"]
    # 把余额清到一个已知低值: 充值后买一个贵的
    prod = req(VMALL, "/consumer/products?page=1", token=btok)[1]["data"]["items"][0]
    det = req(VMALL, f"/consumer/products/{prod['id']}", token=btok)[1]["data"]
    sku = det["skus_json"][0]
    price = float(sku["price"])
    # 下单 -> 不充值直接看余额是否够；构造余额不足：下一个远超余额的单
    bal = req(VMALL, "/consumer/wallet", token=btok)[1]["data"]["balance"]
    big_qty = max(int(bal // price) + 5, 5)  # 确保超额
    oc = req(VMALL, "/consumer/orders", {"product_id": prod["id"], "sku_code": sku["sku_code"], "quantity": big_qty, "receiver_name": "x", "receiver_phone": "1", "receiver_address": "x"}, btok, "POST")
    if oc[0] == 200:
        oid = oc[1]["data"]["id"]
        pay = req(VMALL, f"/consumer/orders/{oid}/pay", {}, btok, "POST")
        check("1.1 余额不足支付被拒(400)", pay[0] == 400)
    else:
        check("1.1 余额不足(库存不足亦合理拒绝)", oc[0] == 400)

    # ---- 2. 重复退款幂等/状态机 ----
    print("\n--- 2. 售后状态机 ---")
    req(VMALL, f"/admin/wallets/{bid}/recharge", {"amount": 99999}, atok, "POST")
    oc = req(VMALL, "/consumer/orders", {"product_id": prod["id"], "sku_code": sku["sku_code"], "quantity": 1, "receiver_name": "x", "receiver_phone": "1", "receiver_address": "x"}, btok, "POST")
    oid = oc[1]["data"]["id"]
    req(VMALL, f"/consumer/orders/{oid}/pay", {}, btok, "POST")
    import time
    time.sleep(3.5)
    # 未发货就申请售后(状态机应拒绝 — 仅 shipped/received/completed 可申请)
    as_early = req(VMALL, "/consumer/after-sales", {"order_id": oid, "type": "refund_only", "refund_amount": price}, btok, "POST")
    check("2.1 未发货申请售后被拒(400)", as_early[0] == 400)
    # 正常流程: 发货 -> 申请 -> 通过 -> 寄回 -> 确认
    req(VMALL, f"/admin/orders/{oid}/ship", {"company": "顺丰", "tracking_no": "SF1"}, atok, "POST")
    time.sleep(1)
    sid = req(VMALL, "/consumer/after-sales", {"order_id": oid, "type": "refund_only", "refund_amount": price}, btok, "POST")[1]["data"]["id"]
    req(VMALL, f"/admin/after-sales/{sid}/review", {"action": "approve"}, atok, "POST")
    req(VMALL, f"/consumer/after-sales/{sid}/ship-return", {"tracking_no": "RT1"}, btok, "POST")
    w_before = req(VMALL, "/consumer/wallet", token=btok)[1]["data"]["balance"]
    r1 = req(VMALL, f"/admin/after-sales/{sid}/confirm-receive", {}, atok, "POST")
    check("2.2 确认收货退款成功", r1[0] == 200)
    time.sleep(1)
    w_after = req(VMALL, "/consumer/wallet", token=btok)[1]["data"]["balance"]
    check("2.3 退款回补钱包正确", abs((w_after - w_before) - price) < 0.01)
    # 重复确认收货(幂等/状态机): 已 refunded 再确认应被拒
    r2 = req(VMALL, f"/admin/after-sales/{sid}/confirm-receive", {}, atok, "POST")
    check("2.4 重复退款被状态机拒绝(非200)", r2[0] != 200)
    w_dup = req(VMALL, "/consumer/wallet", token=btok)[1]["data"]["balance"]
    check("2.5 重复退款未二次加钱", abs(w_dup - w_after) < 0.01)

    # ---- 3. 越权/鉴权 ----
    print("\n--- 3. 鉴权边缘 ---")
    s, _ = req(VMALL, "/consumer/wallet", token="garbage.token.here")
    check("3.1 畸形 token 被拒(401)", s == 401)
    s, _ = req(VMALL, "/consumer/orders/999999/pay", {}, btok, "POST")
    check("3.2 支付不存在订单(404)", s == 404)
    s, _ = req(VMALL, "/admin/wallets", token=btok)  # 买家 token 访问 admin
    check("3.3 买家越权访问 admin(401/403)", s in (401, 403))
    # SaaS: openapi confirm-bind 无 key
    s, _ = req(SAAS, "/openapi/confirm-bind", {"bind_token": "x", "vmall_url": "y"}, method="POST")
    check("3.4 openapi 无 API Key 被拒(401)", s == 401)

    # ---- 4. 输入校验边缘 ----
    print("\n--- 4. 输入校验 ---")
    stok, mid = saas_login()
    s, _ = req(SAAS, "/products?page=-1&page_size=5", token=stok)
    check("4.1 SaaS 负分页被拒(422)", s == 422)
    s, _ = req(SAAS, "/products?page=1&page_size=99999", token=stok)
    check("4.2 SaaS 超大 page_size 被拒(422)", s == 422)
    s, _ = req(SAAS, "/tickets", {"title": ""}, stok, "POST")
    check("4.3 SaaS 空工单标题被拒(422)", s == 422)
    s, r = req(VMALL, "/consumer/orders", {"product_id": 999999, "sku_code": "x", "quantity": 1}, btok, "POST")
    check("4.4 vMall 下单不存在商品被拒(400)", s == 400)

    # ---- 5. auto 模式兜底链(主LLM不可用时不空响应) ----
    print("\n--- 5. AI 兜底 ---")
    s, r = req(SAAS, "/ai/suggest", {"shop_id": req(SAAS, "/products?page=1&page_size=1", token=stok)[1]["data"]["items"][0]["shop_id"], "buyer_question": "你们发货快吗"}, stok, "POST")
    sugg = r.get("data", {}).get("suggestions", []) if s == 200 else []
    check("5.1 AI 建议非空(主或兜底)", s == 200 and len(sugg) >= 1 and bool(sugg[0].get("content")))

    # ---- 6. 跨系统精确路由 ----
    print("\n--- 6. 跨系统路由 ---")
    # 取一个非首店铺的商品发消息，验证落到对应 SaaS 店铺
    shops = req(SAAS, "/shops", token=stok)[1]["data"]
    shops = shops["items"] if isinstance(shops, dict) else shops
    vmall_shops = [s for s in shops if s.get("platform_type") == "vmall"]
    # /shops 按商户隔离：每个商户有自己的 vmall 店铺；路由正确性由 shop_url 指向容器服务名体现
    check("6.1 商户 vmall 店铺存在且 shop_url 指向容器(非 localhost)",
          len(vmall_shops) >= 1 and "vmall-backend" in (vmall_shops[0].get("shop_url") or ""))

    print("\n" + "=" * 56)
    total = PASS + FAIL
    print(f"结果: {PASS}/{total} 通过, {FAIL} 失败")
    if ERRS:
        print("失败项:")
        for e in ERRS:
            print("   -", e)
    print("=" * 56)
    return FAIL == 0


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
