# 多平台智能托管 SaaS

> 多租户电商客服托管平台。绑定外部店铺，AI 实时生成话术、语义搜索商品、千人千面催单、智能工单处理。
> **六阶段全部交付** — Mock 模式下完整可演示，无需外部平台 Key。

---

## 快速启动

```bash
# 1. 后端依赖 + 种子数据
cd backend
pip install -r requirements.txt
python seed.py

# 2. 向量化回填
python -c "
from app.database.session import SessionLocal
from app.services.ai_suggest import backfill_all
db=SessionLocal(); print(backfill_all(db, 2, full_rebuild=True)); db.close()
"

# 3. 启动后端
uvicorn main:app --port 8012 --reload

# 4. 启动前端（3 个入口终端）
cd ../frontend
npm install
npm run dev:admin      # :8093  平台管理
npm run dev:merchant   # :8094  商户工作台
npm run dev:service    # :8095  客服工作台
```

登录：**admin / 123456**（admin / manager / service 三种角色均可用）

---

## 系统架构

```
                    ┌──────────────────────────────┐
                    │     MySQL 8.0 :3306          │
                    │     Redis :6379              │
                    │     ChromaDB (嵌入式)         │
                    └──────────────┬───────────────┘
                                   │
    ┌──────────────────────────────┴──────────────────────────────┐
    │                   FastAPI Backend :8012                      │
    │                                                              │
    │  ┌──────────┐  ┌──────────────┐  ┌──────────────────────┐  │
    │  │ Platform │  │  AI Pipeline │  │  LangChain Agent    │  │
    │  │ Connector│  │  Embedding   │  │  Tool Calling       │  │
    │  │ Mock/TB  │  │  RAG + RRF  │  │  (订单/物流/库存)    │  │
    │  │ JD/vMall │  │  Qwen LLM   │  │                     │  │
    │  └──────────┘  └──────────────┘  └──────────────────────┘  │
    │                                                              │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
    │  │  Scheduler   │  │  CRAG 知识库 │  │  Mode Engine     │  │
    │  │  APScheduler │  │  BM25 + 向量 │  │  copilot/auto/   │  │
    │  │  30min 同步  │  │  hybrid检索  │  │  manual          │  │
    │  └──────────────┘  └──────────────┘  └──────────────────┘  │
    └──────────────────────┬──────────────────────────────────────┘
                           │
    ┌──────────────────────┴──────────────────────────────────────┐
    │            Vue 3 + Vite + Element Plus + Pinia              │
    │                                                              │
    │  :8093 平台管理  │  :8094 商户工作台  │  :8095 客服工作台    │
    │  index.html      │  merchant.html     │  service.html       │
    └─────────────────────────────────────────────────────────────┘
```

---

## 端口规划

| 端口 | 角色 | 入口 | 说明 |
|:---:|------|------|------|
| **:8012** | SaaS Backend | — | FastAPI，JWT 多租户 |
| **:8093** | 平台管理 | `index.html` | admin/manager 登录，全局管理 |
| **:8094** | 商户工作台 | `merchant.html` | 商家看板、商品/订单/店铺管理 |
| **:8095** | 客服工作台 | `service.html` | 会话处理、AI 话术、工单 |

---

## 目录结构

```
backend/
├── main.py                     # FastAPI 入口，Scheduler 生命周期
├── seed.py                     # 幂等种子脚本（2 商户 + 店铺 + 商品 + 订单 + 会话 + 工单）
├── requirements.txt / .env
└── app/
    ├── ai/                     # LangChain Agent (NEW)
    │   ├── agent.py            # create_service_agent, run_agent
    │   └── tools.py            # 5 个工具：订单/物流/商品搜索/库存/历史工单
    ├── api/v1/
    │   ├── auth.py             # 登录/刷新/多租户 JWT
    │   ├── shops.py            # 店铺 CRUD + 绑定/解绑 + 调度器状态 + 全量同步
    │   ├── products.py         # 商品列表/搜索/语义搜索/CSV导出
    │   ├── orders.py           # 订单列表/售后/催单/CSV导出
    │   ├── conversations.py    # 会话列表/分配/关闭 + WS 实时通道
    │   ├── tickets.py          # 工单 CRUD + 分类 + 认领 + AI 建议 + 批量操作
    │   ├── ai.py               # AI 话术/催单/知识库搜索/话术风格
    │   ├── dashboard.py        # 看板指标 + 实时监控
    │   └── service_mode.py     # 客服模式配置 + 接管 + 自动回复日志
    ├── core/
    │   ├── config.py           # Pydantic Settings (DB/JWT/Redis/DashScope)
    │   ├── security.py         # JWT HS256 + bcrypt 密码哈希
    │   ├── redis_client.py     # Redis 连接 + 分布式锁
    │   ├── response.py         # ok()/page() 统一响应
    │   └── platform_connector/ # Mock / Taobao / JD / vMall V3
    ├── database/session.py     # SQLAlchemy engine + Base + get_db
    ├── kb/                     # CRAG 知识库模块
    │   ├── kb_api.py           # 知识库 CRUD + 混合检索 + CRAG 评估
    │   ├── processor.py        # 文档分块 + embedding 入库
    │   ├── retriever.py        # 混合检索（向量 + BM25）
    │   ├── chroma_client.py    # ChromaDB 按商户隔离
    │   ├── bm25_index.py       # BM25 关键词索引
    │   ├── reranker.py         # 重排序
    │   ├── crag.py             # CRAG 评估器
    │   └── ...
    ├── models/                 # 22 张表
    ├── schemas/                # Pydantic 请求模型
    └── services/
        ├── ai_suggest.py       # RAG Pipeline（RRF + LLM）+ Agent 路径分发
        ├── ticket_ai.py        # 工单 AI（分类/建议/总结/向量化）
        ├── llm.py              # LangChain ChatDashScope 封装（支持 bind_tools）
        ├── embedding.py        # DashScope text-embedding-v4（1024 维）
        ├── chroma_client.py    # ChromaDB 读写（商品/话术向量）
        ├── mode_engine.py      # 客服模式引擎（copilot/auto/manual）
        ├── scheduler.py        # APScheduler 30 分钟全量同步
        └── recommendation.py   # 协同购买推荐

frontend/
├── index.html / merchant.html / service.html   # 3 入口
├── vite.config.js / vite.config.merchant.js / vite.config.service.js
└── src/
    ├── main.js / main-merchant.js / main-service.js
    ├── api/index.js            # Axios + API 封装
    ├── router/index.js         # 平台管理路由
    ├── router/merchant.js      # 商户工作台路由
    ├── router/service.js       # 客服工作台路由
    ├── stores/auth.js          # Pinia token 持久化
    └── views/                  # 26 页面
        ├── Login.vue           # 三入口自适应登录
        ├── AdminLayout.vue     # 平台管理布局
        ├── MerchantLayout.vue  # 商户工作台布局
        ├── ServiceLayout.vue   # 客服工作台布局
        ├── Dashboard.vue       # 看板 + 日期筛选 + 趋势图
        ├── LiveMonitor.vue     # 实时客服监控（10s 轮询）
        ├── Connectors.vue      # 平台连接器管理
        ├── Service.vue         # 客服会话工作台
        ├── ServiceModeConfig.vue
        ├── Tickets.vue / TicketDetail.vue / TicketCategories.vue
        ├── AutoReplyLogs.vue
        ├── AdminKnowledge.vue / ServiceKnowledge.vue
        ├── AuditLogs.vue / WebhookLogs.vue
        ├── SLAPolicies.vue / SkillGroups.vue
        ├── AIConfig.vue / Recommendations.vue
        ├── Products.vue / Orders.vue / Shops.vue
        ├── Categories.vue / Users.vue
        └── Layout.vue          # 旧布局（兼容）
```

---

## API 速查

Base: `/api/v1`，Authorization: `Bearer <JWT>`

### 认证
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/auth/login` | `{username, password}` → `{access_token, user}` |
| POST | `/auth/refresh` | `{refresh_token}` |

### 店铺 & 连接器
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/shops` | 店铺列表（含商品数/订单数） |
| POST | `/shops` | 绑定店铺 |
| DELETE | `/shops/{id}` | 解绑（级联删除商品/订单/会话） |
| POST | `/shops/{id}/sync` | 手动同步单个店铺 |
| POST | `/shops/{id}/bind-token` | 生成 vMall 绑定 token |
| GET | `/shops/scheduler-status` | 同步调度器状态 + 最近日志 |
| POST | `/shops/trigger-sync` | 触发全量同步 |
| GET | `/shops/connectors` | 各平台连接器状态总览 |

### 商品
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/products` | 列表 `?shop_id=&keyword=&category=&price_min=&price_max=` |
| GET | `/products/search` | 语义搜索 `?q=送礼&shop_id=` |
| GET | `/products/{id}` | 详情 |
| POST | `/products` | 手动创建 |
| PUT | `/products/{id}` | 编辑 |
| DELETE | `/products/{id}` | 删除 |
| GET | `/products/export` | CSV 导出（UTF-8 BOM） |
| POST | `/products/sync/{shop_id}` | 同步指定店铺商品 |

### 订单
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/orders` | 列表 `?shop_id=&status=` |
| GET | `/orders/{id}` | 详情 |
| POST | `/orders/{id}/refund` | 售后（Redis 分布式锁） |
| GET | `/orders/pending-payment` | 未付单列表 |
| POST | `/orders/pending-payment/remind` | AI 催单 `{shop_id, limit}` |
| GET | `/orders/export` | CSV 导出（UTF-8 BOM） |

### 会话
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/conversations` | 列表 `?shop_id=&handled_status=` |
| GET | `/conversations/{id}` | 详情（含 messages_json） |
| POST | `/conversations/{id}/assign` | 分配给我 |
| POST | `/conversations/{id}/messages` | 客服发送消息 |
| POST | `/conversations/{id}/close` | 关闭 |
| GET | `/conversations/export` | CSV 导出（UTF-8 BOM） |
| WS | `/ws/service?token=` | 实时通道（ai_suggest + set_mode + takeover） |

### 工单
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tickets` | 列表（支持分类/状态/优先级筛选） |
| POST | `/tickets` | 创建 |
| GET | `/tickets/{id}` | 详情 + 评论时间线 |
| POST | `/tickets/{id}/claim` | 认领 |
| POST | `/tickets/{id}/ai-suggest` | AI 处理建议 |
| POST | `/tickets/batch` | 批量操作（分配/关闭） |
| GET | `/tickets/export` | CSV 导出 |

### AI 引擎
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/ai/suggest` | 话术建议 `{shop_id, buyer_question, product_id?}` |
| POST | `/ai/campaign/pending-payment` | 催单话术 `{shop_id, limit}` |
| POST | `/ai/search` | 知识库搜索 `{query, top_k}` |
| POST | `/ai/suggest/log` | 记录话术采纳反馈 |
| GET/POST/PUT/DELETE | `/ai/styles` | 话术风格配置 |

### 客服模式
| 方法 | 路径 | 说明 |
|------|------|------|
| GET/PUT | `/service-mode/config` | 模式配置（阈值/时段/模板） |
| POST | `/service-mode/conversations/{id}/mode` | 切换会话模式 |
| POST | `/service-mode/conversations/{id}/takeover` | 人工接管 |
| GET | `/service-mode/auto-reply-logs` | 自动回复日志 |
| GET | `/service-mode/stats` | 自动回复统计 |

### 看板
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/dashboard/metrics` | 指标统计 `?start=&end=` |
| GET | `/dashboard/live-monitor` | 实时客服监控 |

---

## AI Pipeline

```
买家问题
  → 关键词检测（订单/物流/库存 → Agent 路径）
  → Agent 路径：LangChain Agent → 工具调用 → LLM 生成回复
  → RAG 路径：ChromaDB 向量检索 (商品+话术) → RRF 融合 → LLM → 3 条建议
  → 回写 ai_suggest_reply + 记录采纳反馈
```

**Agent 工具集**：`query_order` / `check_logistics` / `search_product_kb` / `check_inventory` / `search_ticket_history`

**LangChain 封装**：`ChatDashScope(BaseChatModel)` 支持 `bind_tools`，用 `langgraph.create_react_agent` 编排。

---

## 平台连接器

| 连接器 | 类型 | 数据 | 说明 |
|--------|------|------|------|
| MockConnector | 内置 | Faker 生成 15 条模板 | 默认 Demo |
| TaobaoConnector | 模拟 | 15 条淘宝风格商品 | 含逼真订单 + 会话 |
| JdConnector | 模拟 | 15 条京东风格商品 | 自营标签 + Plus 会员 |
| V3Connector | 真实 | vMall OpenAPI | 对接 vmall_system |

定时同步：APScheduler 每 30 分钟自动全量同步所有活跃店铺。

---

## 技术栈

| 层 | 技术 |
|------|------|
| 前端 | Vue 3.4, Vite 5, Element Plus 2.5, Pinia 2, Axios, ECharts 5 |
| 后端 | Python 3.13, FastAPI 0.115, SQLAlchemy 2.0, Pydantic 2.10 |
| 数据库 | MySQL 8.0 (PyMySQL), Redis, ChromaDB (嵌入式 PersistentClient) |
| AI | DashScope text-embedding-v4, qwen-max, LangChain + LangGraph Agent |
| 调度 | APScheduler (AsyncIOScheduler) |
| Mock | Faker 33 (zh_CN) |

---

## 多租户隔离

| 层 | 方式 |
|----|------|
| MySQL | 所有查询 `WHERE merchant_id = ...`，JWT 注入 `Depends(get_current_merchant)` |
| ChromaDB | Collection `merchant_{merchant_id}` |
| Redis | Key 前缀 `m:{merchant_id}:...` |

---

## 外部对接

对接 [vMall 虚拟电商平台](../vmall_system/README.md) 获取真实业务数据：
- 店铺绑定 → 生成 Token → vmall 端确认 → `/sync` 拉取数据
- 物流感知 AI：`/ai/suggest` 自动查询 vMall 物流状态注入 Prompt
- Webhook：接收 ORDER_PAID / LOGISTICS_UPDATED / REFUND_SUCCESS 事件
