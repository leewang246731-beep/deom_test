# Slice 1 设计 — 订单/售后按钮真实化（智能托管 SaaS 端）

> 大目标：把三端（8093 平台 / 8094 商户 / 8095 客服）所有"Mock 模式空壳"按钮改成真逻辑（本地真实持久化 + 对 vmall 真实联动），逐切片交付。
> 本文件只覆盖 **切片 1**：订单域的两个操作按钮。约束：**只改智能托管 SaaS（`backend/` + `frontend/`），不改 `vmall_system`**。

## 1. 背景与现状诊断（已核验）

系统默认 `PLATFORM_MODE=mock`（`backend/app/core/config.py:35`），按钮在演示中"能点、有反馈"，但操作类按钮只改本地 DB 或只生成文案，真实业务/跨系统联动缺失或损坏。

SaaS 前端订单页（`frontend/src/views/Orders.vue`）操作按钮：导出CSV（已真实，保留）、**一键催单**、**售后**。无发货按钮（vmall 负责发货）。

### 1.1 售后按钮（`backend/app/api/v1/orders.py:127` `refund_order`）
- 本地：仅把 `ExternalOrder.status` 置 `refunded`，已有 Redis 锁防并发。
- 外部联动**已损坏**：
  - `connector.approve_after_sale(...)` 是 `async` 方法，却被 **同步调用未 `await`** → 只造了协程从不执行（`orders.py:161`）。
  - 传入的 `sale_id` 实为 `o.platform_order_id`（订单号），但 vmall `/openapi/after-sales/{sale_id}/approve` 需要的是**售后单 id**（`VmAfterSale.id`），见 `vmall_system/.../openapi/router.py:139`。
  - 整段包在 `try/except: pass`，失败完全静默。

### 1.2 催单按钮（`backend/app/api/v1/orders.py:76` `remind_pending`）
- 仅调用 `generate_payment_reminders` **生成话术文本**返回前端复制，**从不真正发送**；异常被吞为 `"AI 催单待步骤6 接入"`。

### 1.3 跨系统已具备的基础（关键可行性依据）
- vmall 在买家提交售后时推送 `AFTER_SALE_CREATED` webhook，**载荷含售后单 id**：
  `{"id": a.id, "order_id", "order_no", "refund_amount", "type", "reason", "status"}`（`vmall_system/.../consumer/after_sales.py:32`）。
- SaaS 已接收该 webhook（`backend/app/api/v1/webhooks.py:66`），但当前 `_upsert_order(db, data, "refunding")` **丢弃了 `id`**。
- 结论：SaaS 只要把售后单 id 落库，即可在不改 vmall 的前提下，对 vmall 真实审批售后。

## 2. 切片 1 目标与边界

| 按钮 | 本地真实 | 外部联动（vmall, real 模式） | 本切片是否做 |
|---|---|---|---|
| 售后 refund | ✅ 状态机 + 审计 + 幂等 | ✅ `await` 正确 `sale_id` 审批 + 失败处理 | **是** |
| 催单 remind | ✅ 落库发送记录 + 冷却幂等 + 真实 sent_count | ⛔ vmall `/openapi/messages` 需 `conversation_id`，无买家可寻址接口 | **本地真；外部延后切片 2** |

催单外部发送延后切片 2（会话/消息基础设施所在），避免消息逻辑做两遍。这是已确认决策。

## 3. 详细设计

### 3.1 数据模型变更（纯新增列，向后兼容）
`backend/app/models/external_order.py` 新增：
- `after_sale_id BIGINT NULL` — vmall 售后单 id（来自 webhook）。
- `after_sale_status VARCHAR(20) NULL` — `created/approved/rejected`，本地镜像。

迁移：写 `backend/scripts/migrate_slice1.py`，对已有库 `ALTER TABLE external_orders ADD COLUMN ...`（幂等：先查列是否存在）。`seed.py` 无需改。

### 3.2 异步连接器调用范式（可复用，切片 2/3 继承）
新增 `backend/app/core/platform_connector/runner.py`：
```python
def run_connector(coro):
    """在同步 FastAPI 端点中执行 async 连接器方法。返回 (ok: bool, data, error)。"""
```
- 用 `asyncio.run(coro)` 执行；捕获 `httpx.HTTPStatusError` / 超时 / 其它，区分"vmall 返回错误"与"网络失败"。
- 不再吞异常——把结果交给调用方决定状态机与返回码。

### 3.3 售后流程（`refund_order` 重写）
前置：角色 `admin`/`manager`（保留）。Redis 锁（保留）。
1. 校验订单存在且属于当前 merchant 的店铺；状态 ∈ {`paid`,`refunding`} 否则 `40001`；已是 `refunded`/处理中 → `40901`。
2. **外部优先于落终态**（real 模式 + 店铺 `platform_type=="vmall"` + 有 `after_sale_id`）：
   - `ok, data, err = run_connector(connector.approve_after_sale(after_sale_id, "approve", "SaaS平台审核通过"))`
   - 成功 → 本地 `status="refunded"`、`after_sale_status="approved"`，提交。
   - 失败 → 本地保持 `refunding`，返回 `code=50201, msg="vMall 售后审批失败，已挂起待重试"`，记录审计 + `WebhookDeliveryLog`/日志。
3. **mock 模式 / 非 vmall 店铺 / 无 after_sale_id**：仅本地 `status="refunded"`（本地真实，行为同今天但去掉静默吞错与错误 sale_id）。
4. 始终写 `AuditLog`（`action="status_change"`, `target_type="order"`, `target_id=o.id`, `detail_json={before,after,channel,vmall_sale_id}`, `ip`）。
5. webhook `AFTER_SALE_CREATED` 处理增强：在 `_upsert_order` 之外，落 `after_sale_id=data["id"]`、`after_sale_status="created"`。

### 3.4 催单流程（`remind_pending` 重写，本地真实）
1. 保留 `generate_payment_reminders` 生成话术。
2. **冷却幂等**：每个订单一个 Redis 键 `mkey(merchant_id,"remind",order_id)`，TTL = `REMINDER_COOLDOWN_SECONDS`（新增配置，默认 6h）。已存在则跳过，计入 `skipped`。
3. **落库发送记录**：新增轻量表 `order_reminders(id, merchant_id, shop_id, order_id, channel, content, created_at)`（`channel="local"`，切片 2 加 `"vmall"`）。
4. 返回真实结构：`{reminders:[...], sent_count, skipped_count, total_pending, has_more}`；不再吞错为占位文案，异常按 `5xxxx` 返回。
5. 前端 `Orders.vue` 催单弹窗展示 `sent_count/skipped_count`，文案可复制（保留）。

### 3.5 错误码约定
| code | 含义 |
|---|---|
| 40401 | 订单不存在 |
| 40001 | 订单状态不允许售后 |
| 40901 | 售后处理中/重复提交 |
| 50201 | vMall 售后联动失败（本地挂起） |
| 50301 | 催单生成/发送内部错误 |

## 4. 测试计划（验收：用例 100% 通过 + 不回归）

### 4.1 单元/接口测试（`backend/tests/test_slice1_*.py`，pytest）
- 售后状态机：`paid→refunded` 成功；非法状态 → 40001；重复提交 → 40901；审计写入断言。
- mock 模式售后：不触发外部调用（mock connector 计数=0），本地落终态。
- 催单冷却：连续两次催同一订单 → 第二次 `skipped_count+1`；TTL 过期后可再催。
- `run_connector`：vmall 返回 4xx → `(False,_,err)`；网络异常 → `(False,_,err)`，均不抛穿。

### 4.2 集成/E2E（需 vmall + SaaS 均启动，real 模式）
- 买家在 vmall 提交售后 → SaaS 收 `AFTER_SALE_CREATED`、`after_sale_id` 落库 → SaaS 点"售后" → 断言 vmall `VmAfterSale.status=="approved"` 且 SaaS 订单 `refunded`。
- vmall 不可达时点售后 → SaaS 返回 50201、订单保持 `refunding`、有审计与日志。

### 4.3 回归
- `python test_e2e_smoke.py`（78 用例）保持通过。
- `python -m pytest tests/ -q`（RAG 10 用例）保持通过。

## 5. 变更清单（仅 SaaS 侧）
- `backend/app/models/external_order.py`（+2 列）
- `backend/app/models/order_reminder.py`（新）
- `backend/scripts/migrate_slice1.py`（新，幂等迁移）
- `backend/app/core/platform_connector/runner.py`（新）
- `backend/app/core/config.py`（+`REMINDER_COOLDOWN_SECONDS`）
- `backend/app/api/v1/orders.py`（重写 `refund_order` / `remind_pending`）
- `backend/app/api/v1/webhooks.py`（`AFTER_SALE_CREATED` 落 `after_sale_id`）
- `frontend/src/views/Orders.vue`（催单弹窗展示 sent/skipped）
- 测试：`backend/tests/test_slice1_refund.py`、`test_slice1_remind.py`

## 6. 不做（YAGNI / 后续切片）
- 催单真实外发到 vmall → 切片 2。
- 商户余额/佣金/提现（那是 vmall_system 的 REFACTOR_PLAN，另一项目）。
- taobao/jd 真实对接（无凭证，不可行）。
- 自动重试队列（本切片失败仅挂起 + 日志；重试机制留后续）。
