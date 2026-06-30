# 多平台智能托管 SaaS

> 多租户电商客服托管平台。绑定 vMall/淘宝/京东店铺，AI 多智能体实时处理客服请求——商品搜索、订单查询、物流追踪、售后审批、智能催单、工单管理。
> **已完成全量业务真实化重构** — 平台端多租户上下文、订单/售后 vmall 联动、连接器 per-shop 模式、Agent 五维优化。

---

## 快速启动

### Docker（推荐）

```bash
# 仅 SaaS（MySQL + Redis + Backend + Frontend）
docker-compose up -d

# SaaS + vMall 全套（含买家H5 + 商户端 + 运营后台）
docker-compose --profile full up -d
```

访问：

| 入口 | 端口 | 账号 | 密码 | 角色 |
|---|---|---|---|---|
| 平台管理 | 8093 | super_admin | 123456 | 平台超级管理员 |
| 商户工作台 | 8094 | admin | 123456 | 商户管理员 |
| 客服工作台 | 8095 | service | 123456 | 客服人员 |

> 平台管理端需先**在顶部选择目标商户**，再进行操作。

### 本地开发

```bash
# 1. 后端
cd backend
pip install -r requirements.txt
python seed.py --backfill --full
uvicorn main:app --host 0.0.0.0 --port 8012

# 2. 前端
cd frontend
npm install
npm run dev:admin      # :8093
npm run dev:merchant   # :8094
npm run dev:service    # :8095
```

### vMall 全套（可选）

```bash
# vMall 后端 :8020
cd vmall_system/backend
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8020

# vMall 前端（3 个入口）
cd vmall_system/frontend_admin && npm install && npm run dev   # :8092 运营后台
cd vmall_system/frontend_merchant && npm install && npm run dev # :8091 商户端
cd vmall_system/frontend_consumer && npm install && npm run dev # :8090 买家H5
```

---

## 系统架构

```
                    ┌──────────────────────────────┐
                    │     MySQL 8.0 + Redis         │
                    │     ChromaDB (嵌入式向量库)    │
                    └──────────────┬───────────────┘
                                   │
    ┌──────────────────────────────┴──────────────────────────────┐
    │                   FastAPI Backend :8012                      │
    │                                                              │
    │  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐  │
    │  │ Per-Shop     │  │  AI Pipeline   │  │  Supervisor    │  │
    │  │ Connector    │  │  RAG + RRF     │  │  Multi-Agent   │  │
    │  │ Mock/vMall   │  │  10 Agent Tools│  │  DAG Planning  │  │
    │  └──────────────┘  └────────────────┘  └────────────────┘  │
    │                                                              │
    │  ┌──────────────┐  ┌────────────────┐  ┌────────────────┐  │
    │  │  Memory      │  │  Scheduler     │  │  Mode Engine   │  │
    │  │  Session+    │  │  APScheduler   │  │  copilot/auto/ │  │
    │  │  Buyer+Exec  │  │  30min 同步    │  │  manual        │  │
    │  └──────────────┘  └────────────────┘  └────────────────┘  │
    └──────────────────────┬──────────────────────────────────────┘
                           │
    ┌──────────────────────┴──────────────────────────────────────┐
    │            Vue 3 + Vite + Element Plus + Pinia              │
    │                                                              │
    │  :8093 平台管理  │  :8094 商户工作台  │  :8095 客服工作台    │
    └─────────────────────────────────────────────────────────────┘
```

---

## Agent 系统

### 多智能体架构

```
Supervisor (主管)
  ├─ classify_intent  → LLM Structured Output 规划 (含 DAG 依赖)
  ├─ route_experts    → 按任务依赖拓扑排序
  ├─ dispatch_experts → DAG 调度 (依赖串行 / 独立并行)
  ├─ replan_check     → 低置信度自动重试
  ├─ aggregate_reply  → ReplyAgent 合成回复
  └─ clarify_check    → 信息不足时反问买家
       │
       ├── OrderAgent      (订单查询 + 退款)
       ├── LogisticsAgent  (物流轨迹)
       ├── ProductAgent    (商品搜索 + 库存)
       ├── TicketAgent     (工单查询)
       ├── RAGAgent        (知识库检索)
       └── ReplyAgent      (合成回复)
```

### Agent 工具集（10 个）

| 工具 | 标签 | 数据源 |
|---|---|---|
| `query_order` | order, query | DB 查询 |
| `check_logistics` | logistics, query | vmall conn + mock fallback |
| `search_product_kb` | product, knowledge | ChromaDB 向量检索 |
| `check_inventory` | product, inventory | DB 查询 |
| `search_ticket_history` | ticket, knowledge | ChromaDB 向量检索 |
| `deliver_order` | order, action | vmall conn + DB |
| `send_buyer_message` | message, action | vmall conn |
| `create_support_ticket` | ticket, action | DB |
| `recommend_products` | product, recommendation | 推荐服务 + 语义搜索 |
| `get_buyer_profile` | buyer, query | ChromaDB buyer_memory |

### Agent 记忆体系

- **短期记忆**：对话历史透传给子 Agent（最近 6 轮）
- **会话持久化**：每次调用自动写入 kb_messages
- **买家画像**：订单+会话提取偏好 → ChromaDB buyer_memory
- **执行记忆**：记录工具调用策略 → 相似问题复用

---

## 已完成的重大重构

### 切片 1 — 平台端多租户上下文
- 平台管理员顶部选择目标商户
- `get_effective_merchant_id` 统一解析：平台 token 读 `X-Merchant-Id`，商户 token 读自身
- 全 14 个后端模块替换 `current.merchant_id` → `mid`
- 租户隔离：商户 token 伪造 `X-Merchant-Id` 无效

### 切片 2 — 订单/售后/催单真实化
- `refund_order`：修复 un-await bug + 错误 sale_id + 静默吞错 → `run_connector` 真联动 vmall
- `remind_pending`：落库 `order_reminders` + Redis 冷却 6h + vmall 通知外发
- vmall 新增 `POST /openapi/notifications` 买家通知端点
- Webhook `AFTER_SALE_CREATED` 捕获 `after_sale_id` 供售后审批

### 切片 3 — 连接器 per-shop 模式
- 移除全局 `PLATFORM_MODE=mock` 短路
- `bind_shop` 自动调 vmall `/openapi/auth` 获取 access_token
- vmall 店铺有 token → V3Connector，无 token → 降级 mock
- 前端展示 token 状态

### 切片 4 — 收尾修复
- AI fallback 文案修正（"待步骤6接入" → "AI 生成失败"）
- KB 模块 `kb_documents` 补 `file_path`/`file_type` 列

---

## 端口规划

| 端口 | 角色 | 入口 | 说明 |
|:---:|------|------|------|
| 8012 | SaaS Backend | — | FastAPI，JWT 多租户 |
| 8093 | 平台管理 | `index.html` | super_admin 登录，全局管理 + 商户选择器 |
| 8094 | 商户工作台 | `merchant.html` | 商家看板、商品/订单/店铺管理 |
| 8095 | 客服工作台 | `service.html` | 会话处理、AI 多智能体、工单 |

vMall 全套（`--profile full`）：

| 端口 | 角色 |
|:---:|------|
| 8020 | vMall Backend |
| 8092 | vMall 运营后台 |
| 8091 | vMall 商户端 |
| 8090 | vMall 买家 H5 |

---

## 目录结构

```
backend/
├── main.py                     # FastAPI 入口 + 路由注册
├── seed.py                     # 幂等种子（3 商户 + 商品 + 订单 + 会话 + 工单）
├── Dockerfile                  # Docker 构建（含幂等迁移）
├── requirements.txt
└── app/
    ├── ai/                     # 多智能体系统
    │   ├── agent.py            # 统一入口（传统 ReAct + Supervisor）
    │   ├── supervisor.py       # Supervisor-Worker (LLM规划 + DAG + RePlan + Clarify)
    │   ├── tools.py            # 工具集入口（委托 ToolRegistry）
    │   ├── tool_registry.py    # 统一工具注册中心 (10 tools)
    │   ├── memory.py           # 记忆系统（会话+买家画像+执行记忆）
    │   └── agents/             # 子 Agent
    │       ├── base_agent.py   # 基类 (CoT + ReAct limit + memory)
    │       ├── order_agent.py  # 订单查询+退款
    │       ├── logistics_agent.py # 物流（真 vmall + mock）
    │       ├── product_agent.py
    │       ├── ticket_agent.py
    │       ├── rag_agent.py
    │       └── reply_agent.py  # 合成回复
    ├── api/v1/                 # REST API
    │   ├── auth.py             # 双通道 JWT（平台+商户）
    │   ├── dependencies.py     # get_effective_merchant_id 等
    │   ├── shops.py            # 店铺绑定/同步/connector
    │   ├── orders.py           # 订单/售后/催单（真联动）
    │   ├── products.py         # 商品/语义搜索
    │   ├── tickets.py          # 工单 CRUD + AI
    │   ├── ai.py               # AI 话术/风格
    │   ├── dashboard.py        # 看板
    │   ├── conversations.py    # 会话 + WS
    │   ├── recommendations.py  # 推荐规则
    │   ├── service_mode.py     # 客服模式配置
    │   ├── skill_groups.py     # 技能组
    │   ├── sla.py              # SLA 策略
    │   ├── categories.py       # 分类管理
    │   ├── users.py            # 用户管理
    │   ├── merchants.py        # 商户列表（平台端选择器）
    │   ├── webhooks.py         # vMall webhook 接收
    │   ├── webhook_logs.py     # Webhook 日志
    │   ├── audit.py            # 审计日志
    │   └── openapi.py          # 对外 OpenAPI
    ├── core/
    │   ├── config.py           # Pydantic Settings
    │   ├── security.py         # JWT + bcrypt
    │   ├── redis_client.py     # Redis 连接
    │   └── platform_connector/ # 平台连接器
    │       ├── __init__.py     # Per-shop 工厂
    │       ├── base.py         # PlatformConnector 基类
    │       ├── vmall.py        # V3Connector (真实 vMall)
    │       ├── mock.py         # MockPlatformConnector
    │       ├── runner.py       # run_connector async→sync 桥接
    │       ├── taobao.py       # TaobaoConnector (框架)
    │       └── jd.py           # JdConnector (框架)
    ├── kb/                     # 知识库 (CRAG + 混合检索)
    ├── models/                 # SQLAlchemy 模型
    └── services/               # 业务服务 (AI/推荐/调度/嵌入/模式引擎)

frontend/
├── Dockerfile
├── nginx.conf                  # 3 端口 Nginx 配置
└── src/
    ├── api/                    # API client + request interceptor
    ├── views/                  # 页面组件
    │   ├── AdminLayout.vue     # 平台布局 (含商户选择器)
    │   ├── MerchantLayout.vue  # 商户布局
    │   ├── ServiceLayout.vue   # 客服布局
    │   └── *.vue               # 各功能页面
    ├── stores/                 # Pinia stores
    └── router/                 # 3 套路由

vmall_system/                   # vMall 电商平台（可选依赖）
    ├── backend/                # FastAPI (JWT + OpenAPI)
    └── frontend_*/             # Vue 3 前端 (admin/merchant/consumer)
```

---

## 运行测试

```bash
cd backend
python test_e2e_smoke.py   # E2E 冒烟（78 用例，需后端已启动）
python -m pytest tests/ -q  # RAG 管道回归（10 用例）
```
