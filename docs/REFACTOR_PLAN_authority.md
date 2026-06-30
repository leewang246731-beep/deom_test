# vMall 权责重构方案 — 三方模型诊断与实施计划

## 一、现状诊断 — 权责混乱的根本问题

### 当前架构的致命缺陷

**错误的两方模型**：现有 vMall 把"平台运营"和"商户"强行塞进两个后端，但**钱包/订单收益/商品所有权的归属逻辑完全错位**。

| 实体 | 当前归属 | 问题 |
|---|---|---|
| **VmWallet** | `buyer_id` 外键 → 买家钱包 | ✅ 正确 |
| **钱包充值权** | admin 后台 `POST /admin/wallets/{buyer_id}/recharge` | ❌ **运营后台不该直接操作买家钱**（应该是官方平台权限） |
| **VmOrder** | `merchant_id` 字段标识商户所有 | ✅ 归属正确 |
| **订单收益流向** | 买家付款 → 扣买家钱包 → **钱消失**（未进商户账户） | ❌ **商户没收到钱，钱去哪了？** |
| **VmProduct** | `merchant_id` 外键 → 商户商品 | ✅ 正确 |
| **商户收益可见性** | merchant dashboard 只显示订单数，**无收益金额/余额** | ❌ 商户看不到自己赚了多少 |
| **退款资金来源** | 从买家钱包原路退回 | ✅ 流程对，但商户没"被扣款"（因为本就没入账） |
| **admin/merchant 发货权重叠** | admin 和 merchant **都能发货同一订单** | ❌ 职责不清：谁该发货？ |
| **admin 能看/操作所有商户订单** | `GET /admin/orders` 无 merchant_id 过滤 | ❌ 越界：运营不该直接操作商户订单细节 |

---

## 二、目标三方模型 — 你的预设逻辑（正确）

```
┌─────────────────┐
│  官方平台运营方  │  (admin 后台 :8092)
│  VmPlatform     │  - 平台级钱包充值（买家消费余额的注资方）
└────────┬────────┘  - 商户入驻审核
         │           - 平台佣金抽成（可选）
         │           - 仲裁纠纷、管控风险
    ┌────┴────┐
    │         │
┌───▼──┐  ┌──▼───────┐
│ 商户  │  │ 买家      │
│Merch.│  │Consumer  │
└──────┘  └──────────┘
  owns:      owns:
  - 商品       - 消费钱包
  - 店铺收益账户  - 订单(buyer_id)
  - 订单收入
  (merchant_id)

  操作:       操作:
  - 上架/定价   - 浏览/下单/支付
  - 发货       - 申请售后
  - 查看收益   - 充值(via 官方渠道)
  - 提现(to 真实账户)
```

### 核心原则（你的预设，完全正确）

1. **买家钱包充值** → 只能由**官方平台运营方**操作（代表第三方支付/银行入金）。商户、买家本人都不能自己"凭空造钱"。
2. **商户收益账户** → 商户有自己的"店铺钱包"，订单付款后钱进**商户账户**，商户可见余额、可提现。
3. **退款资金来源** → 从**商户店铺账户**扣，退回买家钱包（商户承担退款成本）。若商户余额不足，官方垫付后向商户追偿，或拒绝退款。
4. **发货权** → 只有**商户**能发货自己的订单；官方平台只做"监督/强制发货"等特殊干预。
5. **订单可见性** → 官方平台能"看"所有订单（监管），但日常**不直接操作**（发货/改价/取消等由商户做）；平台只处理**投诉/仲裁**。

---

## 三、现有功能模块清单与职责划分诊断

### 3.1 当前 admin 后台（运营）功能

| 模块 | 端点 | 当前职责 | 问题 | 目标职责 |
|---|---|---|---|---|
| 订单管理 | `GET /admin/orders`<br>`POST /{id}/ship` | 看所有订单、**直接发货** | ❌ 越权操作商户订单 | **只读监控** + 异常订单仲裁/强制操作 |
| 售后审核 | `POST /after-sales/{id}/review`<br>`POST /{id}/confirm-receive` | 审核退款、确认收货退款 | ⚠️ 合理，但退款应扣商户账户 | 保留（改为扣商户钱包） |
| 物流 | `POST /logistics/{id}/ship`<br>`/{id}/advance`<br>`/{id}/exception` | 更新物流状态 | ❌ 应该是商户/快递回调做 | 移除或改为"强制更新"（仲裁用） |
| 会话 | `GET /admin/conversations`<br>`POST /{id}/messages` | 看所有会话、代商户回复 | ❌ 越权；客服是商户职责 | **删除**（平台不参与日常客服） |
| **钱包** | `GET /wallets`<br>`POST /{buyer_id}/recharge`<br>`GET /{buyer_id}/transactions` | 买家钱包充值、查流水 | ✅ 充值权对；但缺商户钱包 | 保留买家钱包充值；**新增商户钱包管理** |
| 仪表盘 | `GET /admin/dashboard` | 平台整体统计 | ✅ 合理 | 保留 |
| 设置 | `PUT /admin/settings` | 平台配置 | ✅ 合理 | 保留 |

### 3.2 当前 merchant 后台（商户）功能

| 模块 | 端点 | 当前职责 | 问题 | 目标职责 |
|---|---|---|---|---|
| 商品 | `GET/POST/PUT/DELETE /merchant/products` | 商品 CRUD | ✅ 正确 | 保留 |
| 订单 | `GET /merchant/orders`<br>`GET /{id}`<br>`POST /{id}/ship` | 看自己的订单、发货 | ✅ 正确 | 保留 |
| 会话 | `GET /conversations`<br>`POST /{id}/messages` | 看自己的客服会话、回复 | ✅ 正确 | 保留 |
| 仪表盘 | `GET /dashboard` | 统计订单数 | ⚠️ **缺收益金额/余额** | **新增：店铺收益账户余额、今日收入、可提现金额** |
| 绑定 SaaS | `GET /binding/status`<br>`POST /confirm`<br>`DELETE /` | 托管绑定 | ✅ 正确 | 保留 |
| 设置 | `GET/PUT /settings` | 店铺设置 | ✅ 正确 | 保留 |
| **收益/提现** | ❌ **不存在** | — | ❌ **商户看不到钱、取不出钱** | **新增：钱包余额、收益明细、提现申请** |

### 3.3 consumer 后台（买家）

| 模块 | 当前职责 | 问题 | 目标 |
|---|---|---|---|
| 商品浏览/下单/支付 | ✅ 正确 | 无 | 保留 |
| 钱包 | `GET /wallet` 只读 | ⚠️ **买家不能自己充值**（对，应由官方充） | 保留只读；充值入口指向"官方充值渠道"（第三方支付） |
| 售后 | 申请退款/退货 | ✅ 正确 | 保留 |
| 会话 | 发起咨询 | ✅ 正确 | 保留 |

---

## 四、重构实施计划 — 分阶段、不破坏现有功能

### Phase 1：数据模型扩展（新增商户钱包，不动现有表）

**目标**：让商户有"收钱的地方"，订单付款后钱有去处。

#### 1.1 新增表 `vm_merchant_wallets`（商户店铺钱包）

```sql
CREATE TABLE vm_merchant_wallets (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  merchant_id INT NOT NULL UNIQUE COMMENT '商户ID',
  balance DECIMAL(12,2) DEFAULT 0 COMMENT '可用余额(已结算收入-提现-退款)',
  total_revenue DECIMAL(12,2) DEFAULT 0 COMMENT '累计总收入(所有订单实收)',
  total_withdrawn DECIMAL(12,2) DEFAULT 0 COMMENT '累计提现',
  total_refunded DECIMAL(12,2) DEFAULT 0 COMMENT '累计退款支出',
  status TINYINT DEFAULT 1 COMMENT '1:正常 0:冻结',
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  INDEX idx_merchant (merchant_id)
);
```

#### 1.2 新增表 `vm_merchant_wallet_transactions`（商户钱包流水）

```sql
CREATE TABLE vm_merchant_wallet_transactions (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  wallet_id BIGINT NOT NULL COMMENT '商户钱包ID',
  merchant_id INT NOT NULL,
  type VARCHAR(20) NOT NULL COMMENT 'order_income/refund_out/withdraw/adjustment',
  amount DECIMAL(12,2) NOT NULL,
  balance_before DECIMAL(12,2) NOT NULL,
  balance_after DECIMAL(12,2) NOT NULL,
  order_no VARCHAR(30) NULL COMMENT '关联订单号',
  remark VARCHAR(300) NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_wallet (wallet_id),
  INDEX idx_merchant (merchant_id),
  INDEX idx_order (order_no)
);
```

#### 1.3 新增表 `vm_withdrawal_requests`（商户提现申请）

```sql
CREATE TABLE vm_withdrawal_requests (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  merchant_id INT NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  account_type VARCHAR(20) NOT NULL COMMENT 'bank/alipay/wechat',
  account_info VARCHAR(500) NOT NULL COMMENT '收款账户信息(JSON)',
  status VARCHAR(20) DEFAULT 'pending' COMMENT 'pending/approved/rejected/completed',
  operator_id INT NULL COMMENT '审核人(平台运营)',
  reject_reason VARCHAR(500) NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  processed_at DATETIME NULL,
  INDEX idx_merchant_status (merchant_id, status)
);
```

#### 1.4 迁移脚本 `migrations/add_merchant_wallet.py`

```python
# 为现有商户初始化钱包,balance=0(历史订单不追溯,从上线时刻起算)
# 执行: docker exec saas-backend python migrations/add_merchant_wallet.py
```

---

### Phase 2：支付/退款流改造（钱流向商户账户）

**不破坏现有逻辑，在旁路并行写入商户钱包，验证后切主路径。**

#### 2.1 支付流改造 `consumer/orders.py::_async_pay`

**现状**：扣买家钱包 → 钱消失。

**目标**：扣买家钱包 → **同时入商户钱包** → 写商户流水(`order_income`)。

```python
# 原有:扣买家
wallet.balance = before - order.pay_amount
wallet.total_spent += order.pay_amount
db.add(VmWalletTransaction(..., type="payment"))

# 新增:入商户(Phase2开始并行写)
from app.models.vm_merchant_wallet import VmMerchantWallet, VmMerchantWalletTransaction
m_wallet = db.query(VmMerchantWallet).filter(VmMerchantWallet.merchant_id == order.merchant_id).first()
if not m_wallet:  # 首单自动建钱包
    m_wallet = VmMerchantWallet(merchant_id=order.merchant_id, balance=0, ...)
    db.add(m_wallet); db.flush()
m_before = m_wallet.balance
m_wallet.balance += order.pay_amount
m_wallet.total_revenue += order.pay_amount
db.add(VmMerchantWalletTransaction(
    wallet_id=m_wallet.id, merchant_id=order.merchant_id, type="order_income",
    amount=order.pay_amount, balance_before=m_before, balance_after=m_wallet.balance,
    order_no=order.order_no, remark=f"订单收入"))
```

#### 2.2 退款流改造 `admin/after_sales.py::confirm_receive`

**现状**：只回补买家钱包。

**目标**：**先扣商户钱包**（`refund_out`），再回补买家；商户余额不足则拒绝/官方垫付。

```python
# 扣商户
m_wallet = db.query(VmMerchantWallet).filter(...).first()
if m_wallet.balance < a.refund_amount:
    raise HTTPException(400, detail={"code":40001, "msg":"商户余额不足,退款失败(需平台介入)"})
m_before = m_wallet.balance
m_wallet.balance -= a.refund_amount
m_wallet.total_refunded += a.refund_amount
db.add(VmMerchantWalletTransaction(..., type="refund_out", amount=a.refund_amount, ...))

# 回补买家(已有逻辑保留)
wallet.balance += a.refund_amount
...
```

---

### Phase 3：merchant 后台新增收益模块

#### 3.1 新增 `merchant/wallet.py`

```python
@router.get("/merchant/wallet")
def my_wallet(authorization: str = Header(None), db: Session = Depends(get_db)):
    """商户查看自己的店铺钱包余额、累计收益。"""
    merchant = _get_merchant(authorization)
    mid = int(merchant["sub"])
    w = db.query(VmMerchantWallet).filter(VmMerchantWallet.merchant_id == mid).first()
    if not w:
        return ok({"balance": 0, "total_revenue": 0, "total_withdrawn": 0, "total_refunded": 0})
    return ok({
        "balance": float(w.balance),
        "total_revenue": float(w.total_revenue),
        "total_withdrawn": float(w.total_withdrawn),
        "total_refunded": float(w.total_refunded),
        "status": w.status,
    })

@router.get("/merchant/wallet/transactions")
def my_transactions(page: int = 1, page_size: int = 20, ...):
    """商户查看自己的钱包流水(收入/退款/提现)。"""
    ...

@router.post("/merchant/wallet/withdraw")
def apply_withdraw(body: dict, ...):
    """商户申请提现(到银行卡/支付宝等)。"""
    amount = body["amount"]
    if amount > wallet.balance:
        raise HTTPException(400, ...)
    db.add(VmWithdrawalRequest(merchant_id=mid, amount=amount, account_info=body["account"], status="pending"))
    # 冻结对应余额(可选:扣balance或加frozen_balance字段)
    ...
```

#### 3.2 改造 `merchant/dashboard.py`

新增收益数据:

```python
"stats": {
    "balance": float(wallet.balance),          # 当前余额
    "today_revenue": ...,                      # 今日收入
    "pending_withdraw": ...,                   # 待提现金额
    ...
}
```

---

### Phase 4：admin 后台职责收缩与新增

#### 4.1 **删除** admin 直接操作商户订单的权限

- `POST /admin/orders/{id}/ship` → **删除**（只有商户能发货）。
- `POST /admin/logistics/{id}/ship` → **删除**。
- 保留 `GET /admin/orders`（只读监控）。

**替代方案**：新增"强制发货"权限（仲裁用）：

```python
@router.post("/admin/orders/{id}/force-ship")  # 需审计日志
def force_ship(...):
    """平台强制发货(投诉/商户失联等极端场景),记录操作人。"""
```

#### 4.2 **删除** admin 客服模块

- `GET /admin/conversations` → **删除**。
- `POST /admin/conversations/{id}/messages` → **删除**。

客服是商户职责，平台不参与日常接待。

#### 4.3 **新增** 商户提现审核

```python
@router.get("/admin/withdrawals")
def list_withdrawals(status: str = None, ...):
    """平台查看所有商户提现申请。"""

@router.post("/admin/withdrawals/{id}/approve")
def approve_withdraw(id: int, ...):
    """审核通过→扣商户余额→线下打款→标记completed。"""

@router.post("/admin/withdrawals/{id}/reject")
def reject_withdraw(id: int, body: dict, ...):
    """驳回提现(附原因)。"""
```

#### 4.4 保留/增强买家钱包充值

```python
@router.post("/admin/wallets/{buyer_id}/recharge")  # 保留
@router.get("/admin/wallets")  # 保留(只看买家钱包)
# 新增:商户钱包只读(监管用)
@router.get("/admin/merchant-wallets")
def list_merchant_wallets(...):
    """平台查看所有商户钱包状态(监控/风控)。"""
```

---

### Phase 5：前端适配

#### 5.1 merchant 前端 (:8091) 新增页面

- **钱包/收益** → 显示余额、今日收入、累计收益、流水明细。
- **提现管理** → 申请提现、查看提现记录/状态。

#### 5.2 admin 前端 (:8092) 改造

- **订单管理** → 移除"发货"按钮（只读+仲裁按钮）。
- **客服管理** → **整个模块删除**。
- **提现审核** → 新增页面：待审核列表、审核操作。
- **商户钱包监控** → 新增：查看各商户余额/异常（风控）。

#### 5.3 consumer 前端 (:8090) 微调

- 钱包页提示"充值请联系平台客服/使用官方充值渠道"（Phase1 不做真实支付网关对接，后续扩展）。

---

## 五、实施路径与里程碑

| 阶段 | 工作量 | 验收标准 | 风险 |
|---|---|---|---|
| **Phase 1 数据模型** | 1-2 天 | 表创建、迁移脚本跑通、现有功能不受影响 | 低（纯新增） |
| **Phase 2 钱流改造** | 2-3 天 | 新订单付款后商户钱包入账；退款扣商户钱包；旧逻辑并行运行 | 中（核心金额逻辑） |
| **Phase 3 merchant 收益模块** | 2-3 天 | 商户能看余额/流水、能申请提现（pending 状态） | 低（纯新增） |
| **Phase 4 admin 职责收缩** | 1-2 天 | admin 不能直接发货/客服；能审核提现 | 低（删代码+新增审核） |
| **Phase 5 前端适配** | 3-4 天 | 三个前端按新模块改造 | 中（UI 工作量大） |
| **Phase 6 E2E 测试** | 1-2 天 | 完整流程：买家付款→商户收钱→商户提现→admin审核→退款扣商户 | 高（集成验证） |

**总计**：10-16 天（按顺序分阶段，每阶段独立验收）。

---

## 六、不删除后端功能 — 改造而非砍

按你的要求，**所有现有后端功能保留**，只做职责归属调整：

| 当前功能 | 处理方式 |
|---|---|
| admin 发货 | **移到 merchant**（admin 只留"强制发货"仲裁权） |
| admin 客服 | **移到 merchant**（admin 完全退出日常客服） |
| admin 钱包充值 | **保留**（官方权限） |
| merchant 订单/商品/客服 | **保留**（职责正确） |
| consumer 所有功能 | **保留**（职责正确） |
| 新增：商户钱包/提现/收益 | Phase 1-3 实现 |
| 新增：admin 提现审核/商户钱包监控 | Phase 4 实现 |

---

## 七、后续扩展点（本次不做，留接口）

1. **平台佣金抽成**：订单完成后从商户收入中扣 X%佣金到平台账户。
2. **真实支付网关**：买家充值接第三方支付（支付宝/微信）。
3. **商户保证金**：入驻时冻结保证金，用于退款/罚款。
4. **自动提现**：商户余额达阈值自动发起提现。
5. **风控规则**：异常退款率/余额不足预警。

---

## 八、需要你确认的决策点

| 决策 | 选项 A | 选项 B | 建议 |
|---|---|---|---|
| 历史订单收益追溯？ | 回溯计算历史订单,初始化商户钱包余额 | 从重构上线时刻起算,历史订单不追溯 | **选 B**（数据一致性风险低） |
| 商户余额不足时退款？ | 拒绝退款(买家申诉) | 平台垫付,后向商户追偿 | **选 A**（简单;B 需账期/追偿流程） |
| admin "看订单"粒度？ | 只能看统计/列表 | 能看订单详情(金额/买家/物流) | **选后者**（监管需要） |
| 提现审核是否自动？ | 人工审核每笔 | 小额自动通过,大额人工 | **Phase1 人工;Phase2+ 自动** |
| 平台佣金本次做吗？ | 做(Phase2 入账时扣) | 不做(后续扩展) | **不做**（先理顺钱流） |

---

**本文档状态**：待你确认决策点 + 批准实施。确认后我按 Phase 1→2→3→4→5→6 顺序实施，每个 Phase 独立提交+验证。
