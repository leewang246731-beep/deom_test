# API 规划 · 智能电商全链路平台

---

## 一、API 设计规范

- **Base URL:** `/api/v1`
- **认证方式:** JWT Bearer Token（Header: `Authorization: Bearer <token>`）
- **数据格式:** JSON（请求/响应）
- **分页规范:** `?page=1&page_size=20` → 响应含 `total`, `page`, `page_size`, `items`
- **错误格式:** `{"code": 40001, "message": "...", "detail": {}}`
- **WebSocket:** `/ws/chat?token=<jwt>`

---

## 二、接口总览

| 模块 | 接口数 | 说明 |
|------|:-----:|------|
| 认证鉴权 | 5 | 登录/注册/刷新/登出/个人信息 |
| 商品中心 | 10 | 分类 + SPU/SKU + 搜索 + 属性 |
| 智能推荐 | 8 | 推荐 + 卖点 + 尺码 + 搭配 + 比价 |
| 购物车 | 4 | CRUD + 结算预检 |
| 订单 | 9 | CRUD + 支付 + 物流 + **催单催付** |
| 智能客服 | 8 | 聊天(WS) + 历史 + 意图 + 知识库 + **对比/素材/采纳** |
| 工单售后 | 7 | CRUD + 流转 + 评价 + **紧急升级** |
| 营销活动 | 6 | 优惠券 + 活动 + **消息推送** |
| 学习系统 | 4 | **销冠提炼/知识更新/风格微调/修正反馈** |
| 数据运营 | 6 | 用户分析 + 商品分析 + 客服统计 + 转化漏斗 |
| 用户中心 | 5 | 画像 + 行为 + 收藏 + 浏览历史 |

**总计：约 72 个 REST 接口 + 2 个 WebSocket 端点**

---

## 三、核心接口详情

### 3.1 认证鉴权

```
POST   /api/v1/auth/register         # 注册
POST   /api/v1/auth/login            # 登录
POST   /api/v1/auth/refresh          # 刷新 Token
POST   /api/v1/auth/logout           # 登出
GET    /api/v1/auth/me               # 当前用户信息
```

### 3.2 商品中心

```
GET    /api/v1/categories            # 分类树
GET    /api/v1/categories/{id}       # 分类详情
GET    /api/v1/products              # 商品列表 ?category=&keyword=&sort=&page=&page_size=
GET    /api/v1/products/{id}         # 商品详情（含 SKU 列表）
GET    /api/v1/products/{id}/skus    # SKU 列表
GET    /api/v1/products/search       # 全文搜索 + 向量语义搜索
POST   /api/v1/products              # [管理] 创建商品
PUT    /api/v1/products/{id}         # [管理] 更新商品
DELETE /api/v1/products/{id}         # [管理] 下架商品
POST   /api/v1/products/{id}/vectorize  # [管理] 生成/更新商品向量
```

### 3.3 智能推荐（增强版）

```
GET    /api/v1/recommend/home           # 首页混合推荐
GET    /api/v1/recommend/product/{id}   # 商品详情页推荐
GET    /api/v1/recommend/personalized   # 个性化推荐
GET    /api/v1/recommend/hot            # 热门排行
GET    /api/v1/recommend/similar/{id}   # 相似商品
POST   /api/v1/recommend/selling-points # 商品卖点提炼 {product_id} ← 新增
POST   /api/v1/recommend/size           # 尺码推荐 {product_id, height, weight, ...} ← 新增
POST   /api/v1/recommend/outfit         # 搭配推荐 {product_id} ← 新增
```

推荐响应格式：
```json
{
  "code": 200,
  "data": {
    "sections": [
      {
        "type": "personalized",
        "title": "为你推荐",
        "reason": "基于你的浏览偏好",
        "products": [
          {
            "id": 1,
            "name": "iPhone 15 Pro",
            "price": 7999.00,
            "main_image": "...",
            "score": 0.95,
            "reason": "你最近浏览过手机"
          }
        ]
      },
      {
        "type": "collaborative",
        "title": "买过的人也买了",
        "products": [...]
      }
    ]
  }
}
```

### 3.4 购物车

```
GET    /api/v1/cart                   # 购物车列表
POST   /api/v1/cart/items             # 添加商品 {sku_id, quantity}
PUT    /api/v1/cart/items/{sku_id}    # 修改数量
DELETE /api/v1/cart/items/{sku_id}    # 删除商品
POST   /api/v1/cart/checkout-check    # 结算预检（库存/价格/优惠）
```

### 3.5 订单

```
POST   /api/v1/orders                 # 创建订单
GET    /api/v1/orders                 # 订单列表 ?status=
GET    /api/v1/orders/{id}            # 订单详情
POST   /api/v1/orders/{id}/cancel     # 取消订单
POST   /api/v1/orders/{id}/pay        # 发起支付
POST   /api/v1/orders/pay-callback    # 支付回调（支付宝/微信）
GET    /api/v1/orders/{id}/logistics  # 物流信息
POST   /api/v1/orders/{id}/confirm    # 确认收货
```

### 3.6 智能客服（增强版）

```
WS     /ws/chat                       # WebSocket 实时对话
GET    /api/v1/chat/history           # 历史对话 ?session_id=&page=
POST   /api/v1/chat/intent            # 意图识别 {text: "..."}
POST   /api/v1/chat/search-kb         # 知识库检索 {query: "..."}
POST   /api/v1/chat/compare           # 商品对比 {product_ids: [1,2,3]}
POST   /api/v1/chat/send-material     # 手动触发素材图 {product_id, image_type}
POST   /api/v1/chat/adopt             # 采纳话术 {message_id, original, corrected?}
POST   /api/v1/chat/session-mode      # 设置会话模式 {mode: "auto"|"assist"}
```

WebSocket 消息协议：
```json
// 客户端 → 服务端
{
  "type": "message",
  "session_id": "uuid",
  "content": "这款手机续航怎么样？",
  "context": {                       // 可选：浏览上下文
    "current_product_id": 123,
    "page": "product_detail"
  }
}

// 服务端 → 客户端（增强版）
{
  "type": "reply",
  "session_id": "uuid",
  "content": "这款手机配备 5000mAh 电池...",
  "intent": "product_inquiry",
  "agent": "customer_service",
  "mode": "assist",                       // auto | assist ← 新增
  "style": "expert",                      // 当前话术风格 ← 新增
  "suggestions": ["加入购物车", "查看评价"],
  "materials": [                          // 自动匹配的素材图 ← 新增
    {"type": "size_chart", "url": "...", "label": "尺码表"}
  ],
  "products": [...],
  "auto_sent": false                      // 是否自动发送 ← 新增
}
```

### 3.7 工单售后

```
POST   /api/v1/tickets               # 创建工单
GET    /api/v1/tickets               # 工单列表 ?status=&type=
GET    /api/v1/tickets/{id}          # 工单详情
PUT    /api/v1/tickets/{id}/status   # [管理] 更新状态
POST   /api/v1/tickets/{id}/comments # 添加工单评论
POST   /api/v1/tickets/{id}/rate     # 满意度评价
```

### 3.8 营销活动

```
GET    /api/v1/coupons               # 可用优惠券列表
POST   /api/v1/coupons/{id}/claim    # 领取优惠券
GET    /api/v1/promotions            # 进行中的活动
GET    /api/v1/promotions/{id}       # 活动详情（含活动商品）
```

### 3.11 学习系统（新增）

```
POST   /api/v1/learn/extract-top-seller # 销冠话术提炼 {chat_logs: [...]}
POST   /api/v1/learn/update-knowledge   # 知识库自动更新 {product_id, source}
POST   /api/v1/learn/style-finetune     # 风格微调 {style_id, corrections: [...]}
GET    /api/v1/learn/correction-stats   # 修正统计 {agent_id, date_range}

### 3.12 外部推送（新增）

```
POST   /api/v1/notify/send              # 发送消息 {target, platform, content}
GET    /api/v1/notify/channels          # 可用推送渠道（钉钉/微信/飞书）
```

```
GET    /api/v1/analytics/dashboard   # 运营仪表盘
GET    /api/v1/analytics/users       # 用户分析（新增/活跃/留存）
GET    /api/v1/analytics/products    # 商品分析（销量排行/转化率）
GET    /api/v1/analytics/customer-service  # 客服统计（响应时间/满意度）
GET    /api/v1/analytics/funnel      # 转化漏斗（浏览→加购→下单→支付）
GET    /api/v1/analytics/rfm         # RFM 用户分层
```

### 3.10 用户中心

```
GET    /api/v1/user/profile          # 用户画像
PUT    /api/v1/user/profile          # 更新资料
GET    /api/v1/user/behaviors        # 行为记录 ?action=
GET    /api/v1/user/favorites        # 收藏列表
GET    /api/v1/user/browsing-history # 浏览历史
```

---

## 四、错误码规范

| 范围 | 含义 |
|:----:|------|
| 200 | 成功 |
| 40001-40099 | 参数校验错误 |
| 40100-40199 | 认证授权错误 |
| 40300-40399 | 权限不足 |
| 40400-40499 | 资源不存在 |
| 40900-40999 | 业务冲突（库存不足等） |
| 50000-50099 | 服务端错误 |
| 51000-51099 | AI 服务错误 |

---

## 五、WebSocket 端点设计

| 端点 | 用途 | 认证 |
|------|------|:---:|
| `/ws/chat` | 智能客服实时对话 | JWT Token |
| `/ws/notifications` | 系统通知（订单状态、物流、活动） | JWT Token |
