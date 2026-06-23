# 一期实施计划 · 多平台智能托管 SaaS 平台

> 目标：4 周交付可运行的 SaaS 管理后台 + Mock 演示数据 + AI 话术引擎

---

## 一、一期范围

| 模块 | 范围 | 暂不做 |
|------|------|--------|
| 多租户 | 商户 + 员工 (admin/manager/service) 登录 | 注册/邀请流程 |
| 店铺管理 | Mock 模式一键绑定/解绑 | 真实淘宝/京东 API |
| 商品库 | 列表/语义搜索/自动向量化 | 手动编辑商品 |
| 订单中心 | 列表/详情/售后(Mock)/催单 | 真实退款流程 |
| 客服工作台 | 会话列表+聊天窗口+AI话术面板 | 话术风格自定义 |
| AI 引擎 | 话术建议(向量检索+LLM生成)/催单话术 | 采纳反馈闭环 |
| 种子脚本 | 1商户+2店铺+100商品+60会话+200订单 | — |

---

## 二、目录结构

```
D:\demo_test\
├── backend/
│   ├── main.py
│   ├── seed.py                     # 种子脚本
│   ├── requirements.txt
│   ├── .env
│   ├── app/
│   │   ├── core/
│   │   │   ├── config.py           # PLATFORM_MODE, REDIS_URL, CHROMA_PATH
│   │   │   ├── security.py         # JWT + bcrypt
│   │   │   └── platform_connector/
│   │   │       ├── __init__.py
│   │   │       ├── base.py         # PlatformConnector ABC
│   │   │       ├── mock.py         # MockPlatformConnector (Faker)
│   │   │       └── taobao.py       # NotImplementedError
│   │   ├── database/
│   │   │   └── session.py
│   │   ├── models/
│   │   │   ├── merchant.py
│   │   │   ├── merchant_user.py
│   │   │   ├── platform_shop.py
│   │   │   ├── external_product.py
│   │   │   ├── external_order.py
│   │   │   ├── conversation.py
│   │   │   └── category.py
│   │   ├── schemas/
│   │   ├── api/v1/
│   │   │   ├── dependencies.py     # get_current_merchant + factory
│   │   │   ├── auth.py
│   │   │   ├── shops.py
│   │   │   ├── products.py
│   │   │   ├── orders.py
│   │   │   ├── conversations.py
│   │   │   └── ai/
│   │   │       └── suggest.py
│   │   ├── services/
│   │   │   ├── embedding.py        # BGE-M3
│   │   │   ├── chroma_client.py    # Collection 管理
│   │   │   └── ai_suggest.py       # 话术生成 Pipeline
│   │   └── tasks/
│   │       └── celery_sync.py      # Celery 同步任务
│   └── data/
├── frontend/
│   ├── src/
│   │   ├── router/index.js         # 路由守卫 + merchant role
│   │   ├── stores/
│   │   │   └── auth.js             # Pinia auth store
│   │   ├── api/
│   │   ├── views/
│   │   │   ├── Login.vue
│   │   │   ├── Dashboard.vue       # 工作台
│   │   │   ├── Shops.vue           # 店铺管理
│   │   │   ├── Products.vue        # 商品库（含语义搜索）
│   │   │   ├── Orders.vue          # 订单中心
│   │   │   ├── Service.vue         # 客服工作台（重点）
│   │   │   └── AIConfig.vue        # AI配置占位
│   │   └── components/
│   └── .env.development
└── docs/
```

---

## 三、实施步骤

### 步骤 1：数据库 + 模型重构 (1天)

| # | 动作 | 验证 |
|---|------|------|
| 1.1 | 创建数据库 demo_test，执行所有 DDL（merchants, merchant_users, platform_shops, external_products, external_orders, conversations, categories） | `SHOW TABLES` 8 张表 |
| 1.2 | 编写 SQLAlchemy 模型 | `python -c "from app.models import *"` 无报错 |
| 1.3 | 插入种子商户 + admin 账号 | `SELECT * FROM merchants` 有数据 |

### 步骤 2：Platform Connector (1.5天)

| # | 动作 | 验证 |
|---|------|------|
| 2.1 | 实现 `base.py` 抽象类 | 抽象方法定义完整 |
| 2.2 | 实现 `mock.py` MockPlatformConnector（Faker zh_CN） | `fetch_products()` 返回 50 个商品 |
| 2.3 | 实现工厂函数 `get_platform_connector(shop_id)` | 根据 PLATFORM_MODE 返回正确实例 |
| 2.4 | Celery 同步任务 `sync_all_shops` | 每30分钟自动执行 |

### 步骤 3：种子脚本 (1天)

| # | 动作 | 验证 |
|---|------|------|
| 3.1 | 创建 1 商户 + admin 账号 (admin/123456) | 登录成功 |
| 3.2 | 创建 2 个 Mock 店铺 | `SELECT * FROM platform_shops` 2 行 |
| 3.3 | 生成 100 个商品 + 自动向量化 | `SELECT COUNT(*) FROM external_products` = 100 |
| 3.4 | 生成 60 条会话（覆盖问尺码/快递/质量） | `SELECT COUNT(*) FROM conversations` = 60 |
| 3.5 | 生成 200 条订单（含不同状态） | `SELECT COUNT(*) FROM external_orders` = 200 |
| 3.6 | 脚本末尾打印 "种子数据生成成功！请使用 admin/123456 登录" | — |

### 步骤 4：API 重构 (2天)

| # | 动作 | 验证 |
|---|------|------|
| 4.1 | `POST /auth/login`（仅 admin/manager/service） | curl 返回 JWT 含 merchant_id |
| 4.2 | `GET /shops`（按 merchant_id 过滤） | 返回该商户绑定店铺 |
| 4.3 | `GET /products` + `GET /products/search?q=...` | 语义搜索返回相关商品 |
| 4.4 | `GET /orders` + `POST /orders/{id}/refund` | Mock 售后成功 |
| 4.5 | `GET /conversations` + WebSocket /ws/service | 实时推送新消息 |
| 4.6 | `POST /ai/suggest` 话术建议 | < 2s 返回 3 条建议 |
| 4.7 | `POST /ai/campaign/pending-payment` 催单 | 返回催单话术列表 |

### 步骤 5：前端重构 (2天)

| # | 动作 | 验证 |
|---|------|------|
| 5.1 | 删除 C 端页面，新建管理后台布局 | 左侧菜单 + 顶部导航 |
| 5.2 | Login.vue | 登录跳转工作台 |
| 5.3 | Dashboard.vue | 4 张统计卡片有数据 |
| 5.4 | Shops.vue | 店铺列表 + 绑定弹窗 |
| 5.5 | Products.vue | 表格分页 + 语义搜索框 |
| 5.6 | Orders.vue | 按平台筛选 + 售后按钮 |
| 5.7 | **Service.vue（核心）** | 三栏布局 + AI 话术实时刷新 |
| 5.8 | 路由守卫 | 未登录跳转登录页 |

### 步骤 6：AI Pipeline (1天)

| # | 动作 | 验证 |
|---|------|------|
| 6.1 | BGE-M3 加载 + ChromaDB Collection 创建 | `merchant_1` collection 存在 |
| 6.2 | 话术检索：buyer_question → 向量检索 → RRF 融合 | < 500ms |
| 6.3 | LLM 生成：Prompt 模板 + 千问 → 3 条建议 | < 2s 总响应 |
| 6.4 | 催单话术：未付订单 → 商品卖点 → 千人千面 | 返回差异化话术 |

### 步骤 7：联调验证 (1天)

| # | 动作 |
|---|------|
| 7.1 | `python seed.py` → 登录 → 所有页面有数据 |
| 7.2 | 商品语义搜索 "适合送礼的" → 返回数码产品 |
| 7.3 | 客服工作台 → 选会话 → 右侧出现 AI 建议 → 复制发送 |
| 7.4 | 催单 → 生成差异化话术 → 模拟发送成功 |
| 7.5 | 所有 API < 500ms（AI 接口 < 2s） |

---

## 四、依赖顺序

```
步骤1: DB + Models
  └─→ 步骤2: Platform Connector
        ├─→ 步骤3: 种子脚本
        │     └─→ 步骤7: 联调
        └─→ 步骤4: API
              ├─→ 步骤5: 前端
              │     └─→ 步骤7: 联调
              └─→ 步骤6: AI Pipeline
                    └─→ 步骤7: 联调
```

---

## 五、验证检查表

### 步骤1
- [ ] 8 张表全部存在
- [ ] `admin/123456` 可登录

### 步骤2
- [ ] MockPlatformConnector 生成 50 商品 30 会话
- [ ] `PLATFORM_MODE=mock` 返回 Mock 连接器

### 步骤3
- [ ] 种子脚本运行后打印 "种子数据生成成功！"
- [ ] 所有 AI 功能无需真实店铺即可演示

### 步骤4
- [ ] 所有 API 通过 `merchant_id` 过滤
- [ ] 话术建议 < 2s

### 步骤5
- [ ] 左侧菜单 6 项可点击
- [ ] 客服工作台三栏布局正确
- [ ] 路由守卫生效

### 步骤6
- [ ] `merchant_1` collection 有商品向量 + 话术向量
- [ ] 语义搜索返回相关结果

### 步骤7
- [ ] 完整流程：登录 → 看工作台 → 浏览商品 → 打开客服工作台 → AI 话术 → 催单
