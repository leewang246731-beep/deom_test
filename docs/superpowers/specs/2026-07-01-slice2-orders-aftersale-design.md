# Slice 2 设计 — 订单/售后/催单真实化（本地 + vmall 联动）

> 约束：**可改 vmall_system**（本次需要 vm 新接口），不改 taobao/jd（无凭证）。

## 1. 现状（Slice 1 完成后未变）

### 1.1 售后 `refund_order`（`orders.py:127`）
- 本地状态更新 + Redis 锁：正常
- 外部联动**三重损坏**：
  1. `connector.approve_after_sale(...)` 是 `async`，同步调用未 `await` → 协程不执行
  2. `sale_id = o.platform_order_id` 传的是订单号，vmall 要 `VmAfterSale.id`
  3. 整段包在 `try/except: pass`，失败静默

### 1.2 催单 `remind_pending`（`orders.py:76`）
- `generate_payment_reminders` 生成话术文本
- 不落库、不发送、异常吞为 "待步骤6接入"
- 无限冷却（无防重复机制）

### 1.3 Webhook `AFTER_SALE_CREATED`（`webhooks.py:66`）
- vmall 推送载荷含 `{"id": a.id, "order_id", "order_no", "refund_amount", ...}`
- 当前 `_upsert_order(db, data, "refunding")` 丢弃了 `id`（售后单 id）
- `ExternalOrder` 表无 `after_sale_id` 列

## 2. 设计

### 2.1 vmall 新接口 `POST /openapi/notifications`

```
入参: {buyer_id: int, order_id: int, content: str, msg_type: "reminder"}
逻辑: buyer_id 匹配 → 查找或创建买家系统会话 → 写入 VmMessage
返回: {id, conversation_id}
鉴权: Bearer token (与其他 openapi 一致)
```

**vmall 改动文件**：`vmall_system/backend/app/api/openapi/router.py`（新增 `send_notification` 端点）

### 2.2 SaaS connector 新增方法

`V3Connector.send_notification(buyer_id: int, order_id: int, content: str) -> dict`
→ `POST /openapi/notifications`

`PlatformConnector` 基类加抽象方法（`MockPlatformConnector` 返回 `{"id": 0, "conversation_id": 0}`）。

### 2.3 SaaS 基础设施 `run_connector`

新文件 `backend/app/core/platform_connector/runner.py`：
```python
def run_connector(coro) -> tuple[bool, any, str|None]:
    """同步端点中执行 async connector 方法。返回 (ok, data, error_msg)。"""
```
- 用 `asyncio.run()`；区分 `httpx.HTTPStatusError`/timeout/其他
- 所有 connector 调用点统一使用

### 2.4 售后流程

1. Redis 锁（保留）
2. 校验 `mid` 作用域 + 状态 ∈ {paid, refunding}
3. real 模式 + `platform_type=="vmall"` + `after_sale_id` 非空：
   - `run_connector(connector.approve_after_sale(after_sale_id, "approve", remark))`
   - 成功 → `status="refunded"`, `after_sale_status="approved"`
   - 失败 → 保持 `refunding`，返回 `50201`
4. mock/非 vmall/无 sale_id → 仅本地 `status="refunded"`
5. 始终写 `AuditLog`

### 2.5 催单流程

1. `generate_payment_reminders` 生成话术
2. 逐订单：
   - Redis 冷却检查（`REMINDER_COOLDOWN_SECONDS` 默认 21600）
   - 落 `order_reminders` 行
   - real+vmall → `run_connector(connector.send_notification(buyer_id, order_id, content))`
   - 外发 best-effort：失败记日志不阻塞
3. 返回 `{reminders, sent_count, skipped_count, total_pending}`

### 2.6 Webhook 增强

`AFTER_SALE_CREATED` handler 增加 `external_order.after_sale_id = data["id"]`、`after_sale_status = "created"`。

### 2.7 数据模型

- `ExternalOrder` + `after_sale_id BIGINT NULL` + `after_sale_status VARCHAR(20) NULL`
- 新表 `order_reminders(id, merchant_id, shop_id, order_id, buyer_openid, content, channel, sent_at, created_at)`
- 迁移脚本：幂等 ALTER TABLE（先查列是否存在）

### 2.8 前端

`Orders.vue` 催单弹窗展示 `sent_count/skipped_count`。

## 3. 测试计划

- 售后状态机：paid/refunding→refunded；非法状态→40001；重复→40901
- 售后 external：vmall 售后 → SaaS webhook 落 sale_id → SaaS 审批 → vmall `VmAfterSale.status=="approved"`
- 售后 vmall 不可达 → 50201，订单保持 refunding
- 催单冷却：同订单 6h 内第二次 → skipped_count+1
- 催单 external：real 模式 → `order_reminders` 行存在 + vmall `VmMessage` 已创建
- `run_connector`：vmall 4xx/网络异常 → (False, _, err)，不抛穿
- 回归：`test_e2e_smoke.py` 78 用例通过 + RAG 10 通过

## 4. 错误码

| code | 含义 |
|---|---|
| 40001 | 订单状态不允许售后 |
| 40401 | 订单不存在 |
| 40901 | 售后处理中/重复提交 |
| 50201 | vMall 售后联动失败（本地挂起） |
| 50202 | vMall 催单外发部分失败 |

## 5. 变更清单

**vmall (1 文件):**
- `vmall_system/backend/app/api/openapi/router.py` — 新增 `POST /openapi/notifications`

**SaaS 后端 (7 文件):**
- `backend/app/core/platform_connector/base.py` — `PlatformConnector` +抽象方法 `send_notification`
- `backend/app/core/platform_connector/vmall.py` — `V3Connector.send_notification`
- `backend/app/core/platform_connector/mock.py` — `MockPlatformConnector.send_notification`（空返回）
- `backend/app/core/platform_connector/runner.py` — 新增 `run_connector`
- `backend/app/api/v1/orders.py` — 重写 `refund_order` / `remind_pending`
- `backend/app/api/v1/webhooks.py` — AFSA 落 after_sale_id
- `backend/app/models/external_order.py` — +2 列
- `backend/app/models/order_reminder.py` — 新表
- `backend/scripts/migrate_slice2.py` — 幂等迁移
- `backend/app/core/config.py` — +`REMINDER_COOLDOWN_SECONDS`

**SaaS 前端 (1 文件):**
- `frontend/src/views/Orders.vue` — 催单弹窗展示 sent/skipped

## 6. 不做

- taobao/jd 连接器真实对接（无凭证）
- 自动重试队列（失败挂起 + 日志，重试后续）
