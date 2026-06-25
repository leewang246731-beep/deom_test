"""Full system check script"""
import requests, time

B = "http://127.0.0.1:8020/api/v1"
S = "http://127.0.0.1:8010/api/v1"
errs = []


def ck(n, c, d=""):
    if not c:
        errs.append(f"{n} {d}")
        print(f"  FAIL {n} {d}")
    else:
        print(f"  OK   {n}")


print("=== vMall Consumer ===")
r = requests.post(B + "/consumer/auth/login", json={"username": "buyer_test", "password": "123456"})
ck("login", r.status_code == 200)
hc = {"Authorization": "Bearer " + r.json()["data"]["access_token"]}

r = requests.get(B + "/consumer/profile", headers=hc)
ck("profile", r.status_code == 200 and r.json()["data"]["wallet"]["balance"] > 0,
   str(r.json()["data"]["wallet"]["balance"]))

r = requests.get(B + "/consumer/products?page=1", headers=hc)
ck("products", r.json()["data"]["total"] > 0)
pid = r.json()["data"]["items"][0]["id"]

r = requests.get(B + f"/consumer/products/{pid}", headers=hc)
ck("detail", len(r.json()["data"]["skus_json"]) > 0)
sku = r.json()["data"]["skus_json"][0]

r = requests.post(B + "/consumer/orders", headers=hc, json={
    "product_id": pid, "sku_code": sku["sku_code"], "quantity": 1,
    "receiver_name": "T", "receiver_phone": "1", "receiver_address": "N"})
ck("order", r.status_code == 200)
oid = r.json()["data"]["id"]

r = requests.post(B + f"/consumer/orders/{oid}/pay", headers=hc)
ck("pay", r.status_code == 200)
time.sleep(3)

r = requests.get(B + f"/consumer/orders/{oid}", headers=hc)
ck("paid", r.json()["data"]["status"] == "paid")

r = requests.post(B + "/consumer/conversations", headers=hc, json={"product_id": pid})
ck("conv", r.status_code == 200)
cid = r.json()["data"]["id"]

r = requests.post(B + f"/consumer/conversations/{cid}/messages", headers=hc,
                  json={"msg_type": "text", "content": {"text": "hello"}})
ck("msg", r.status_code == 200)

r = requests.get(B + "/consumer/wallet/transactions?page=1", headers=hc)
ck("tx", r.status_code == 200)

r = requests.put(B + "/consumer/profile", headers=hc, json={"nickname": "NewName"})
ck("update_profile", r.status_code == 200)

print("\n=== vMall Admin ===")
r = requests.post(B + "/admin/auth/login", json={"username": "admin_vmall", "password": "123456"})
ha = {"Authorization": "Bearer " + r.json()["data"]["access_token"], "Content-Type": "application/json"}

r = requests.get(B + "/admin/dashboard", headers=ha)
ck("dash", r.status_code == 200)

r = requests.get(B + "/admin/orders?page=1", headers=ha)
ck("orders", r.json()["data"]["total"] > 0)

r = requests.post(B + f"/admin/logistics/{oid}/ship", headers=ha,
                  json={"company": "SF", "tracking_no": "T1"})
ck("ship", r.status_code == 200)
lid = r.json()["data"]["id"]

r = requests.post(B + f"/admin/logistics/{lid}/advance", headers=ha)
ck("advance", r.status_code == 200)

r = requests.get(B + f"/admin/logistics/{oid}", headers=ha)
ck("logistics", len(r.json()["data"]["tracks"]) > 0)

r = requests.get(B + "/admin/conversations?page=1", headers=ha)
ck("convs", r.json()["data"]["total"] > 0)

r = requests.post(B + f"/admin/conversations/{cid}/messages", headers=ha,
                  json={"content": {"text": "reply"}})
ck("reply", r.status_code == 200)

r = requests.get(B + "/admin/wallets", headers=ha)
ck("wallets", r.json()["data"]["total"] > 0)
real_buyer_id = r.json()["data"]["items"][0]["buyer_id"]

r = requests.post(B + f"/admin/wallets/{real_buyer_id}/recharge", headers=ha, json={"amount": 10, "remark": "check"})
ck("recharge", r.status_code == 200 and r.json()["data"]["balance"] > 0)

r = requests.get(B + "/admin/settings", headers=ha)
ck("settings", r.status_code == 200)

r = requests.get(B + "/admin/after-sales?page=1", headers=ha)
ck("aftersales", r.status_code == 200)

print("\n=== OpenAPI ===")
r = requests.post("http://127.0.0.1:8020/openapi/auth", json={"merchant_id": 1, "shop_id": 1})
hv = {"Authorization": "Bearer " + r.json()["data"]["access_token"]}
r = requests.get("http://127.0.0.1:8020/openapi/products?page=1", headers=hv)
ck("oa-prods", r.json()["data"]["total"] > 0)
r = requests.get("http://127.0.0.1:8020/openapi/orders?page=1", headers=hv)
ck("oa-orders", r.json()["data"]["total"] > 0)

print("\n=== SaaS ===")
r = requests.post(S + "/auth/login", json={"username": "admin", "password": "123456"})
hs = {"Authorization": "Bearer " + r.json()["data"]["access_token"], "Content-Type": "application/json"}
r = requests.get(S + "/dashboard/metrics", headers=hs)
ck("saas-dash", r.status_code == 200)
r = requests.get(S + "/products?page=1", headers=hs)
ck("saas-prods", r.json()["data"]["total"] > 0)
r = requests.get(S + "/orders?page=1", headers=hs)
ck("saas-orders", r.json()["data"]["total"] > 0)
r = requests.get(S + "/conversations?page=1", headers=hs)
ck("saas-convs", r.status_code == 200)
r = requests.get(S + "/tickets?page=1", headers=hs)
ck("saas-tickets", r.status_code == 200)
r = requests.post(S + "/ai/suggest", headers=hs, json={"shop_id": 1, "buyer_question": "test"})
ck("saas-ai", r.status_code == 200)
r = requests.post(S + "/webhooks/vmall", json={"event": "T", "data": {}}, headers=hs)
ck("saas-webhook", r.status_code == 200)

print(f"\n=== {len(errs)} ERRORS ===")
for e in errs:
    print("  " + e)
if not errs:
    print("  ALL 35 CHECKS PASSED")
