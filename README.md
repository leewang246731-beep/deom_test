# 多平台智能托管 SaaS

> 多租户电商客服托管平台。绑定外部店铺，AI 实时生成话术、语义搜索商品、千人千面催单、智能工单处理。
> **七轮迭代优化** — Mock 模式下完整可演示，AI 层升级为 OpenAI 兼容协议，全量 LLM 降级兜底。

---

## 快速启动

```bash
# 1. 后端依赖 + 种子数据 + 向量回填
cd backend
pip install -r requirements.txt
python seed.py --backfill --full   # 创建 3 商户、250 商品、200 订单等，并重建向量索引

# 2. 启动后端
uvicorn main:app --host 0.0.0.0 --port 8012

# 3. 启动前端（3 个入口）
cd ../frontend
npm install
npm run dev:admin      # :8093  平台管理后台
npm run dev:merchant   # :8094  商户工作台
npm run dev:service    # :8095  客服工作台
```

### 登录账号

| 入口 | 端口 | 账号 | 密码 | 角色 |
|------|:---:|------|------|------|
| 平台管理 | 8093 | super_admin | 123456 | 平台超级管理员 |
| 商户工作台 | 8094 | admin | 123456 | 商户管理员 |
| 客服工作台 | 8095 | service | 123456 | 客服人员 |

> **多商户提示**: 种子数据创建了 3 个商户（数码旗舰/时尚女装/潮流美妆），每商户均有 admin/manager/service 用户。如登录时提示"该用户名在多个商户中存在"，需在下拉框中选择目标商户后重新登录。

### 运行测试

```bash
cd backend
python test_e2e_smoke.py   # 57 用例 E2E 冒烟测试（需后端已启动）
```

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

**LLM 调用链**：`openai.OpenAI(base_url=DashScope兼容端点)` → 自动重试(2次,指数退避) → 降级兜底话术（不抛异常）

**Agent 工具集**：`query_order` / `check_logistics` / `search_product_kb` / `check_inventory` / `search_ticket_history`

**LangChain 封装**：`ChatDashScope(BaseChatModel)` 支持 `bind_tools`，用 `langgraph.create_react_agent` 编排。`achat()` 异步安全包装避免事件循环阻塞。

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
| 前端 | Vue 3.4, Vite 5, Element Plus 2.5, Pinia 2, Axios, ECharts 5, TypeScript 5.5 |
| 后端 | Python 3.13, FastAPI 0.115, SQLAlchemy 2.0, Pydantic 2.10 |
| 数据库 | MySQL 8.0 (PyMySQL), Redis, ChromaDB (嵌入式 PersistentClient) |
| AI | DashScope OpenAI 兼容 (qwen-plus / text-embedding-v4 / gte-rerank-v2), LangChain + LangGraph |
| 多智能体 | Supervisor-Worker 架构 (LangGraph StateGraph), 6 专家 Agent |
| RAG | 多格式加载器 (PDF/DOCX/XLSX/PPTX), tiktoken 分块, HyDE, 自纠错 |
| 调度 | APScheduler (AsyncIOScheduler) |
| 测试 | Playwright (E2E), pytest, AST body:dict 扫描器 |
| Mock | Faker 33 (zh_CN) |

---

## 多租户隔离

| 层 | 方式 |
|----|------|
| MySQL | 所有查询 `WHERE merchant_id = ...`，JWT 注入 `Depends(get_current_merchant)` |
| ChromaDB | Collection `merchant_{merchant_id}` |
| Redis | Key 前缀 `m:{merchant_id}:...` |

---

## AI 多智能体架构 (v2.1.0)

```
买家问题
  │
  ▼
SupervisorAgent (主管)
  │ classify_intent (意图分类)
  ▼
route_experts (路由分发)
  │
  ├── OrderAgent (订单查询/退款)
  ├── LogisticsAgent (物流追踪)
  ├── ProductAgent (商品搜索/库存)
  ├── TicketAgent (工单历史/优先级)
  ├── RAGAgent (知识库检索)
  └── ReplyAgent (结果聚合→最终回复)
```

## 企业级 RAG 全链路 (v2.1.0)

```
文档上传 (PDF/DOCX/XLSX/PPTX/MD/TXT)
  → SmartChunker (tiktoken cl100k_base, 384 token)
  → ChromaDB + BM25 混合索引

用户提问
  → Query Optimize (Rewrite + HyDE + Step-Back)
  → Hybrid Retrieve (Dense + BM25 + RRF)
  → CRAG Evaluate (LLM 相关性判断)
  → gte-rerank-v2 API 重排序
  → Sentence-level Context Compression
  → LLM Generate (SSE Streaming)
  → Self-Correction (Fact-check + 幻觉检测)
  → Quality Monitor (Trace Logging)
```

## 外部对接

对接 [vMall 虚拟电商平台](../vmall_system/README.md) 获取真实业务数据：
- 店铺绑定 → 生成 Token → vmall 端确认 → `/sync` 拉取数据
- 物流感知 AI：`/ai/suggest` 自动查询 vMall 物流状态注入 Prompt
- Webhook：接收 ORDER_PAID / LOGISTICS_UPDATED / REFUND_SUCCESS 事件
- 跨系统桥接 C1-C8 全部代码完备

---

## 设计决策 (By Design)

以下特性为**有意设计**，非缺陷：

| 决策 | 说明 |
|------|------|
| **商品不支持手动 CRUD** | 商品通过平台连接器同步 (`POST /products/sync/{shop_id}`)，`POST/PUT/DELETE /products` 仅提供基础的增删改用于测试 |
| **WebSocket 独立于 REST** | `/ws/service` 用于实时推送（AI 建议、会话状态），REST 端点已覆盖所有数据操作 |
| **语义搜索依赖向量回填** | 首次部署必须执行 `python seed.py --backfill --full`，否则搜索返回空结果 |
| **AI 功能依赖 DashScope** | 所有 AI 功能（话术、催付、RAG、语义搜索）需有效 DashScope API key；API 不可用时端点返回明确错误信息 |
| **工单分类按商户隔离** | `ticket_categories` 表按 `merchant_id` 隔离，每个商户独立管理分类树 |
| **openapi.py 保留 `body: dict`** | 外部 API 契约（vMall 集成），使用 API Key 认证，保持向后兼容 |
| **多商户登录需指定 merchant_id** | 同名用户在不同商户中使用时，前端自动弹出商户选择下拉框 |

---

## 变更记录

### v2.1.1 (2026-06-27) — AI 层升级 + 全量稳定性修复 (7 轮迭代)

**AI / LLM 升级**
- **重构**: LLM 层从 `dashscope` SDK → `openai` SDK（DashScope OpenAI 兼容端点）
- **切换**: 默认模型 `qwen-max` → `qwen-plus`（配额更宽松，性价比更高）
- **新增**: LLM 自动重试（2次，指数退避）+ 降级兜底话术模板（物流/退款/价格/质量/通用 5 类场景）
- **新增**: `achat()` 异步安全包装 — `asyncio.to_thread()` 避免阻塞事件循环
- **重构**: Embedding 层同样迁移到 OpenAI 兼容端点

**后端稳定性修复**
- **修复**: `_timeout_checker` 硬编码 `merchant_id==1` → 动态查找商户配置
- **修复**: 分页参数无校验 → 10 个端点统一加 `ge=1, le=200`
- **修复**: 会话详情 `status` 字段为 null → 新增 `status` 别名映射 `handled_status`
- **新增**: 商品同步/创建后自动触发 `backfill_all` 向量回填
- **新增**: 工单创建后后台线程触发 `backfill_tickets`
- **新增**: 健康检查增加 LLM 连通性检测
- **修复**: ChromaDB 废弃 `Settings` API → 环境变量 `ANONYMIZED_TELEMETRY`
- **修复**: `TicketCreate.title` 增加 `min_length=1` 校验
- **修复**: KB Collection 改用 `get_or_create_collection` 替代 try/except

**前端交互修复 (12 页面)**
- **修复**: 催单话术仅显示计数 → 弹窗展示完整话术内容 + 一键复制
- **修复**: 订单详情仅用行数据 → `showDetail` 调用 `GET /orders/{id}` API
- **修复**: 批量分配缺少用户选择 → 增加处理人下拉框
- **新增**: 9 个页面 Loading 态绑定（SkillGroups/AIConfig/Recommendations/Service/Categories×2）
- **新增**: 分类管理页面空状态提示 + 快速创建入口
- **新增**: `api/index.js` 新增 `generateBindToken` / `regenerateToken`
- **修复**: Shops.vue 改用封装 API 函数替代裸 `http.post`

**部署 / 文档**
- **更新**: `docker-compose.yml` 新增 `LLM_MODEL` / `LLM_API_BASE` 环境变量
- **更新**: README 技术栈/架构图/AI Pipeline 同步更新

### v2.1.0 (2026-06-26) — 全栈工程化 + 多智能体 + 企业级 RAG

**Stage 1: 前端/后端工程化硬化**
- **新增**: `useRequest.ts` 统一请求层（泛型+防抖+重试+确认）
- **新增**: OpenAPI → TypeScript 类型生成 (`npm run generate:api`)
- **新增**: AST `body:dict` 硬拦截扫描器 (`python backend/scripts/check_body_dict.py`)
- **改进**: API 拦截器错误分类（400/401/403/404/409/429/500）
- **改进**: Token 自动刷新（401 → refresh_token → 重试原请求）
- **改进**: Products.vue 搜索 300ms 防抖

**Stage 2: 多智能体系统 (Supervisor-Worker)**
- **新增**: `SupervisorAgent` — LangGraph StateGraph 主管编排（classify→route→dispatch→aggregate）
- **新增**: 6 专家 Agent (Order/Logistics/Product/Ticket/RAG/Reply)
- **新增**: `BaseExpertAgent` 抽象基类，支持工具构建+ReAct 执行
- **重构**: `agent.py` 统一入口，自动检测 Agent 类型

**Stage 3: 企业级 RAG 全链路**
- **新增**: 多格式文档加载器 (PDF/DOCX/XLSX/PPTX/MD/TXT)
- **新增**: tiktoken 精确分块器 (替代 `len/1.3` 启发式)
- **新增**: DashScope gte-rerank-v2 重排序 (替代余弦)
- **新增**: 句子级上下文压缩
- **新增**: HyDE 查询扩展 (原关闭，现已启用)
- **新增**: Self-Correction 自纠错 (事实核查+幻觉检测)
- **新增**: Quality Monitor 质量追踪
- **改进**: `/kb/ask` 管道升级为 9 步完整链路

**Stage 4: E2E + 体验**
- **新增**: Playwright E2E 测试 (5 核心流程)
- **新增**: `useFeedback.ts` 统一反馈封装

**生产安全**
- **新增**: 可配置 CORS (`.env` 控制)
- **新增**: 登录频率限制 (Redis, 10次/分钟/IP)
- **新增**: RequestID 追踪中间件
- **新增**: 分页参数自动修正 (`clamp_pagination`)
- **修复**: Webhook 投递日志持久化
- **修复**: C6 消息桥接 `c.shop` AttributeError

**DevOps**
- **新增**: `docker-compose.yml` 统一部署
- **新增**: `Dockerfile` (SaaS + vMall)
- **新增**: `verify.py` 系统验证 (10 项检查)
- **新增**: `test_api_full.py` 全量 API 测试 (94 端点)
- **新增**: `DEPLOYMENT.md` 部署指南
- **更新**: `test_e2e_smoke.py` 扩展至 69 用例

### v2.0.1 (2026-06-26)

- **修复**: 平台运营登录路由注册 (BUG-001)
- **修复**: 工单创建 500 错误 — 全端点 Pydantic Schema 化 (BUG-002, BUG-006)
- **修复**: 多租户登录隔离 — 同名用户检测 + 商户选择 (BUG-005)
- **修复**: 语义搜索空结果 — 306 个向量回填 (BUG-003)
- **修复**: AI 催付空数据 — 错误处理改进 (BUG-004)
- **修复**: 工单分类路由排序 — `/categories` 被 `/{ticket_id}` 拦截 (BUG-009)
- **修复**: 店铺重名检查 (BUG-011)
- **改进**: `body: dict` 全面替换为 Pydantic Schema (34→5，85% 清理率)
- **改进**: 响应格式统一 — `/shops` 和 `/orders/pending-payment` 改为分页格式
- **改进**: 前端登录增加多商户选择 UI
- **新增**: E2E 冒烟测试脚本 (`test_e2e_smoke.py`, 57 用例)
