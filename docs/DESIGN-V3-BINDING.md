# DESIGN-V3: 多商户可视化绑定 & 租户隔离

**日期**: 2026-06-25
**状态**: 待实施
**前提**: DESIGN-V2-REFACTOR 已完成的 6 个阶段

---

## 1. 现状分析

### 1.1 问题全景

| # | 问题 | 严重度 | 位置 |
|---|------|--------|------|
| 1 | vMall 全局唯一 webhook URL（所有商户共享） | 致命 | `VmPlatformSetting` 单行表 |
| 2 | SaaS webhook 处理器硬编码 `.first()` → 永远路由到第一个 vmall 店铺 | 致命 | `webhooks.py:54,93,121` |
| 3 | vMall 绑定页面是假流程：仅本地写 `saas_bound=True`，从未调用 SaaS OpenAPI | 致命 | `Binding.vue` → `binding.py` |
| 4 | 会话同步不带 `saas_shop_id`，无法区分属于哪个 SaaS 租户 | 高 | `conversations.py:63-71` (vMall) |
| 5 | 订单/物流 webhook 同样不带 `saas_shop_id` | 高 | `conversations.py:42` (vMall) |
| 6 | vMall webhook dispatch 从全局设置读 URL，不区分商户 | 高 | `webhook.py:9-11` (vMall) |
| 7 | SaaS seed 只创建 1 个商户 + 2 个 mock 店铺，无 vmall 类型店铺 | 中 | `seed.py:36-41` |
| 8 | vMall seed 只创建 1 条 VmPlatformSetting | 中 | `seed_vmall.py:123-125` |
| 9 | SaaS Shops.vue 只提供 mock 选项，无 vmall 选项 | 中 | `Shops.vue:31-37` |
| 10 | SaaS→vMall 回复 relay 硬编码 `127.0.0.1:8020` | 中 | `conversations.py:120` (SaaS) |

### 1.2 根本原因

设计假设是"一个 SaaS 平台托管一个 vMall 实例"，但实际需求是：

```
SaaS 平台 (多租户)
├── Merchant A (数码旗舰店) → PlatformShop vmall-1 → 绑定 vMall merchant01
├── Merchant B (时尚女装馆) → PlatformShop vmall-2 → 绑定 vMall merchant02
└── Merchant C (潮流美妆坊) → PlatformShop vmall-3 → 绑定 vMall merchant03
```

当前代码中，所有的 `PlatformShop.platform_type == "vmall"` 查询都假设只有一条记录。

### 1.3 数据流断裂点

```
vMall merchant01 发消息
  → VmMessage 写入 (OK)
  → webhook.dispatch() → 读全局 VmPlatformSetting.saas_webhook_url (只有一个)
  → POST {event:"NEW_MESSAGE", data:{conversation_id:5, ...}}
  → SaaS webhooks.py _handle_message()
  → shop = db.query(PlatformShop).filter(platform_type="vmall").first()  ← BUG: 总是取第一个
  → 消息写到错误的租户
```

---

## 2. 方案设计

### 2.1 绑定流程（可视化三步）

```
┌──────────────────────────────────────────────────────────────┐
│  Step 1: SaaS 管理员生成绑定凭据                               │
│                                                              │
│  SaaS 管理后台 → 店铺管理 → 添加店铺                            │
│  选择平台类型: "vMall 虚拟电商"                                 │
│  输入店铺名称: "数码旗舰店"                                     │
│  系统自动生成:                                                 │
│    - PlatformShop (platform_type=vmall, bind_status=pending)  │
│    - bind_token: "vmall_a1b2c3d4e5f6" (唯一随机串)            │
│    - 显示: "请复制以下绑定码到 vMall 商户后台"                    │
│       ┌─────────────────────────────────────┐                 │
│       │  vmall_a1b2c3d4e5f6                 │  ← 一键复制     │
│       │  SaaS 地址: http://127.0.0.1:8010   │                 │
│       └─────────────────────────────────────┘                 │
│  等待绑定中... (bind_status=pending)                           │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 2: vMall 商户输入绑定码完成绑定                           │
│                                                              │
│  vMall 商户后台 → SaaS 绑定 → 输入绑定码                        │
│  ┌─────────────────────────────────────┐                      │
│  │  绑定码: [vmall_a1b2c3d4e5f6    ]   │                      │
│  │  SaaS地址: http://127.0.0.1:8010  │ ← 预填                │
│  │  [ 确认绑定 ]                       │                      │
│  └─────────────────────────────────────┘                      │
│                                                              │
│  点击确认 → vMall backend:                                    │
│    1. POST {token, shop_name, contact} → SaaS /openapi/confirm-bind │
│    2. SaaS 验证 token → 更新 PlatformShop:                     │
│         bind_status=active                                    │
│         shop_url=http://127.0.0.1:8020 (vMall backend)        │
│         app_key=vmall_merchant_01                             │
│    3. SaaS 返回 {saas_shop_id, saas_merchant_id}              │
│    4. vMall 写入 VmMerchant:                                  │
│         saas_bound=True                                       │
│         saas_shop_id=7                                        │
│         saas_url=http://127.0.0.1:8010                        │
│         saas_bind_time=now                                    │
└──────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────┐
│  Step 3: SaaS 管理后台确认绑定成功                              │
│                                                              │
│  店铺列表刷新 → bind_status 变成 active                        │
│  显示: "已绑定 vMall: 数码旗舰店 (merchant01)"                  │
│  可操作: 同步商品 | 同步订单 | 查看会话 | 解绑                    │
└──────────────────────────────────────────────────────────────┘
```

### 2.2 数据模型变更

#### SaaS 侧 — PlatformShop 新增字段

```python
# platform_shop.py 新增
bind_token = Column(String(64), nullable=True, unique=True, comment="vMall 绑定凭据")
bind_status = Column(String(20), default="idle", comment="idle/pending/active")
# idle: 未发起绑定
# pending: 已生成 token，等待 vMall 确认
# active: 绑定完成
```

#### vMall 侧 — VmMerchant 已有字段（无需变更）

```python
# 已有字段足够:
saas_bound = Column(Boolean, default=False)
saas_shop_id = Column(Integer, nullable=True)
saas_url = Column(String(500), nullable=True)
saas_bind_time = Column(DateTime, nullable=True)
```

#### vMall 侧 — VmPlatformSetting 保留作为全局默认，但 webhook 改为 per-merchant

```python
# 不变。但 dispatch() 不再只读全局 URL：
# 新增逻辑: 每个 VmMerchant 有独立的 saas_url → webhook URL = saas_url + /api/v1/webhooks/vmall
```

### 2.3 API 新增/变更

#### SaaS 新增 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/openapi/generate-bind-token` | 为指定 shop 生成 bind_token，返回 token + saas_url |
| POST | `/openapi/confirm-bind` | vMall 提交 token 确认绑定，返回 saas_shop_id |
| POST | `/shops/{id}/regenerate-token` | 重新生成 bind_token（管理后台按钮） |

#### vMall 新增/变更 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/merchant/binding/confirm` | 替换 `apply`，调用 SaaS confirm-bind |
| GET  | `/merchant/binding/status` | 不变，但增加 saas_shop_name, bind_status |

#### Webhook 修复

| 位置 | 变更 |
|------|------|
| `webhook.dispatch()` | 改为 per-merchant：从 VmMerchant.saas_url 构造 webhook URL |
| `webhooks.py` 全部 handler | 从 `data.saas_shop_id` 精确查找 PlatformShop |
| vMall 发送消息 API | webhook payload 增加 `saas_shop_id` |

### 2.4 租户隔离修正点

**所有 `PlatformShop.query.filter(platform_type="vmall").first()` 替换为 `PlatformShop.query.filter(id=data["saas_shop_id"]).first()`**

涉及文件:
- `backend/app/api/v1/webhooks.py` — 3 处：`_upsert_order`, `_handle_logistics`, `_handle_message`
- `backend/app/api/v1/conversations.py` — 1 处：relay 回 vMall 时从 shop.shop_url 取地址

### 2.5 数据隔离关系

```
SaaS:
  Merchant(id=1) "数码旗舰商户"
    └── PlatformShop(id=10, platform_type=vmall, bind_token="xxx", bind_status=active)
         └── ExternalProduct (shop_id=10)  ← 从 vMall 同步
         └── ExternalOrder (shop_id=10)     ← 从 vMall 同步
         └── Conversation (shop_id=10)      ← 从 vMall webhook 写入

  Merchant(id=2) "时尚女装商户"
    └── PlatformShop(id=11, platform_type=vmall, bind_token="yyy", bind_status=active)
         └── ...

vMall:
  VmMerchant(id=1) → saas_shop_id=10, saas_url=8010
  VmMerchant(id=2) → saas_shop_id=11, saas_url=8010
  VmMerchant(id=3) → saas_bound=False (未绑定)

webhook dispatch per merchant:
  merchant01 → POST http://127.0.0.1:8010/api/v1/webhooks/vmall  {saas_shop_id:10, ...}
  merchant02 → POST http://127.0.0.1:8010/api/v1/webhooks/vmall  {saas_shop_id:11, ...}
```

---

## 3. 实施计划

### Phase 1: 数据模型 (1 文件) (T+15min)

**目标**: 添加 bind_token / bind_status 字段

- [ ] `backend/app/models/platform_shop.py` — 新增 `bind_token` (String 64, unique), `bind_status` (String 20, default "idle")
- [ ] `vmall_system/backend/app/models/vm_platform_setting.py` — 不修改，保留作为"默认值"
- [ ] 执行 ALTER TABLE SQL 或重建表

**验证**: `python -c "from app.models.platform_shop import PlatformShop; print('OK')"`

### Phase 2: SaaS OpenAPI 绑定端点 (1 文件) (T+30min)

**目标**: 实现 generate-bind-token + confirm-bind

- [ ] `backend/app/api/v1/openapi.py` — 新增:
  - `POST /openapi/generate-bind-token` (需 JWT 鉴权，admin/manager)
    - 入参: `{shop_id}`
    - 生成 `secrets.token_urlsafe(24)` → `bind_token`
    - 更新 PlatformShop: bind_token + bind_status="pending"
    - 返回: `{bind_token, saas_url}`
  - `POST /openapi/confirm-bind` (API Key 鉴权)
    - 入参: `{bind_token, shop_name, contact_phone, vmall_url}`
    - 校验 token → 找到 PlatformShop
    - 更新: bind_status="active", shop_url=vmall_url
    - 返回: `{saas_shop_id, saas_merchant_id, shop_name}`

**验证**: Swagger UI 调用两个端点，确认 token 流

### Phase 3: vMall merchant 绑定 API (1 文件) (T+30min)

**目标**: 替换假 binding 为真实调用 SaaS

- [ ] `vmall_system/backend/app/api/merchant/binding.py` — 修改:
  - `POST /merchant/binding/confirm` 替换 `apply`
    - 入参: `{bind_token, saas_url}`
    - 调用 SaaS `POST {saas_url}/api/v1/openapi/confirm-bind`
    - 写入 VmMerchant: saas_bound=True, saas_shop_id, saas_url, saas_bind_time
    - 更新 VmPlatformSetting.saas_webhook_url（如果尚未设置）
  - `GET /merchant/binding/status` — 增加 `bind_status` 字段
  - `DELETE /merchant/binding` — 解绑时通知 SaaS 重置 bind_status

**验证**: merchant01 使用 token 完成绑定，检查 VmMerchant 字段

### Phase 4: Webhook per-merchant 路由 (3 文件) (T+45min)

**目标**: webhook payload 带 saas_shop_id，SaaS 端精确路由

- [ ] `vmall_system/backend/app/services/webhook.py` — 修改:
  - `dispatch()` 不再只读全局 URL
  - 新增 `dispatch_for_merchant(merchant_id, event_type, payload)`
  - 从 VmMerchant.saas_url 构造 webhook URL
  - payload 自动注入 `saas_shop_id`
- [ ] `vmall_system/backend/app/api/consumer/conversations.py` — 修改:
  - `send_message()` 的 webhook payload 增加 `saas_shop_id`、`merchant_id`
  - `_get_buyer` 改为返回 `(buyer_id, merchant_id)`
- [ ] `backend/app/api/v1/webhooks.py` — 修改全部 3 个 handler:
  - `_upsert_order()` — `shop_id = data.get("saas_shop_id")` → 精确查询
  - `_handle_logistics()` — 同上
  - `_handle_message()` — 同上
- [ ] `backend/app/api/v1/conversations.py` — 修改 relay:
  - `send_conversation_message()` — 从 `shop.shop_url` 取 vMall 地址，不再硬编码

**验证**: merchant01 发消息 → SaaS 确认出现在正确的 Conversation (shop_id=10)

### Phase 5: 前端 — SaaS 管理后台绑定面板 (2 文件) (T+45min)

**目标**: 生成 token、显示绑定状态、支持重新生成

- [ ] `frontend/src/views/Shops.vue` — 修改:
  - 平台选择增加 "vMall 虚拟电商" 选项
  - 绑定后显示 bind_status 标签 (pending→黄色, active→绿色)
  - vmall 类型店铺展示额外操作栏: [查看绑定码] [重新生成] [解绑]
  - 点击"查看绑定码"弹出 dialog 显示 token + 一键复制
- [ ] `frontend/src/api/index.js` — 新增:
  - `generateBindToken(shopId)` → `POST /shops/{shopId}/bind-token`
  - `regenerateBindToken(shopId)` → `POST /shops/{shopId}/regenerate-token`

**验证**: 管理后台创建 vmall 店铺，复制 token

### Phase 6: 前端 — vMall 商户绑定面板 (2 文件) (T+30min)

**目标**: 输入 token 完成可视化绑定

- [ ] `vmall_system/frontend_merchant/src/views/Binding.vue` — 重写:
  - 默认显示绑定状态卡片: 未绑定 / 已绑定(显示 SaaS 店铺名)
  - "申请绑定" → 弹出 dialog: 输入 bind_token + saas_url（预填）
  - 确认 → 调用 `POST /merchant/binding/confirm`
  - 已绑定状态显示: SaaS 店铺名、绑定时间、[解绑按钮]
- [ ] `vmall_system/frontend_merchant/src/api/index.js` — 新增:
  - `confirmBinding(data)` → `POST /merchant/binding/confirm`

**验证**: merchant01 输入 token，完成绑定，状态卡片变为绿色

### Phase 7: Seed 数据多租户化 (2 文件) (T+30min)

**目标**: seed 创建 3 个 SaaS 商户 + 3 个 vmall 店铺 + 正确的绑定关系

- [ ] `backend/seed.py` — 修改:
  - 创建 3 个 Merchant: "数码旗舰商户" / "时尚女装商户" / "潮流美妆商户"
  - 每个 Merchant 创建 1 个 PlatformShop(platform_type=vmall, bind_status=active)
  - 每个 Merchant 创建 admin/manager/service 账号
  - 每个 Merchant 创建 5-8 条 Mock 会话（模拟已有消费者咨询）
- [ ] `vmall_system/backend/seed_vmall.py` — 修改:
  - 3 个 VmMerchant 预绑定:
    - merchant01 → saas_shop_id=第1个, saas_url=http://127.0.0.1:8010
    - merchant02 → saas_shop_id=第2个, saas_url=http://127.0.0.1:8010
    - merchant03 → 不绑定 (saas_bound=False)
  - VmPlatformSetting 保留全局 webhook URL 作为默认值

**验证**: 分别用 admin@merchant1 / admin@merchant2 登录，看到不同的店铺和会话

### Phase 8: 集成测试 (T+30min)

**目标**: 端到端验证绑定 + 同步

- [ ] 用 admin/123456 登录 SaaS :8092 → 切换商户 → 确认看到 3 个商户
- [ ] 每个商户有对应的 vmall 店铺 + bind_token
- [ ] merchant01 (:8093) 已完成绑定 → SaaS :8094 能看到 merchant01 的会话
- [ ] 消费者 (:8090) 在 merchant01 商品下联系客服
  → 消息出现在 SaaS :8094 的"数码旗舰商户"会话列表
- [ ] 客服回复 → 消费者 Chat.vue 看到回复
- [ ] merchant02 的会话只在 SaaS 商户2 下可见，不会串到商户1
- [ ] 管理后台 :8092 修改客服模式 → :8094 刷新后同步

---

## 4. 影响范围汇总

| 系统 | 新增 | 修改 | 文件列表 |
|------|------|------|----------|
| SaaS 后端 | 2 端点 | 3 文件 | `openapi.py`, `webhooks.py`, `conversations.py`, `shops.py` |
| vMall 后端 | 1 端点 | 3 文件 | `binding.py`, `webhook.py`, `conversations.py` |
| SaaS 前端 | 1 组件 | 2 文件 | `Shops.vue`, `api/index.js` |
| vMall 商户前端 | 0 | 2 文件 | `Binding.vue`, `api/index.js` |
| 数据模型 | 2 列 | 1 文件 | `platform_shop.py` |
| Seed | — | 2 文件 | `seed.py`, `seed_vmall.py` |

**总计: 17 文件, 预计 4 小时**

## 5. 风险与注意事项

1. **ALB 兼容** — `bind_token` 新增字段需要 database migration。开发环境直接 ALTER TABLE 或重建。
2. **Webhook 回调幂等** — confirm-bind 需支持重复调用（同一 token 已 active 时返回现有数据）。
3. **解绑安全** — 解绑时需同时重置 SaaS 侧 `bind_status=idle` 和清空 token，防止被其他商户误绑。
4. **会话迁移** — 已存在的会话不迁移。绑定后新消息才开始同步。
5. **回退路径** — 所有变更都是增量式的，不影响现有 mock 店铺和独立运行的 vMall。
