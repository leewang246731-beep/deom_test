# vMall 三方权责重构 — 实施设计（最终版）

> 本文档是 `docs/REFACTOR_PLAN_authority.md` 的**校正与定稿版**，为唯一实施依据。
> 原计划的诊断已逐条对照代码验证通过；本文档修正其机制错误并锁定决策。
> 日期：2026-06-29

## 1. 诊断结论（已对代码验证）

三方模型（平台 / 商户 / 买家）是正确的目标架构。已验证的核心缺陷：

| 缺陷 | 代码位置 | 状态 |
|---|---|---|
| 买家付款后钱凭空消失，无商户入账 | `consumer/orders.py::_async_pay` | 已证实 |
| 退款只回补买家，商户不被扣 | `admin/after_sales.py::confirm_receive` | 已证实 |
| admin 与 merchant 同时拥有发货权（重复 `paid→shipped`） | `admin/orders.py::ship_order` + `merchant/orders.py::ship_order` | 已证实 |
| admin 看所有订单无 `merchant_id` 过滤 | `admin/orders.py::list_orders` | 已证实（保留：监管需要） |
| 商户工作台无收益/余额 | `merchant/dashboard.py` | 已证实 |
| admin 代商户客服 | `admin/conversations.py` | 已证实 |

## 2. 对原计划的机制校正

1. **无需迁移脚本建表**：启动时 `main.py` 执行 `Base.metadata.create_all(checkfirst=True)`。
   新模型只需定义 + 在 `app/models/__init__.py` 注册即可自动建表。
   首单付款时 `_async_pay` 自动创建商户钱包，无需历史初始化脚本。
2. **服务为独立 :8020**（非 :8092，无 `saas-backend` 容器）。原计划端口/docker 命令作废。
3. **退款余额不足处理**：见决策（§3）——改为允许负余额，非"拒绝退款"。

## 3. 锁定决策

| 决策 | 结论 |
|---|---|
| 退款时商户余额不足 | **允许负余额**：商户钱包扣成负数（平台隐式垫付/记欠款），余额暴露给 admin 风控；买家始终拿到退款。不引入追偿状态机。 |
| 历史订单收益追溯 | **不追溯**，从上线起算。现有商户钱包 balance=0。 |
| admin 订单可见粒度 | 可看详情（金额/买家/物流）——现状已满足，保留。 |
| 提现审核 | **Phase 1 全人工**：admin approve/reject，线下打款后标记 completed。 |
| 平台佣金 | **本期不做**，留扩展点。 |

## 4. 数据模型（Phase 1，纯新增）

新增 `app/models/vm_merchant_wallet.py`，并在 `app/models/__init__.py` 注册。
`merchant_id` 用 `BigInteger` 对齐 `VmMerchant.id`（与 `VmOrder.merchant_id` Integer 比较兼容）。

### 4.1 `VmMerchantWallet` → 表 `vm_merchant_wallets`
- `id` BigInteger PK
- `merchant_id` BigInteger, unique, not null
- `balance` DECIMAL(12,2) default 0 — 可用余额（**允许负数**）
- `total_revenue` DECIMAL(12,2) default 0 — 累计订单实收
- `total_withdrawn` DECIMAL(12,2) default 0 — 累计提现
- `total_refunded` DECIMAL(12,2) default 0 — 累计退款支出
- `frozen` DECIMAL(12,2) default 0 — 提现申请中冻结金额
- `status` SmallInteger default 1 — 1正常 0冻结
- `created_at` / `updated_at`

### 4.2 `VmMerchantWalletTransaction` → 表 `vm_merchant_wallet_transactions`
- `id` BigInteger PK
- `wallet_id` BigInteger not null
- `merchant_id` BigInteger not null
- `type` String(20) — `order_income` / `refund_out` / `withdraw` / `adjustment`
- `amount` DECIMAL(12,2) — 正数表示入账方向，方向由 type 决定
- `balance_before` / `balance_after` DECIMAL(12,2)
- `order_no` String(30) nullable
- `remark` String(300) nullable
- `created_at`

### 4.3 `VmWithdrawalRequest` → 表 `vm_withdrawal_requests`
- `id` BigInteger PK
- `merchant_id` BigInteger not null
- `amount` DECIMAL(12,2) not null
- `account_type` String(20) — bank/alipay/wechat
- `account_info` String(500) — JSON 字符串
- `status` String(20) default `pending` — pending/approved/rejected/completed
- `operator_id` BigInteger nullable — 审核人
- `reject_reason` String(500) nullable
- `created_at` / `processed_at`

## 5. 钱流改造（Phase 2）

### 5.1 支付入账 — `consumer/orders.py::_async_pay`
在扣买家钱包、写买家 `payment` 流水之后、`order.status="paid"` 之前，于**同一事务**内：
- 查 `VmMerchantWallet(merchant_id=order.merchant_id)`，无则创建（balance=0）。
- `balance += pay_amount`，`total_revenue += pay_amount`。
- 写 `VmMerchantWalletTransaction(type="order_income", order_no=...)`，记 before/after。

原买家扣款逻辑完全不动。整体一次 `db.commit()`，保证原子性。

### 5.2 退款扣商户 — `admin/after_sales.py::confirm_receive`
在回补买家钱包**之前**，于同一事务内：
- 查/建商户钱包；记 `before`。
- `balance -= refund_amount`（**允许负数，不拦截**），`total_refunded += refund_amount`。
- 写 `VmMerchantWalletTransaction(type="refund_out", order_no=...)`。
- 余额转负时 `remark` 标注"平台垫付"，供 admin 风控识别。

原买家回补逻辑保留不变。

## 6. 商户收益模块（Phase 3，纯新增）

新增 `app/api/merchant/wallet.py`，在 `main.py` 注册到 `v1_routers`：
- `GET /merchant/wallet` — 余额、累计收益/提现/退款、冻结、状态。
- `GET /merchant/wallet/transactions` — 分页流水。
- `POST /merchant/wallet/withdraw` — 申请提现：校验 `amount <= balance-frozen`，创建 `pending` 申请，`frozen += amount`。

改造 `merchant/dashboard.py::dashboard`：`stats` 增加 `balance` / `today_revenue` / `frozen`（待提现）。

## 7. admin 职责调整（Phase 4）

- **删除 admin 发货**：移除 `admin/orders.py::ship_order` 路由（发货归商户）。
- **删除 admin 客服**：移除 `admin/conversations.py` 路由注册（日常客服归商户）。
- 保留 `GET /admin/orders` 列表与详情（只读监管）。
- 新增"强制发货"仲裁权：`POST /admin/orders/{id}/force-ship`，记 operator 审计。
- 保留买家钱包充值（官方权限）。
- 新增提现审核 `app/api/admin/withdrawals.py`：
  - `GET /admin/withdrawals?status=` 列表
  - `POST /admin/withdrawals/{id}/approve` — 扣商户 balance/frozen、写 `withdraw` 流水、`total_withdrawn +=`、标 completed
  - `POST /admin/withdrawals/{id}/reject` — 解冻 frozen、附原因、标 rejected
- 新增商户钱包监控 `GET /admin/merchant-wallets`（含负余额/冻结预警）。

> 注：`logistics.py` 强制更新留作仲裁用，本期不删（避免破坏物流模拟器）。

## 8. 前端适配（Phase 5）

- merchant 前端（`frontend_*`）：新增"钱包/收益"与"提现"页面。
- admin 前端：订单移除"发货"按钮（留强制发货/只读）；删除客服模块入口；新增"提现审核""商户钱包监控"。
- consumer 前端：钱包页提示"充值请走官方渠道"（不接真实支付网关）。

## 9. 验收（Phase 6 E2E）

完整链路：买家充值 → 下单付款 → **商户钱包入账** → 商户看到余额 → 商户发货 → 买家申请售后 → admin 审核 → 买家寄回 → admin 确认收货 → **商户钱包扣款（含负余额场景）** → 买家收到退款 → 商户申请提现 → admin 审核打款。

回归：现有买家付款/退款链路金额守恒；admin 不再能发货/客服；商户订单/商品/客服不受影响。

## 10. 阶段与提交边界

每个 Phase 独立提交、独立验收：
1. Phase 1 模型（建表，启动不报错，现有功能回归）
2. Phase 2 钱流（付款入商户、退款扣商户、负余额可发生）
3. Phase 3 商户收益模块（余额/流水/提现申请）
4. Phase 4 admin 收缩+新增（发货/客服移除、提现审核、钱包监控）
5. Phase 5 前端三端适配
6. Phase 6 E2E + 回归

## 11. 留作扩展（本期不做）
平台佣金抽成、真实支付网关、商户保证金、自动提现、风控规则。
