# API 规划 · 多平台智能托管 SaaS 平台

---

## 一、规范

- **Base URL:** `/api/v1`
- **认证:** JWT Bearer Token，内含 `merchant_id` + `user_id` + `role`
- **多租户:** 所有数据查询通过 `Depends(get_current_merchant)` 强制携带 `merchant_id`
- **分页:** `?page=1&page_size=20` → `{"total": N, "page": 1, "page_size": 20, "items": [...]}`
- **WebSocket:** `/ws/service?token=<jwt>`

---

## 二、接口总览

| 模块 | 接口数 | 说明 |
|------|:-----:|------|
| 认证 | 3 | 登录/刷新/登出（仅 admin/manager/service） |
| 店铺管理 | 5 | 绑定/解绑/列表/同步触发 |
| 商品库 | 4 | 列表+筛选/语义搜索/详情/手动同步 |
| 订单中心 | 5 | 列表+筛选/详情/售后/催单 |
| 客服工作台 | 5 | 会话列表/详情/WS实时/AI话术 |
| AI 引擎 | 3 | 话术建议/催单话术/搜索 |
| 数据看板 | 3 | 工作台指标/订单趋势/客服统计 |

**总计：约 28 个 REST 接口 + 1 个 WebSocket 端点**

---

## 三、接口详情

### 3.1 认证

```
POST   /api/v1/auth/login          # 登录 {username, password} → {access_token, refresh_token}
POST   /api/v1/auth/refresh        # 刷新 Token
POST   /api/v1/auth/logout         # 登出
```

> 仅 `admin` / `manager` / `service` 可登录。`consumer` 角色不存在。

JWT Payload：
```json
{
  "sub": "1",
  "merchant_id": 1,
  "role": "admin",
  "exp": 1719000000
}
```

### 3.2 店铺管理

```
GET    /api/v1/shops               # 店铺列表
POST   /api/v1/shops               # 绑定店铺 {platform_type, shop_name}
DELETE /api/v1/shops/{id}          # 解绑店铺
POST   /api/v1/shops/{id}/sync     # 手动触发同步
GET    /api/v1/shops/{id}/status   # 同步状态
```

### 3.3 商品库

```
GET    /api/v1/products            # 商品列表 ?shop_id=&category=&keyword=&price_min=&price_max=&page=
GET    /api/v1/products/search     # 语义搜索 ?q=适合送礼的电子产品
GET    /api/v1/products/{id}       # 商品详情
POST   /api/v1/products/sync/{shop_id}  # 手动同步该店铺商品
```

语义搜索响应：
```json
{
  "code": 200,
  "data": {
    "query": "适合送礼的电子产品",
    "results": [
      {"id": 1, "title": "华为Mate70 Pro", "score": 0.92, "shop_name": "模拟数码专营店"},
      {"id": 2, "title": "Apple AirPods Pro", "score": 0.88, "shop_name": "模拟数码专营店"}
    ]
  }
}
```

### 3.4 订单中心

```
GET    /api/v1/orders              # 订单列表 ?shop_id=&platform_type=&status=&page=
GET    /api/v1/orders/{id}         # 订单详情
POST   /api/v1/orders/{id}/refund  # 售后处理（Redis 分布式锁防并发）
GET    /api/v1/orders/pending-payment  # 未支付订单（催单用）
POST   /api/v1/orders/pending-payment/remind  # 批量催单
```

### 3.5 客服工作台

```
WS     /ws/service                 # 实时会话 WebSocket
GET    /api/v1/conversations       # 会话列表 ?shop_id=&handled_status=&page=
GET    /api/v1/conversations/{id}  # 会话详情（含完整 messages_json）
POST   /api/v1/conversations/{id}/assign  # 分配给我
POST   /api/v1/conversations/{id}/close   # 关闭会话
```

### 3.6 AI 引擎

```
POST   /api/v1/ai/suggest          # 话术建议
        Body: {shop_id, buyer_question, conversation_history, product_id?}
        → {suggestions: [{content, source, confidence}]}

POST   /api/v1/ai/campaign/pending-payment  # 催单话术生成
        Body: {shop_id}
        → {reminders: [{buyer_nick, product_title, script, sent}]}

POST   /api/v1/ai/search           # 知识库语义搜索
        Body: {query, shop_id?, top_k=5}
        → {results: [{content, type, score}]}
```

AI 话术建议流程：
```
买家问题 → ChromaDB 语义检索(商品知识+历史话术) → RRF 融合 → LLM 生成回复 → 返回3条建议
```

---

## 四、WebSocket 协议

```
客服工作台 /ws/service：
  服务端推送：
    {"type": "new_conversation", "conversation_id": 1, "buyer_nick": "张三", "preview": "这个多大码？"}
    {"type": "new_message", "conversation_id": 1, "role": "buyer", "content": "有黑色的吗？"}
    
  客户端发送：
    {"type": "ai_suggest", "conversation_id": 1, "question": "有黑色的吗？"}
    → 服务端返回: {"type": "ai_suggest", "suggestions": [...]}
```

---

## 五、错误码

| 范围 | 含义 |
|:----:|------|
| 200 | 成功 |
| 40001 | 参数校验错误 |
| 40101 | Token 无效或过期 |
| 40102 | 不是商户员工 |
| 40301 | 权限不足（service 不能访问店铺管理） |
| 40401 | 资源不存在 |
| 40901 | 同步冲突 |
| 50001 | 平台连接器错误 |
| 51001 | AI 服务错误 |
