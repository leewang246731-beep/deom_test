# Slice 2 — Orders/After-sale/Reminder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复售后和催单两个按钮——售后真实联动 vmall（修 un-await + 错误 sale_id + 静默吞错）、催单落库 + 冷却 + 外发到 vmall。

**Architecture:** vmall 新增 `POST /openapi/notifications` 买家通知端点；SaaS 新增 `run_connector` async→sync 桥接；connector 基类/子类补 `send_notification`；`refund_order` 用正确的 `after_sale_id` await 调用 vmall；`remind_pending` 落库 `order_reminders` + Redis 冷却 + 外发；webhook 捕获 `after_sale_id` 落库。

**Tech Stack:** FastAPI (Python 3.13), Vue 3 + Element Plus, MySQL 8.0, Redis

## Global Constraints

- **可改 vmall_system**（本次需要新接口）。不改 taobao/jd。
- vmall 售后联动失败 → 不吞错，返回 50201，订单保持 refunding。
- 催单外发 best-effort：vmall 失败不阻塞其他订单。
- `python test_e2e_smoke.py` 78 用例不回归；RAG 10 不回归。
- 所有 connector 调用通过 `run_connector` 桥接（不再直接 `asyncio.run` 或忘 `await`）。

---

### Task 1: vmall — 新增 `POST /openapi/notifications` 端点

**Files:**
- Modify: `vmall_system/backend/app/api/openapi/router.py` — 在 `send_message` 之后追加新端点

**Interfaces:**
- Produces: `POST /openapi/notifications` — `{buyer_id, order_id, content, msg_type} → {id, conversation_id}`
- Consumes: `_verify_token` (已有), `VmConversation`, `VmMessage` (已有)

- [ ] **Step 1: 追加端点代码**

在 `vmall_system/backend/app/api/openapi/router.py` 的 `send_message` 函数之后（约第 198 行）追加：

```python
@router.post("/notifications")
def send_notification(body: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    """SaaS 推送买家通知（催单等）。按 buyer_id 查找或创建系统会话后写入消息。"""
    _verify_token(authorization, db)
    buyer_id = body.get("buyer_id")
    order_id = body.get("order_id")
    content = body.get("content", "")
    msg_type = body.get("msg_type", "reminder")

    if not buyer_id or not content:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "buyer_id 和 content 必填"})

    # 查找或创建该买家的系统会话
    conv = db.query(VmConversation).filter(
        VmConversation.buyer_id == buyer_id,
        VmConversation.status == "open",
    ).first()
    if not conv:
        conv = VmConversation(
            buyer_id=buyer_id,
            product_id=0,
            order_id=order_id or 0,
            status="open",
            last_message_at=datetime.now(),
        )
        db.add(conv)
        db.flush()

    msg = VmMessage(
        conversation_id=conv.id,
        sender_role="system",
        msg_type=msg_type,
        content_json={"text": content},
    )
    db.add(msg)
    conv.last_message_at = datetime.now()
    db.commit()
    return ok({"id": msg.id, "conversation_id": conv.id})
```

（`datetime` 已在文件顶部导入；`VmConversation` / `VmMessage` 已在文件顶部导入。）

- [ ] **Step 2: 验证**

```bash
# 假设 vmall backend 在 8020 端口运行
curl -s -X POST http://127.0.0.1:8020/openapi/notifications \
  -H "Authorization: Bearer <valid_token>" \
  -H "Content-Type: application/json" \
  -d '{"buyer_id":1,"order_id":1,"content":"您的订单即将超时，请尽快付款","msg_type":"reminder"}' \
  -w "\nHTTP=%{http_code}\n"
```

Expected: `HTTP=200`, 返回 `{"code":200,"data":{"id":...,"conversation_id":...}}`。

验证消息已写入：
```bash
python -c "
import pymysql
c=pymysql.connect(host='127.0.0.1',port=3306,user='root',password='121300',database='demo_test')
r=c.cursor()
r.execute(\"SELECT id,conversation_id,msg_type,content_json FROM vm_messages ORDER BY id DESC LIMIT 3\")
for row in r.fetchall(): print(row)
c.close()
"
```

Expected: 最后一行是 `msg_type='reminder'` 的新消息。

- [ ] **Step 3: Commit**

```bash
cd vmall_system
git add backend/app/api/openapi/router.py
git commit -m "feat: add POST /openapi/notifications — buyer notification for SaaS reminder"
cd ..
```

---

### Task 2: SaaS — `run_connector` async→sync 桥接

**Files:**
- Create: `backend/app/core/platform_connector/runner.py`

**Interfaces:**
- Produces: `run_connector(coro) -> tuple[bool, any, str|None]` — `(ok, data, error_msg)`
- Consumes: none (standalone utility)

- [ ] **Step 1: 创建文件**

```python
"""run_connector — 同步 FastAPI 端点中安全执行 async connector 方法。"""
import asyncio
from typing import Any


def run_connector(coro) -> tuple[bool, Any, str | None]:
    """在同步端点中执行异步 connector 调用。
    
    返回 (ok, data, error_msg)。
    - ok=True: data 是 connector 方法的返回值
    - ok=False: data 是 None，error_msg 包含错误描述
    """
    try:
        result = asyncio.run(coro)
        return (True, result, None)
    except Exception as e:
        error_msg = f"{type(e).__name__}: {e}"
        return (False, None, error_msg)
```

- [ ] **Step 2: 验证 import**

```bash
cd backend && python -c "from app.core.platform_connector.runner import run_connector; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add app/core/platform_connector/runner.py
git commit -m "feat: add run_connector — async-to-sync bridge for connector calls"
```

---

### Task 3: SaaS — 数据模型 + 迁移

**Files:**
- Modify: `backend/app/models/external_order.py` — +2 列
- Create: `backend/app/models/order_reminder.py` — 新表
- Modify: `backend/app/models/__init__.py` — 注册新模型
- Create: `backend/scripts/migrate_slice2.py` — 幂等迁移
- Modify: `backend/app/core/config.py` — +`REMINDER_COOLDOWN_SECONDS`

**Interfaces:**
- Produces: `ExternalOrder.after_sale_id`, `ExternalOrder.after_sale_status`, `OrderReminder` 表, `settings.REMINDER_COOLDOWN_SECONDS`

- [ ] **Step 1: 修改 `external_order.py`**

在第 43 行（`ship_time` 之后）追加：

```python
    after_sale_id = Column(BigInteger, nullable=True, comment="vMall 售后单 id")
    after_sale_status = Column(String(20), nullable=True, comment="created/approved/rejected")
```

- [ ] **Step 2: 创建 `order_reminder.py`**

```python
"""催单发送记录"""
from sqlalchemy import BigInteger, Column, DateTime, Integer, String, Text, func

from app.database.session import Base


class OrderReminder(Base):
    __tablename__ = "order_reminders"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    merchant_id = Column(BigInteger, nullable=False, index=True)
    shop_id = Column(BigInteger, nullable=False)
    order_id = Column(BigInteger, nullable=False)
    buyer_openid = Column(String(100), nullable=True)
    content = Column(Text, nullable=True)
    channel = Column(String(20), default="vmall", comment="vmall / local")
    sent_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())
```

- [ ] **Step 3: 注册到 `__init__.py`**

在 `backend/app/models/__init__.py` 追加：

```python
from app.models.order_reminder import OrderReminder
```

- [ ] **Step 4: 配置冷却时间**

在 `backend/app/core/config.py` 的 Settings 类中追加：

```python
    REMINDER_COOLDOWN_SECONDS: int = 21600  # 6 hours
```

- [ ] **Step 5: 创建迁移脚本 `backend/scripts/migrate_slice2.py`**

```python
"""Slice 2 幂等迁移：ExternalOrder +after_sale_id/+after_sale_status, order_reminders 表"""
import pymysql
from app.core.config import settings

def migrate():
    conn = pymysql.connect(
        host=settings.DB_HOST, port=settings.DB_PORT,
        user=settings.DB_USER, password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
    )
    cur = conn.cursor()

    # 1. ExternalOrder 新列（幂等：先查是否存在）
    cur.execute("SHOW COLUMNS FROM external_orders LIKE 'after_sale_id'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE external_orders ADD COLUMN after_sale_id BIGINT NULL COMMENT 'vMall售后单id'")
        print("  + external_orders.after_sale_id")

    cur.execute("SHOW COLUMNS FROM external_orders LIKE 'after_sale_status'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE external_orders ADD COLUMN after_sale_status VARCHAR(20) NULL COMMENT 'created/approved/rejected'")
        print("  + external_orders.after_sale_status")

    # 2. order_reminders 表（幂等）
    cur.execute("SHOW TABLES LIKE 'order_reminders'")
    if not cur.fetchone():
        cur.execute("""
            CREATE TABLE order_reminders (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                merchant_id BIGINT NOT NULL,
                shop_id BIGINT NOT NULL,
                order_id BIGINT NOT NULL,
                buyer_openid VARCHAR(100) NULL,
                content TEXT NULL,
                channel VARCHAR(20) DEFAULT 'vmall',
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_merchant (merchant_id),
                INDEX idx_order (order_id)
            )
        """)
        print("  + order_reminders table")

    conn.commit()
    conn.close()
    print("Slice 2 migration complete.")

if __name__ == "__main__":
    migrate()
```

- [ ] **Step 6: 执行迁移**

```bash
cd backend && python scripts/migrate_slice2.py
```

Expected: 输出 `+ external_orders.after_sale_id` `+ external_orders.after_sale_status` `+ order_reminders table` `Slice 2 migration complete.`

再跑一次验证幂等：
```bash
python scripts/migrate_slice2.py
```

Expected: `Slice 2 migration complete.`（无 `+` 行，全部已存在）。

- [ ] **Step 7: Commit**

```bash
git add app/models/external_order.py app/models/order_reminder.py app/models/__init__.py app/core/config.py scripts/migrate_slice2.py
git commit -m "feat: data model — after_sale_id, order_reminders table, cooldown config"
```

---

### Task 4: SaaS — Connector 三文件更新

**Files:**
- Modify: `backend/app/core/platform_connector/base.py` — +`send_notification` 抽象方法
- Modify: `backend/app/core/platform_connector/vmall.py` — +`send_notification` 实现
- Modify: `backend/app/core/platform_connector/mock.py` — +`send_notification` 桩

- [ ] **Step 1: base.py — 追加抽象方法**

在 `get_conversations` 之后追加：

```python
    @abstractmethod
    async def send_notification(self, buyer_id: int, order_id: int, content: str) -> dict:
        """向买家推送通知（催单等）。返回 {id, conversation_id}。"""
        ...
```

- [ ] **Step 2: vmall.py — 追加实现**

在 `approve_after_sale` 之后追加：

```python
    async def send_notification(self, buyer_id: int, order_id: int, content: str) -> dict:
        """调用 vMall /openapi/notifications 推送买家通知。"""
        return await self._post("/openapi/notifications", {
            "buyer_id": buyer_id,
            "order_id": order_id,
            "content": content,
            "msg_type": "reminder",
        })
```

- [ ] **Step 3: mock.py — 追加桩**

在 `MockPlatformConnector` 类中找到类似 `send_message` 的桩方法，在其后追加：

```python
    async def send_notification(self, buyer_id: int, order_id: int, content: str) -> dict:
        return {"id": 0, "conversation_id": 0}
```

- [ ] **Step 4: 验证 import**

```bash
cd backend && python -c "from app.core.platform_connector.base import PlatformConnector; from app.core.platform_connector.vmall import V3Connector; from app.core.platform_connector.mock import MockPlatformConnector; print('all imports OK')"
```

Expected: `all imports OK`

- [ ] **Step 5: Commit**

```bash
git add app/core/platform_connector/base.py app/core/platform_connector/vmall.py app/core/platform_connector/mock.py
git commit -m "feat: connector — add send_notification to base, vmall, mock"
```

---

### Task 5: SaaS — Webhook `AFTER_SALE_CREATED` 增强

**Files:**
- Modify: `backend/app/api/v1/webhooks.py:66-67` — `_upsert_order` 后落 `after_sale_id`

- [ ] **Step 1: 修改 `_handle_after_sale_created` handler**

webhooks.py 第 66 行 `AFTER_SALE_CREATED` 分支当前只调用 `_upsert_order`。改为先 upsert，再回写 `after_sale_id`：

```python
        elif event == "AFTER_SALE_CREATED":
            _upsert_order(db, data, "refunding")
            # 回写 vmall 售后单 id（refund_order 联动需要）
            order_no = data.get("order_no") or str(data.get("order_id", data.get("id", "")))
            sale_id = data.get("id")  # vmall VmAfterSale.id
            if order_no and sale_id:
                shop = _resolve_shop(db, data)
                if shop:
                    exist = db.query(ExternalOrder).filter(
                        ExternalOrder.shop_id == shop.id,
                        ExternalOrder.platform_order_id == order_no,
                    ).first()
                    if exist:
                        exist.after_sale_id = sale_id
                        exist.after_sale_status = "created"
                        db.commit()
```

- [ ] **Step 2: 验证 import**

```bash
cd backend && python -c "from app.api.v1.webhooks import router; print('import OK')"
```

Expected: `import OK`（`ExternalOrder` 已在文件顶部导入）。

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/webhooks.py
git commit -m "feat: webhook AFTER_SALE_CREATED — persist after_sale_id from vmall"
```

---

### Task 6: SaaS — `refund_order` 重写

**Files:**
- Modify: `backend/app/api/v1/orders.py:127-175` — `refund_order` 函数

- [ ] **Step 1: 重写函数**

用 `run_connector` + 正确的 `after_sale_id` + 失败不吞错，替换现有实现：

```python
@router.post("/{order_id}/refund")
def refund_order(
    order_id: int,
    current: CurrentUser = Depends(require_roles("admin", "manager")),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    """售后：Redis 锁防并发；real+vmall 联动审批售后；mock/非vmall 本地标记。"""
    shop_ids = _merchant_shop_ids(db, mid)
    o = db.query(ExternalOrder).filter(
        ExternalOrder.id == order_id,
        ExternalOrder.shop_id.in_(shop_ids) if shop_ids else False,
    ).first()
    if not o:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})

    r = get_redis()
    lock_key = mkey(mid, "lock", f"refund_{order_id}")
    if not r.set(lock_key, "1", nx=True, ex=30):
        raise HTTPException(status_code=409, detail={"code": 40901, "msg": "售后处理中，请勿重复提交"})
    try:
        if o.status in ("refunded", "refunding"):
            raise HTTPException(status_code=409, detail={"code": 40901, "msg": "订单已在售后流程"})
        if o.status not in ("paid", "refunding"):
            raise HTTPException(status_code=400, detail={"code": 40001, "msg": "当前订单状态不允许售后"})

        before_status = o.status
        vmall_notified = False

        # real 模式 + vmall 店铺 + 有 after_sale_id → 联动 vmall 审批
        shop = db.query(PlatformShop).filter(PlatformShop.id == o.shop_id).first()
        if (settings.PLATFORM_MODE == "real" and shop and shop.platform_type == "vmall"
                and shop.access_token and o.after_sale_id):
            from app.core.platform_connector.vmall import V3Connector
            from app.core.platform_connector.runner import run_connector
            connector = V3Connector(shop.shop_url or "http://127.0.0.1:8020", shop.access_token)
            ok, data, err = run_connector(
                connector.approve_after_sale(o.after_sale_id, "approve", "SaaS平台审核通过")
            )
            if ok:
                o.status = "refunded"
                o.after_sale_status = "approved"
                vmall_notified = True
            else:
                # vmall 联动失败：订单保持 refunding，返回错误
                _write_audit(db, mid, current.user_id, current.username, "order",
                             order_id, before_status, "refunding",
                             f"vmall_approve_failed: {err}")
                raise HTTPException(
                    status_code=502,
                    detail={"code": 50201, "msg": f"vMall 售后审批失败，已挂起: {err}"},
                )
        else:
            o.status = "refunded"

        db.commit()

        _write_audit(db, mid, current.user_id, current.username, "order",
                     order_id, before_status, o.status,
                     f"vmall_notified={vmall_notified}")
        return ok({"id": o.id, "status": o.status, "vmall_notified": vmall_notified}, msg="售后成功")
    finally:
        r.delete(lock_key)
```

在文件顶部 import 区加：
```python
from app.core.config import settings
```

（`PlatformShop` 已在 import 中；`mkey` / `get_redis` 已导入。）

在文件末尾加审计辅助函数：
```python
def _write_audit(db, merchant_id, user_id, username, target_type, target_id, before_val, after_val, extra):
    from app.models.audit_log import AuditLog
    import json
    db.add(AuditLog(
        merchant_id=merchant_id, user_id=user_id, username=username,
        action="status_change", target_type=target_type, target_id=target_id,
        detail_json=json.dumps({"before": before_val, "after": after_val, "extra": extra}, ensure_ascii=False),
        ip="",
    ))
```

- [ ] **Step 2: 验证后端 import + 冒烟**

```bash
cd backend && python -c "from app.api.v1.orders import router; print('import OK')"
```

Expected: `import OK`

重启 backend 后测试：
```bash
MT=$(curl -s -X POST http://127.0.0.1:8012/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"123456","merchant_id":11}' | python -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")
# mock 模式下售后（本地真）
curl -s -X POST http://127.0.0.1:8012/api/v1/orders/1/refund -H "Authorization: Bearer $MT" -w "\nHTTP=%{http_code}\n"
```

Expected: `HTTP=200`, `"msg":"售后成功"`, order 1 status=`refunded`。

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/orders.py
git commit -m "feat: refund_order — real vmall after-sale approval via run_connector"
```

---

### Task 7: SaaS — `remind_pending` 重写

**Files:**
- Modify: `backend/app/api/v1/orders.py:76-94` — `remind_pending` 函数

- [ ] **Step 1: 重写函数**

```python
@router.post("/pending-payment/remind")
def remind_pending(
    body: AICampaignRequest,
    current: CurrentUser = Depends(get_current_user),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    """批量催单：AI 生成话术 → 冷却检查 → 落库 → real+vmall 外发。"""
    from app.services.ai_suggest import generate_payment_reminders
    from app.core.platform_connector.vmall import V3Connector
    from app.core.platform_connector.runner import run_connector
    from app.models.order_reminder import OrderReminder
    from datetime import datetime

    r = get_redis()
    limit = min(body.limit or 20, 50)
    reminders_data = generate_payment_reminders(mid, body.shop_id, db, limit=limit, offset=body.offset or 0)
    reminders = reminders_data.get("reminders", [])

    sent_count = 0
    skipped_count = 0
    enriched = []

    for rem in reminders:
        order_id = rem.get("order_id")
        buyer_openid = rem.get("buyer_openid", "")
        content = rem.get("script", "")

        # 冷却检查
        cooldown_key = mkey(mid, "remind", str(order_id))
        if r.exists(cooldown_key):
            skipped_count += 1
            rem["skipped"] = True
            enriched.append(rem)
            continue

        # 落库发送记录
        db.add(OrderReminder(
            merchant_id=mid, shop_id=body.shop_id, order_id=order_id,
            buyer_openid=str(buyer_openid), content=content, channel="vmall",
            sent_at=datetime.now(),
        ))

        # real 模式 + vmall → 外发通知
        if settings.PLATFORM_MODE == "real":
            shop = db.query(PlatformShop).filter(PlatformShop.id == body.shop_id).first()
            if shop and shop.platform_type == "vmall" and shop.access_token:
                connector = V3Connector(shop.shop_url or "http://127.0.0.1:8020", shop.access_token)
                ok, _, err = run_connector(
                    connector.send_notification(int(buyer_openid) if buyer_openid else 0, order_id, content)
                )
                if not ok:
                    rem["send_error"] = err
            else:
                rem["send_error"] = "not vmall or no token"
        else:
            rem["channel"] = "local"

        # 设冷却
        r.set(cooldown_key, "1", ex=settings.REMINDER_COOLDOWN_SECONDS)
        sent_count += 1
        rem["skipped"] = False
        enriched.append(rem)

    db.commit()

    return ok({
        "reminders": enriched,
        "sent_count": sent_count,
        "skipped_count": skipped_count,
        "total_pending": reminders_data.get("total_pending", 0),
        "has_more": len(reminders) >= limit,
    })
```

- [ ] **Step 2: 验证 import**

```bash
cd backend && python -c "from app.api.v1.orders import router; print('import OK')"
```

Expected: `import OK`

重启 backend 后测试催单：
```bash
MT=$(curl -s -X POST http://127.0.0.1:8012/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"123456","merchant_id":11}' | python -c "import sys,json;print(json.load(sys.stdin)['data']['access_token'])")
curl -s -X POST http://127.0.0.1:8012/api/v1/orders/pending-payment/remind \
  -H "Authorization: Bearer $MT" \
  -H "Content-Type: application/json" \
  -d '{"shop_id":null,"limit":5}' | python -m json.tool | head -20
```

Expected: 返回含 `sent_count` / `skipped_count` / `reminders` 的结构。第二次调用同参数 → `skipped_count > 0`（冷却生效）。

- [ ] **Step 3: Commit**

```bash
git add app/api/v1/orders.py
git commit -m "feat: remind_pending — real persistence, cooldown, vmall notification"
```

---

### Task 8: Frontend — `Orders.vue` 催单弹窗展示计数

**Files:**
- Modify: `frontend/src/views/Orders.vue` — 催单弹窗区

- [ ] **Step 1: 修改弹窗模板**

在 `Orders.vue` 的催单弹窗（`<el-dialog v-model="remindVisible">`）内，第 55-56 行附近，替换现有的 `<el-alert v-if="!reminders.length">` 为：

```html
<el-dialog v-model="remindVisible" title="催单话术" width="650px">
  <div style="margin-bottom:12px">
    <el-tag type="success">已发送 {{ sentCount }}</el-tag>
    <el-tag v-if="skippedCount" type="info" style="margin-left:8px">跳过 {{ skippedCount }}（冷却中）</el-tag>
  </div>
  <el-alert v-if="!reminders.length" type="info" :closable="false" title="当前无待催付订单" />
  <div v-else v-for="(r, i) in reminders" :key="i" ...>
```

- [ ] **Step 2: 在 script 中加 sentCount/skippedCount**

在 `const reminders = ref([])` 之后追加：

```javascript
const sentCount = ref(0)
const skippedCount = ref(0)
```

在 `handleRemind` 函数中，API 返回后赋值：

```javascript
    const res = await remindPayment(shopId, 20, 0)
    reminders.value = res.data?.reminders || []
    sentCount.value = res.data?.sent_count || 0
    skippedCount.value = res.data?.skipped_count || 0
    remindVisible.value = true
```

- [ ] **Step 3: 验证 build**

```bash
cd frontend && npx vite build --mode admin 2>&1 | tail -3
```

Expected: `✓ built in ...`

- [ ] **Step 4: Commit**

```bash
git add src/views/Orders.vue
git commit -m "feat: orders page — show sent/skipped counts in reminder dialog"
```

---

### Task 9: 全链路验证

- [ ] **Step 1: 回归测试**

```bash
cd backend
# 确保 backend 在 8012 运行
python test_e2e_smoke.py 2>&1 | tail -5
```

Expected: 76-78 passed（KB 预存问题可忽略）。

```bash
python -m pytest tests/ -q 2>&1 | tail -3
```

Expected: 10 passed.

- [ ] **Step 2: 催单冷却手动验证**

同订单 6h 内第二次催 → `skipped_count=1`。

- [ ] **Step 3: Commit**

```bash
git commit --allow-empty -m "verify: slice 2 regression — E2E + RAG pass"
```

---

### Task 10 (Bonus): 铺开 `run_connector` 到其他 connector 调用点

| 文件 | 当前调用方式 | 改法 |
|---|---|---|
| `orders.py:refund_order` | (已在本 Task 6 修) | ✅ |
| `orders.py:remind_pending` | (已在本 Task 7 修) | ✅ |
| `shops.py:sync_shop` | 直接 `await`（async endpoint） | 不适用（已是 async） |
| `products.py:sync_products` | 直接 `await`（async endpoint） | 不适用 |
| `webhooks.py:_maybe_auto_reply` | `await connector.send_message(...)` — 已有 await | 不变（已是 async） |

本切片无其他需迁移的调用点。

