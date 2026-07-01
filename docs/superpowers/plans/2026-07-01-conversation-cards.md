# 会话卡片 + 订单同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让客服会话支持商品卡片、订单卡片的双向收发与渲染，并补全 vmall→SaaS 订单实时同步，从而可验证售前/售中/售后客服话术。

**Architecture:** 用统一的 card 信封 JSON（`{text, card}`）承载结构化消息，复用现有 `messages_json` / `VmMessage.content_json` 字段（无迁移）。卡片构造与 vmall 商品 ID 还原抽成纯函数模块便于单测。四个方向（客服→买家商品卡/订单卡、买家→客服带单咨询、双方渲染）分别接入现有会话桥接链路。订单同步复用已有 webhook 事件，仅补 `buyer_nick`。

**Tech Stack:** FastAPI（两个后端）、SQLAlchemy、Vue 3 + Element Plus（两个前端）、unittest（现有测试框架，非 pytest）。

## Global Constraints

- card 信封格式固定：`{"text": <降级文本 str>, "card": {"type": "product"|"order", ...}}`。
- 商品卡片 `card.product_id` 必须是 **vmall 商品 ID**（从 `ExternalProduct.platform_product_id` 的 `"vm_<id>"` 还原），跳转路由 `/product/<id>`。
- 订单卡片 `card.link` 固定 `/orders`（消费者端无订单详情路由）。
- 所有卡片消息必带 `text` 降级字段；渲染层 `if (card) 卡片 else 文本`，向后兼容老消息。
- 内部服务调用 api_key 固定 `"vmall-internal-demo-key"`。
- 测试框架用 `unittest`（`python -m unittest`），不引入 pytest。
- Docker Desktop 当前停止；纯函数单测可离线跑，涉及 DB/HTTP 的 E2E 验证需先重启 Docker 并 `docker-compose --profile full up -d --build`。

---

### Task 1: vmall 商品 ID 还原纯函数

**Files:**
- Create: `backend/app/services/card_builder.py`
- Test: `backend/tests/test_card_builder.py`

**Interfaces:**
- Produces: `restore_vm_product_id(platform_product_id: str | None) -> int | None`

> 说明：卡片的 JSON 信封在前端（Vue）构造，后端只做「透传存储」+「商品 ID 还原」。因此本模块只需一个纯函数把 `ExternalProduct.platform_product_id`（`"vm_785"`）还原成 vmall 商品 ID（785），供 `conversation_detail` 给前端提供正确的跳转 ID。不构造整卡（YAGNI）。

- [ ] **Step 1: Write the failing test**

Create `backend/tests/test_card_builder.py`:

```python
"""card_builder 纯函数单测（无 DB / 无 Docker 依赖）。"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.card_builder import restore_vm_product_id


class TestRestoreVmProductId(unittest.TestCase):
    def test_valid_prefix(self):
        self.assertEqual(restore_vm_product_id("vm_785"), 785)

    def test_none(self):
        self.assertIsNone(restore_vm_product_id(None))

    def test_empty(self):
        self.assertIsNone(restore_vm_product_id(""))

    def test_no_prefix(self):
        self.assertIsNone(restore_vm_product_id("785"))

    def test_non_numeric_tail(self):
        self.assertIsNone(restore_vm_product_id("vm_abc"))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && python -m unittest tests.test_card_builder -v`
Expected: FAIL / ERROR — `ModuleNotFoundError: No module named 'app.services.card_builder'`

- [ ] **Step 3: Write minimal implementation**

Create `backend/app/services/card_builder.py`:

```python
"""vmall 商品 ID 还原（纯函数，无副作用）。"""


def restore_vm_product_id(platform_product_id: str | None) -> int | None:
    """从 'vm_785' 还原 vmall 商品 ID 785。非 'vm_' 前缀或非数字尾部返回 None。"""
    if not platform_product_id or not platform_product_id.startswith("vm_"):
        return None
    tail = platform_product_id[len("vm_"):]
    return int(tail) if tail.isdigit() else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && python -m unittest tests.test_card_builder -v`
Expected: PASS（5 个用例全绿）

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/card_builder.py backend/tests/test_card_builder.py
git commit -m "feat: restore_vm_product_id 纯函数（SaaS→vmall 商品 ID 还原）"
```

---

### Task 2: vmall 订单同步补 buyer_nick

**Files:**
- Modify: `vmall_system/backend/app/api/consumer/orders.py:111-124`（`_order_json` 函数）
- Test: `vmall_system/backend/test_order_json.py`（新建，unittest + mock）

**Interfaces:**
- Modifies: `_order_json(order, items, db)` 返回 dict 增加 `"buyer_nick"` 键。

- [ ] **Step 1: Write the failing test**

Create `vmall_system/backend/test_order_json.py`:

```python
"""_order_json 补 buyer_nick 单测（mock DB，无 Docker）。"""
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(__file__))

from app.api.consumer.orders import _order_json


class TestOrderJsonBuyerNick(unittest.TestCase):
    def _fake_order(self):
        o = MagicMock()
        o.id = 1
        o.order_no = "VM-1"
        o.buyer_id = 42
        o.total_amount = 100
        o.pay_amount = 100
        o.discount_amount = 0
        o.status = "paid"
        o.after_sale_status = None
        o.receiver_name = "小明"
        o.receiver_phone = "138"
        o.receiver_address = "南京"
        o.pay_time = None
        o.ship_time = None
        o.created_at = None
        return o

    def test_includes_buyer_nick(self):
        buyer = MagicMock()
        buyer.nickname = "测试买家小明"
        db = MagicMock()
        db.query.return_value.get.return_value = buyer  # VmBuyer 查询
        result = _order_json(self._fake_order(), [], db)
        self.assertEqual(result["buyer_nick"], "测试买家小明")

    def test_buyer_missing_fallback(self):
        db = MagicMock()
        db.query.return_value.get.return_value = None
        result = _order_json(self._fake_order(), [], db)
        self.assertEqual(result["buyer_nick"], "")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd vmall_system/backend && python -m unittest test_order_json -v`
Expected: FAIL — `KeyError: 'buyer_nick'`（当前 `_order_json` 无此键）

- [ ] **Step 3: Write minimal implementation**

In `vmall_system/backend/app/api/consumer/orders.py`, add import near top (after line 11 `from app.models.vm_order import VmOrder`):

```python
from app.models.vm_buyer import VmBuyer
```

Modify `_order_json` (line 111) — insert buyer lookup and add key:

```python
def _order_json(order: VmOrder, items: list, db: Session) -> dict:
    sku_details = [{"title": "", "sku_code": i.sku_code, "sku_spec": i.sku_spec,
                     "unit_price": float(i.unit_price), "quantity": i.quantity, "product_id": i.product_id}
                    for i in items]
    buyer = db.query(VmBuyer).get(order.buyer_id)
    return {"id": order.id, "order_no": order.order_no, "buyer_id": order.buyer_id,
            "buyer_nick": buyer.nickname if buyer else "",
            "total_amount": float(order.total_amount), "pay_amount": float(order.pay_amount),
            "discount_amount": float(order.discount_amount or 0),
            "status": order.status, "after_sale_status": order.after_sale_status,
            "receiver_name": order.receiver_name, "receiver_phone": order.receiver_phone,
            "receiver_address": order.receiver_address,
            "pay_time": order.pay_time.isoformat() if order.pay_time else None,
            "ship_time": order.ship_time.isoformat() if order.ship_time else None,
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "sku_details": sku_details}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd vmall_system/backend && python -m unittest test_order_json -v`
Expected: PASS（2 用例绿）

- [ ] **Step 5: Commit**

```bash
git add vmall_system/backend/app/api/consumer/orders.py vmall_system/backend/test_order_json.py
git commit -m "fix: ORDER_PAID payload 补 buyer_nick，使客服端能匹配会话买家订单"
```

---

### Task 3: SaaS 后端 — 发送带卡片 + webhook 存卡片 + 买家订单接口

**Files:**
- Modify: `backend/app/schemas/__init__.py:291-293`（`ConversationMessageSend` 加 `card`）
- Modify: `backend/app/api/v1/conversations.py`（`send_conversation_message` 处理 card；新增 `buyer_orders` 接口）
- Modify: `backend/app/api/v1/webhooks.py`（`_handle_message` 存 card）

**Interfaces:**
- Consumes: `card_builder.restore_vm_product_id`（Task 1）
- Produces:
  - `POST /conversations/{id}/messages` body 支持 `card: dict | None`
  - `GET /conversations/{id}/buyer-orders` → `{code,msg,data:[{order_no,status,amount,created_at}]}`
  - `conversation_detail` 的 `product` 增加 `vm_product_id`（供前端构造正确的 `/product/<vmId>` 链接）

- [ ] **Step 0: conversation_detail 补 vm_product_id**

In `backend/app/api/v1/conversations.py`, add import at top:

```python
from app.services.card_builder import restore_vm_product_id
```

Modify `conversation_detail` 的 product_info 构造（line 134-138）:

```python
    product_info = None
    if c.product_id:
        ep = db.query(ExternalProduct).filter(ExternalProduct.id == c.product_id).first()
        if ep:
            product_info = {
                "id": ep.id,
                "vm_product_id": restore_vm_product_id(ep.platform_product_id),
                "title": ep.title, "price": float(ep.price), "stock": ep.stock,
                "image": (ep.images_json or [None])[0] if ep.images_json else None,
            }
```

- [ ] **Step 1: Extend schema**

In `backend/app/schemas/__init__.py`, modify `ConversationMessageSend` (line 291):

```python
class ConversationMessageSend(BaseModel):
    content: str
    msg_type: Optional[str] = "text"
    card: Optional[dict] = None
```

- [ ] **Step 2: send_conversation_message 处理 card**

In `backend/app/api/v1/conversations.py`, modify `send_conversation_message` (line 163). Replace the message-append block (lines 173-181) and the vmall forward `json=` payload (line 200) so card is stored and forwarded:

```python
    content = body.content
    now = datetime.now()
    msgs = list(c.messages_json or [])
    msg_entry = {"role": "service", "content": content, "time": now.strftime("%Y-%m-%d %H:%M:%S")}
    if body.card:
        msg_entry["card"] = body.card
    msgs.append(msg_entry)
    c.messages_json = msgs
    c.last_message_at = now
    c.handled_status = "replied"
    c.last_human_at = now
    db.commit()
```

And update the forward payload (line 198-202) to include card:

```python
            import requests as _r
            _fwd = {"api_key": "vmall-internal-demo-key", "content": content, "msg_type": "text"}
            if body.card:
                _fwd["card"] = body.card
                _fwd["msg_type"] = body.card.get("type", "text") + "_card"
            _r.post(target, json=_fwd, timeout=5)
```

And update the return (line 205) so cards echo back to the SaaS UI:

```python
    return ok({"id": c.id, "messages_json": [
        {"role": m["role"], "content": m["content"], "time": m.get("time", ""), "card": m.get("card")}
        for m in msgs
    ]})
```

- [ ] **Step 3: Add buyer_orders endpoint**

In `backend/app/api/v1/conversations.py`, add import at top (after line with `from app.models.external_product import ExternalProduct`):

```python
from app.models.external_order import ExternalOrder
```

Add new endpoint after `conversation_detail` (after line 147):

```python
@router.get("/conversations/{conv_id}/buyer-orders")
def buyer_orders(conv_id: int, current: CurrentUser = Depends(get_current_user),
                 mid: int = Depends(get_effective_merchant_id), db: Session = Depends(get_db)):
    """返回会话买家的订单（按 buyer_nick 尽力匹配；匹配不到降级为店铺近期订单）。"""
    shop_ids = _merchant_shop_ids(db, mid)
    c = db.query(Conversation).filter(
        Conversation.id == conv_id,
        Conversation.shop_id.in_(shop_ids) if shop_ids else True,
    ).first()
    if not c:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "会话不存在"})
    q = db.query(ExternalOrder).filter(ExternalOrder.shop_id == c.shop_id)
    matched = q.filter(ExternalOrder.buyer_nick == c.buyer_nick).order_by(
        ExternalOrder.created_at.desc()).limit(10).all() if c.buyer_nick else []
    if not matched:
        matched = q.order_by(ExternalOrder.created_at.desc()).limit(10).all()
    return ok([
        {"order_no": o.platform_order_id, "status": o.status,
         "amount": float(o.pay_amount or 0),
         "created_at": o.created_at.isoformat() if o.created_at else None}
        for o in matched
    ])
```

- [ ] **Step 4: webhook _handle_message 存 card**

In `backend/app/api/v1/webhooks.py`, modify the message-append in `_handle_message` (around line 224-228). Replace with:

```python
    msg_entry = {
        "role": data.get("sender_role", "buyer"),
        "content": text,
        "time": data.get("created_at") or datetime.now().isoformat(),
    }
    if data.get("card"):
        msg_entry["card"] = data["card"]
    msgs.append(msg_entry)
```

- [ ] **Step 5: Verify (requires Docker up)**

Restart Docker Desktop, then:

```bash
docker-compose --profile full up -d --build saas-backend
```

Test buyer-orders endpoint (replace TOKEN/convid with real values from a logged-in CS session):

```bash
curl -s "http://localhost:8012/api/v1/conversations/1/buyer-orders" \
  -H "Authorization: Bearer <SERVICE_TOKEN>" -H "X-Merchant-Id: 10"
```
Expected: `{"code":200,...,"data":[{"order_no":"VM-...","status":"...","amount":...}]}` 或空数组（无订单时）。

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/__init__.py backend/app/api/v1/conversations.py backend/app/api/v1/webhooks.py
git commit -m "feat: SaaS 会话支持卡片消息收发 + 买家订单查询接口"
```

---

### Task 4: vmall 后端 — 接收/发送卡片消息

**Files:**
- Modify: `vmall_system/backend/app/api/consumer/conversations.py`（`receive_saas_reply` 存 card；`send_message` 带 card 到 webhook）

**Interfaces:**
- Consumes: webhook `NEW_MESSAGE` data 里的 `card`（由 vmall→SaaS 方向消费，见 Task 3 Step 4）
- Produces: `receive_saas_reply` 与 `send_message` 支持 card 透传

- [ ] **Step 1: receive_saas_reply 存 card**

In `vmall_system/backend/app/api/consumer/conversations.py`, modify `receive_saas_reply` (line 53-67). Replace the `VmMessage(...)` construction (lines 61-63):

```python
    content_json = {"text": body.get("content", "")}
    if body.get("card"):
        content_json["card"] = body["card"]
    msg = VmMessage(conversation_id=conv_id, sender_role="admin",
                    msg_type=body.get("msg_type", "text"),
                    content_json=content_json)
```

- [ ] **Step 2: send_message 带 card 到 webhook**

In the same file, modify `send_message` (line 70-96). The buyer sends `content` as `{text, card?}`. Update the webhook dispatch payload (line 84-95) to forward card:

```python
    _content = body.get("content", {"text": body.get("text", "")})
    dispatch_sync(db, "NEW_MESSAGE", {
        "conversation_id": conv_id, "sender_role": "buyer",
        "content": _content,
        "card": _content.get("card") if isinstance(_content, dict) else None,
        "msg_type": body.get("msg_type", "text"),
        "buyer_nick": buyer.nickname if buyer else f"买家{buyer_id}",
        "buyer_id": buyer_id,
        "product_id": c.product_id,
        "merchant_id": c.merchant_id,
        "saas_shop_id": mi.get("saas_shop_id"),
        "_merchant_id": c.merchant_id,
        "created_at": msg.created_at.isoformat() if msg.created_at else None,
    })
```

> Note: `_handle_message` (Task 3 Step 4) reads `data["card"]`; the buyer's message `content_json` already stored the card via the existing `content_json=body.get("content", ...)` at line 79 — no change needed there since `content` already carries `{text, card}`.

- [ ] **Step 3: Verify (requires Docker up)**

```bash
docker-compose --profile full up -d --build vmall-backend
```

Send a buyer card message (replace token/convid):

```bash
curl -s -X POST "http://localhost:8020/api/v1/consumer/conversations/1/messages" \
  -H "Authorization: Bearer <BUYER_TOKEN>" -H "Content-Type: application/json" \
  -d '{"msg_type":"product_card","content":{"text":"咨询这个","card":{"type":"product","product_id":785,"title":"乳胶床垫1.8m","price":1599,"link":"/product/785"}}}'
```
Expected: `{"code":200,...,"data":{"id":<n>}}`. 然后在 SaaS 工作台该会话应能看到带 card 的消息（DB `messages_json` 最后一条含 `card`）。

- [ ] **Step 4: Commit**

```bash
git add vmall_system/backend/app/api/consumer/conversations.py
git commit -m "feat: vmall 会话收发卡片消息（internal 接收 + webhook 透传）"
```

---

### Task 5: vmall Chat.vue — 卡片渲染 + 咨询此商品 + 关联订单

**Files:**
- Modify: `vmall_system/frontend_consumer/src/views/Chat.vue`
- Modify: `vmall_system/frontend_consumer/src/api/index.js`（加 getMyOrders 若聊天页未引入）

**Interfaces:**
- Consumes: 会话详情 `product`（已存在，Task 前置已加）、`GET /consumer/orders`（`getMyOrders`）
- Produces: 买家可发 product_card / order_card；渲染 admin 发来的卡片

- [ ] **Step 1: 渲染卡片消息 + 操作按钮**

Replace the message list rendering block and add action buttons in `vmall_system/frontend_consumer/src/views/Chat.vue`. Replace the `<div ref="chatBox">...</div>` message loop (the `v-for="m in msgs"` block) with card-aware rendering:

```vue
      <div ref="chatBox" style="height:400px;overflow-y:auto;margin-bottom:12px">
        <div v-for="m in msgs" :key="m.id" :style="{textAlign:m.sender_role==='buyer'?'right':'left',marginBottom:'8px'}">
          <!-- 卡片消息 -->
          <div v-if="m.content_json?.card" :style="{display:'inline-block',maxWidth:'75%'}">
            <el-card shadow="hover" style="cursor:pointer;text-align:left" body-style="padding:8px" @click="openCard(m.content_json.card)">
              <div v-if="m.content_json.card.type==='product'" style="display:flex;gap:8px;align-items:center">
                <el-image v-if="m.content_json.card.image" :src="m.content_json.card.image" fit="cover" style="width:48px;height:48px;border-radius:6px" />
                <div>
                  <div style="font-size:13px;font-weight:bold">{{ m.content_json.card.title }}</div>
                  <div style="color:#e6a23c;font-weight:bold">¥{{ m.content_json.card.price }}</div>
                </div>
              </div>
              <div v-else style="font-size:13px">
                <div style="font-weight:bold">📦 订单 {{ m.content_json.card.order_no }}</div>
                <div style="color:#909399">状态: {{ m.content_json.card.status }} · ¥{{ m.content_json.card.amount }}</div>
              </div>
              <div style="font-size:11px;color:#409eff;margin-top:4px">点击查看 ›</div>
            </el-card>
          </div>
          <!-- 文本消息 -->
          <div v-else :style="{display:'inline-block',maxWidth:'70%',padding:'8px 12px',borderRadius:'8px',background:m.sender_role==='buyer'?'#409eff':'#f0f0f0',color:m.sender_role==='buyer'?'#fff':'#303133'}">
            <div style="font-size:11px;margin-bottom:2px;opacity:0.7">{{ m.sender_role === 'buyer' ? '我' : '客服' }}</div>
            {{m.content_json?.text||fmtContent(m.content_json)}}</div>
        </div>
        <div v-if="!msgs.length" style="text-align:center;color:#909399;padding:60px 0">暂无消息，开始咨询吧</div>
      </div>
```

Add action buttons under the product card (in the `<el-card v-if="product">` block, after the existing content), plus an order-picker button. Insert before the chat `<el-card>`:

```vue
    <div v-if="product || myOrders.length" style="display:flex;gap:8px;margin-bottom:8px">
      <el-button v-if="product" size="small" type="primary" plain @click="askAboutProduct">咨询此商品</el-button>
      <el-button size="small" plain @click="orderPickerVisible=true">关联我的订单</el-button>
    </div>

    <el-dialog v-model="orderPickerVisible" title="选择要咨询的订单" width="90%">
      <div v-for="o in myOrders" :key="o.id" style="padding:8px;border-bottom:1px solid #eee;cursor:pointer" @click="askAboutOrder(o)">
        <div style="font-weight:bold">{{ o.order_no }}</div>
        <div style="color:#909399;font-size:12px">状态: {{ o.status }} · ¥{{ o.pay_amount }}</div>
      </div>
      <el-empty v-if="!myOrders.length" description="暂无订单" />
    </el-dialog>
```

- [ ] **Step 2: Script — 加载订单、发送卡片、打开卡片**

In the `<script setup>`, add `getMyOrders` to the import from `../api`, and add state + methods:

```javascript
import { getMsgs, sendMsg, createConv, getMyOrders } from '../api'
```

Add refs (near `const product=ref(null)`):

```javascript
const myOrders = ref([]); const orderPickerVisible = ref(false)
```

Add methods (before `onMounted`):

```javascript
async function loadOrders() {
  try { myOrders.value = (await getMyOrders({ page: 1 })).data?.items || [] } catch { /* ok */ }
}
async function askAboutProduct() {
  if (!product.value || !convId) return
  const card = { type: 'product', product_id: product.value.id, title: product.value.title,
                 price: product.value.price, image: product.value.image, link: `/product/${product.value.id}` }
  try {
    await sendMsg(convId, { msg_type: 'product_card', content: { text: `咨询：${product.value.title}`, card } })
    await fetch()
  } catch { /* ok */ }
}
async function askAboutOrder(o) {
  if (!convId) return
  const card = { type: 'order', order_no: o.order_no, status: o.status, amount: o.pay_amount, link: '/orders' }
  try {
    await sendMsg(convId, { msg_type: 'order_card', content: { text: `咨询订单 ${o.order_no}`, card } })
    orderPickerVisible.value = false
    await fetch()
  } catch { /* ok */ }
}
function openCard(card) {
  if (card.type === 'product' && card.product_id) r.push(`/product/${card.product_id}`)
  else r.push('/orders')
}
```

Add `loadOrders()` to `onMounted` (after `await loadProduct()`):

```javascript
onMounted(async () => { await initConv(); await loadProduct(); await loadOrders(); await fetch(); pollTimer = setInterval(fetch, 2000) })
```

- [ ] **Step 3: Verify (requires Docker up)**

```bash
docker-compose --profile full up -d --build vmall-frontend-consumer
```

Browser E2E at `http://localhost:8090`:
1. 买家登录 `buyer_test/123456` → 进乳胶床垫详情 → 联系客服
2. 顶部出现商品卡片 + 「咨询此商品」按钮 → 点击 → 聊天区出现商品卡片消息 ✅
3. 点「关联我的订单」→ 选一个订单 → 聊天区出现订单卡片 ✅
4. 点击任一卡片 → 跳转到对应商品/订单页 ✅

- [ ] **Step 4: Commit**

```bash
git add vmall_system/frontend_consumer/src/views/Chat.vue vmall_system/frontend_consumer/src/api/index.js
git commit -m "feat: vmall 聊天页卡片渲染 + 咨询此商品/关联订单"
```

---

### Task 6: SaaS Service.vue — 订单面板 + 卡片渲染 + 卡片发送

**Files:**
- Modify: `frontend/src/views/Service.vue`
- Modify: `frontend/src/api/index.js`（加 `getBuyerOrders`）

**Interfaces:**
- Consumes: `GET /conversations/{id}/buyer-orders`（Task 3）；`sendConversationMessage(id, {content, card})`
- Produces: 客服可发商品卡片（改造现有按钮）+ 订单卡片；聊天窗口渲染卡片

- [ ] **Step 1: API — 加 getBuyerOrders**

In `frontend/src/api/index.js`, add after `sendConversationMessage` (line 53):

```javascript
export const getBuyerOrders = (id) => http.get(`/conversations/${id}/buyer-orders`)
```

- [ ] **Step 2: 聊天窗口渲染卡片**

In `frontend/src/views/Service.vue`, modify the message loop (the `v-for="(msg, i) in activeConv.messages_json"` block, around line 36-41). Replace with card-aware rendering:

```vue
          <div v-for="(msg, i) in activeConv.messages_json || []" :key="i" :style="{marginBottom:'12px',textAlign:msg.role==='buyer'?'left':'right'}">
            <!-- 卡片消息 -->
            <div v-if="msg.card" style="display:inline-block;max-width:75%;text-align:left">
              <el-card shadow="hover" body-style="padding:8px">
                <div v-if="msg.card.type==='product'" style="display:flex;gap:8px;align-items:center">
                  <el-image v-if="msg.card.image" :src="msg.card.image" fit="cover" style="width:44px;height:44px;border-radius:6px" />
                  <div><div style="font-weight:bold;font-size:13px">{{ msg.card.title }}</div>
                    <div style="color:#e6a23c;font-weight:bold">¥{{ msg.card.price }}</div></div>
                </div>
                <div v-else style="font-size:13px"><div style="font-weight:bold">📦 订单 {{ msg.card.order_no }}</div>
                  <div style="color:#909399">状态: {{ msg.card.status }} · ¥{{ msg.card.amount }}</div></div>
              </el-card>
            </div>
            <!-- 文本消息 -->
            <div v-else :style="{display:'inline-block',maxWidth:'70%',padding:'8px 14px',borderRadius:'8px',background:msg.role==='buyer'?'#f0f0f0':'#409eff',color:msg.role==='buyer'?'#303133':'#fff',textAlign:'left',wordBreak:'break-word'}">
              <div style="font-size:12px;margin-bottom:2px;opacity:0.7">{{ msg.role === 'buyer' ? activeConv.buyer_nick : '客服' }} · {{ msg.time?.slice(11, 16) || '' }}</div>
              {{ msg.content }}
            </div>
          </div>
```

- [ ] **Step 3: 改造发送商品卡片为 card 信封**

In `frontend/src/views/Service.vue`, modify `sendProductCard` (line 234).

> 设计取舍：推荐面板的商品来自 SaaS `getSimilarProducts`，不一定带 vmall 商品 ID，其深链不可靠。而**会话绑定的当前商品**有可靠的 `vm_product_id`（Task 3 Step 0 提供）。因此「发送商品卡片」发送**会话绑定商品**的卡片——这正是「验证售前推荐话术」的核心场景（客服确认/复述买家正在看的商品）。绑定商品缺失时禁用发送并提示。

Replace `sendProductCard`:

```javascript
async function sendProductCard() {
  if (!activeConv.value) return
  const p = activeConv.value.product
  if (!p || !p.vm_product_id) {
    ElMessage.warning('该会话未绑定可跳转的商品，无法发送商品卡片')
    return
  }
  const card = { type: 'product', product_id: p.vm_product_id, title: p.title,
                 price: p.price, image: p.image || '', link: `/product/${p.vm_product_id}` }
  try {
    const res = await sendConversationMessage(activeConv.value.id, { content: `为您推荐：${p.title}`, card })
    activeConv.value.messages_json = res.data?.messages_json || []
    ElMessage.success('已发送商品卡片')
  } catch { /* error shown by interceptor */ }
}
```

> 注意：调用处 `@click="sendProductCard(r)"`（推荐面板按钮）改为 `@click="sendProductCard"`（去掉参数），并在会话头部或推荐面板顶部加一个「发送当前商品卡片」按钮：`<el-button size="small" type="primary" plain :disabled="!activeConv?.product?.vm_product_id" @click="sendProductCard">发送当前商品卡片</el-button>`。推荐面板原有「发送商品卡片」按钮可保留但同样调用无参 `sendProductCard`（发送的是绑定商品）。

- [ ] **Step 4: 买家订单面板 + 发订单卡片**

In `frontend/src/views/Service.vue`, add `getBuyerOrders` to the import from `../api` (line 118). Add state (near `const recommendations = ref([])`):

```javascript
const buyerOrders = ref([])
```

Add a method:

```javascript
async function fetchBuyerOrders() {
  if (!activeConv.value) return
  try { buyerOrders.value = (await getBuyerOrders(activeConv.value.id)).data || [] } catch { buyerOrders.value = [] }
}
async function sendOrderCard(o) {
  if (!activeConv.value) return
  const card = { type: 'order', order_no: o.order_no, status: o.status, amount: o.amount, link: '/orders' }
  try {
    const res = await sendConversationMessage(activeConv.value.id, { content: `订单 ${o.order_no}`, card })
    activeConv.value.messages_json = res.data?.messages_json || []
    ElMessage.success('已发送订单卡片')
  } catch { /* error shown */ }
}
```

Call `fetchBuyerOrders()` inside `selectConv` (after `fetchRecommendations()`):

```javascript
    fetchRecommendations()
    fetchBuyerOrders()
```

Add an order panel in the right column (after the recommendations `<el-card>`, before closing the right column div):

```vue
      <el-card shadow="never" style="flex-shrink:0;max-height:200px;overflow:auto;margin-top:12px" body-style="padding:12px">
        <template #header><span style="font-weight:bold">🧾 买家订单</span></template>
        <div v-if="!activeConv"><el-empty description="选择会话后显示" :image-size="40" /></div>
        <div v-else v-for="o in buyerOrders" :key="o.order_no" style="margin-bottom:8px;padding:8px;background:#fafafa;border-radius:6px;border:1px solid #ebeef5">
          <div style="font-size:13px;font-weight:bold">{{ o.order_no }}</div>
          <div style="font-size:11px;color:#909399">状态: {{ o.status }} · ¥{{ o.amount }}</div>
          <el-button size="small" plain style="margin-top:4px" @click="sendOrderCard(o)">发送订单卡片</el-button>
        </div>
        <el-empty v-if="activeConv && !buyerOrders.length" description="无订单" :image-size="40" />
      </el-card>
```

- [ ] **Step 5: Verify (requires Docker up)**

```bash
docker-compose --profile full up -d --build saas-frontend
```

Browser E2E at `http://localhost:8095`（客服 `service/123456`，选数码旗舰商户）:
1. 打开一个买家会话 → 右侧「买家订单」面板列出订单 ✅
2. 点推荐商品「发送商品卡片」→ 聊天窗口出现商品卡片，买家端也收到可点卡片 ✅
3. 点买家订单「发送订单卡片」→ 聊天窗口出现订单卡片，买家端收到 ✅
4. 买家发来的卡片消息在客服窗口渲染成卡片 ✅

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/Service.vue frontend/src/api/index.js
git commit -m "feat: SaaS 工作台订单面板 + 卡片渲染 + 商品/订单卡片发送"
```

---

## Spec 差异说明

- Spec「校验 `_upsert_order` product 关联」一项经复核**对本子项目非必要**：订单卡片只展示 `order_no / status / amount`，不涉及商品关联。故不新增任务，避免无谓改动。若后续子项目需要订单内商品深链，再单独处理。

## 验证总览（Docker 恢复后一次性 E2E）

```bash
docker-compose --profile full up -d --build
```

1. **售前**：买家从床垫页进会话 → 「咨询此商品」→ 客服端看到商品卡片 → 客服发推荐商品卡片 → 买家点击跳详情 ✅
2. **售中/售后**：买家下单支付 → 客服「买家订单」面板出现该订单（含买家名）→ 发订单卡片 → 买家点击跳订单页 ✅
3. **向后兼容**：老纯文本消息、AI 文本回复正常显示 ✅

## 回滚

各 Task 独立 commit，`git revert <hash>` 可单独回滚任一 Task。卡片渲染向后兼容，回滚前端不影响已存的 card 数据（降级为文本显示）。
