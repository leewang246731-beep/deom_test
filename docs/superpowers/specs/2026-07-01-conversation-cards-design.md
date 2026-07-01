# 子项目 A：会话卡片 + 订单实时同步 — 设计文档

日期：2026-07-01
状态：待评审

## 背景与目标

消费者从商品页进入客服会话后，聊天窗口只能收发纯文本，无法发送**商品链接**或**订单链接**。这导致无法验证「商品推荐」以及「售前 / 售中 / 售后」全流程的客服话术。

本子项目让会话支持两种结构化卡片消息——**商品卡片**、**订单卡片**——双向收发并渲染成可点击 UI；同时补全 vmall → SaaS 的订单实时同步，使客服端能看到买家的真实订单。

**不在本子项目范围**（属于子项目 B / C）：
- 图片消息、本地文件上传、静态文件服务（子项目 B 基建 + 子项目 C 接入）
- 卡片编辑、订单详情页、图片消息

## 术语

- **SaaS**：托管客服平台，后端 `backend/`（:8012），客服工作台前端 `frontend/`（:8095）
- **vmall**：电商系统，后端 `vmall_system/backend/`（:8020），买家 H5 `frontend_consumer/`（:8090）
- **card 信封**：承载结构化消息的统一 JSON 格式（见下）

## 数据模型

无需数据库迁移。复用现有 JSON 字段：
- vmall `VmMessage.msg_type`（已预留 `product_card`）+ `content_json`
- SaaS `Conversation.messages_json`（每条消息一个 dict）

### card 信封格式（统一）

每条卡片消息在原有 `{text}` 基础上增加可选 `card` 字段。`text` 作为降级文本，保证老客户端和不识别卡片的地方仍能显示：

```jsonc
// 商品卡片
{
  "text": "为您推荐这款商品",
  "card": {
    "type": "product",
    "product_id": 785,        // vmall 商品 ID（用于前端跳转 /product/:id）
    "title": "乳胶床垫1.8m",
    "price": 1599.00,
    "image": "http://.../xxx.jpg",
    "link": "/product/785"
  }
}

// 订单卡片
{
  "text": "这是您的订单 VM-xxx",
  "card": {
    "type": "order",
    "order_no": "VM-xxx",
    "status": "shipped",
    "amount": 1599.00,
    "link": "/orders"
  }
}
```

### 关键：商品 ID 还原

SaaS 侧存的是 `ExternalProduct.id`（如 571），但 vmall 消费者路由是 `/product/785`。生成卡片时必须把 `ExternalProduct.platform_product_id`（`"vm_785"`）去掉 `vm_` 前缀还原成 vmall 的 785，否则跳转错误。SaaS→买家发商品卡片时在后端完成还原后写入 `card.product_id` / `card.link`。

## 架构：四个方向的落点

### A. 客服 → 买家 发商品卡片
- **SaaS 前端** `frontend/src/views/Service.vue`：右侧「推荐商品」面板已有「发送商品卡片」按钮，当前发纯文本 `[商品推荐] ...`。改为构造 card 信封发送。
- **SaaS 后端** `backend/app/api/v1/conversations.py` `send_conversation_message`：接受请求体可选 `card` 字段 → 存入 `messages_json` → 回流 vmall internal API 时带上 `card`。商品 ID 还原在此完成。
- **vmall 后端** `consumer/conversations.py` `receive_saas_reply`（internal 接收端）：把 `card` 存入 `VmMessage.content_json`，`msg_type` 设为 `product_card`。

### B. 客服 → 买家 发订单卡片
- **SaaS 前端** `Service.vue`：右侧新增「买家订单」面板，列出当前会话买家的订单，点击某订单发订单卡片。
- **SaaS 后端**：新增接口 `GET /conversations/{id}/buyer-orders` — 返回该会话买家的订单列表（数据源 `ExternalOrder`，按 `buyer_nick` 尽力匹配会话买家；匹配不到则返回该店铺近期订单）。复用同一条 card 发送链路。

### C. 买家 → 客服 带商品 / 订单咨询
- **vmall 前端** `frontend_consumer/src/views/Chat.vue`：顶部商品卡片旁加「咨询此商品」按钮 → 发一条 product_card 消息；加「关联我的订单」→ 弹窗选订单 → 发 order_card 消息（买家从**自己的** `vm_orders` 选，数据干净）。
- **vmall 后端** `consumer/conversations.py`：
  - `send_message` 接受 `card` → 存入 `VmMessage.content_json` → dispatch webhook 时带 `card`。
  - 买家选订单**复用现有** `GET /consumer/orders`（前端 `getMyOrders`），无需新增。
- **SaaS 后端** `webhooks.py` `_handle_message`：把 webhook data 里的 `card` 存入 `messages_json` 对应消息。

### D. 双方渲染卡片
- **vmall Chat.vue**：消息渲染时 `if (msg.content_json?.card)` 走卡片 UI（商品卡片→点击 `router.push('/product/'+product_id)`；订单卡片→ `/orders`），否则走纯文本。
- **SaaS Service.vue**：聊天窗口消息渲染时 `if (msg.card)` 走卡片 UI，让客服能看到买家带来的商品/订单，也能看到自己发出的卡片。

## 订单实时同步（补全已有链路）

### 现状（已存在）
- vmall 已 dispatch：`ORDER_PAID`（`consumer/orders.py:106`，支付成功）、`ORDER_SHIPPED`（`merchant/orders.py:73`，商户发货）、`AFTER_SALE_CREATED`（`after_sales.py:32`）
- SaaS `webhooks.py` `_upsert_order` 已接收入库到 `ExternalOrder`

### 要补 / 修
1. **`_order_json` 补 `buyer_nick`**（`vmall consumer/orders.py:111`）：当前 payload 只有 `buyer_id` 没有 `buyer_nick`，导致同步到 SaaS 的订单没有买家名 → 客服端订单卡片按 `buyer_nick` 匹配会话买家时匹配不到。补上买家昵称查询后写入 payload。
2. **校验 `_upsert_order` 的 product 关联**（`SaaS webhooks.py:132`）：沿用 `vm_{id}` 还原逻辑，确保订单里的 `sku_details` product_id 能被前端正确用于展示，避免与会话 product_id 同类的错配 bug。

## 数据流示例

**售前**（买家咨询 → 客服推荐）：
```
买家在床垫会话点「咨询此商品」
  → vmall send_message(card: product/785) → webhook → SaaS _handle_message 存 card
  → 客服工作台聊天窗口渲染出商品卡片（看到买家在问床垫）
  → 客服点 AI 推荐里的「发送商品卡片」
  → SaaS send_conversation_message(card, 还原 vm id) → 回流 vmall
  → 买家 Chat.vue 渲染出可点卡片 → 点击跳 /product/785  ✅
```

**售中/售后**（订单相关）：
```
买家下单支付 → vmall dispatch ORDER_PAID(含 buyer_nick) → SaaS _upsert_order 入库
  → 客服「买家订单」面板列出该买家订单
  → 客服点订单 → 发订单卡片 → 买家 Chat.vue 渲染 → 点击跳 /orders  ✅
买家侧亦可「关联我的订单」主动带单咨询  ✅
```

## 错误处理与兼容性

- 所有卡片消息**始终带 `text` 降级字段**。渲染层 `if (card)` / `else 纯文本`，老消息、AI 文本回复、系统消息完全不受影响，向后兼容。
- 卡片数据缺字段（如 image 为空）时渲染占位，不报错。
- 订单按 `buyer_nick` 尽力匹配：匹配不到时降级为「该店铺近期订单」，demo 场景可接受（真实系统需买家账号跨系统映射，超出本 demo 范围）。

## 改动文件清单

| 层 | 文件 | 改动 |
|----|------|------|
| vmall 后端 | `consumer/conversations.py` | internal 接收端存 card；send_message 带 card（买家订单复用现有 `/consumer/orders`）|
| vmall 后端 | `consumer/orders.py` | `_order_json` 补 `buyer_nick` |
| vmall 前端 | `frontend_consumer/src/views/Chat.vue` | 卡片渲染 + 「咨询此商品」+「关联我的订单」|
| SaaS 后端 | `api/v1/conversations.py` | send 带 card（含商品 ID 还原）；新增 buyer-orders 接口 |
| SaaS 后端 | `api/v1/webhooks.py` | `_handle_message` 存 card；校验 `_upsert_order` product 关联 |
| SaaS 前端 | `frontend/src/views/Service.vue` | 订单面板 + 卡片渲染 + 卡片发送 |

## 验证方式（Docker 恢复后手动 E2E）

1. **售前商品卡片**：买家从床垫页进会话 → 点「咨询此商品」→ 客服端看到商品卡片 → 客服发推荐商品卡片 → 买家点击跳详情页 ✅
2. **售中/售后订单卡片**：买家下单支付 → 客服「买家订单」面板出现该订单（含买家名）→ 客服发订单卡片 → 买家点击跳订单页 ✅
3. **向后兼容**：老的纯文本消息、AI 文本回复仍正常显示 ✅

## YAGNI（明确不做）

- 图片消息 / 本地上传 / 静态服务 → 子项目 B、C
- 卡片编辑、订单详情页、跨系统买家账号实时映射
