# 电商智能托管平台

> 帮助商家绑定外部店铺，用 AI 实时生成客服话术、千人千面催单。
> **一期已交付** — Mock 模式下完整可演示，无需任何外部平台 Key。

---

## 快速启动（3 步）

```bash
# 1. 种子数据（幂等，可重复运行）
cd backend
pip install -r requirements.txt
python seed.py
# 输出: 种子数据生成成功！请使用 admin/123456 登录

# 2. 向量化回填（每次 re-seed 后需重新跑一次）
python -c "
from app.database.session import SessionLocal
from app.services.ai_suggest import backfill_all
db=SessionLocal(); print(backfill_all(db,1)); db.close()
"
# 输出: {'products': 100, 'replies': 60, 'total_vectors': 160}

# 3. 启动
# 终端 1: 后端
cd backend && python -m uvicorn main:app --port 8010

# 终端 2: 前端
cd frontend && npm install && npm run dev
# → http://localhost:8080
```

登录：**admin / 123456**
其他账号：manager / 123456、service / 123456

---

## 演示流程（5 分钟完整走一遍）

| 步骤 | 页面 | 操作 |
|------|------|------|
| 1 | 登录 | `admin / 123456` → 进入工作台 |
| 2 | 工作台 | 看到 4 张统计卡片 + 订单趋势图 |
| 3 | 店铺管理 | 看到 2 个 Mock 店铺（数码专营店 / 潮流女装店） |
| 4 | 商品库 | 100 个商品分页列表；搜 `送礼` → 华为/AirPods/Kindle 出现，带相似度评分 |
| 5 | 订单中心 | 200 个订单筛选；点"售后"→成功；再点→"请勿重复提交" |
| 6 | 客服工作台 | 左侧选一个会话 → 中间看对话 → 右侧点"生成 AI 建议"→ 3 条 LLM 话术 |
| 7 | 订单中心 | 点"一键催单"→ 5 条千人千面催付话术 |

**核心演示点：AI 话术建议 < 2s 返回，语义搜索准确匹配"送礼"→数码产品。**

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│  Frontend :8080  (Vue3 + Vite + Element Plus + Pinia)      │
│  Login │ Dashboard │ Shops │ Products │ Orders │ Service   │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST + WebSocket
┌──────────────────────┴──────────────────────────────────────┐
│  Backend :8010  (FastAPI + SQLAlchemy + Pydantic)           │
│                                                              │
│  Platform Connector ──── Mock (Faker, 完整)                  │
│                       ─── Taobao (二期, NotImplementedError) │
│                                                              │
│  AI Pipeline ──── embedding (DashScope text-embedding-v4)    │
│              ──── ChromaDB 向量检索 (RRF 融合)               │
│              ──── LLM (qwen-max, 话术生成+催单)              │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────┴──────────────────────────────────────┐
│  MySQL 8.0 :3306  │  ChromaDB (嵌入式)  │  Redis :6379      │
└─────────────────────────────────────────────────────────────┘
```

---

## 项目结构

```
├── backend/
│   ├── main.py              # FastAPI 入口，:8010
│   ├── seed.py              # 幂等种子脚本
│   ├── requirements.txt / .env
│   ├── app/
│   │   ├── core/            # config, security(JWT+bcyrpt), redis_client, response
│   │   │   └── platform_connector/  # base(ABC), mock(Faker), taobao(占位), factory
│   │   ├── database/        # session (engine+Base+get_db)
│   │   ├── models/          # 7 张表 (ORM)
│   │   ├── schemas/         # Pydantic 请求模型
│   │   ├── api/v1/          # auth, shops, products, orders, conversations(AI+WS), ai, dashboard
│   │   └── services/        # embedding, chroma_client, llm, ai_suggest (Pipeline)
│   └── data/chroma/         # ChromaDB 持久化（自动）
├── frontend/
│   ├── vite.config.js       # :8080, proxy /api→:8010, /ws→:8010
│   └── src/
│       ├── router/          # 登录守卫 + 7 routes
│       ├── stores/auth.js   # Pinia token 持久化
│       ├── api/             # Axios 拦截器 + API 封装
│       └── views/           # 7 页面
└── docs/                    # 设计文档 + PROGRESS.md
```

---

## API 速查

所有接口 `Authorization: Bearer <JWT>`，Base: `/api/v1`

| 模块 | 方法 | 路径 | 说明 |
|------|------|------|------|
| Auth | POST | `/auth/login` | `{username, password}` → `{access_token, user}` |
| Auth | POST | `/auth/refresh` | `{refresh_token}` |
| Shops | GET | `/shops` | 店铺列表（含商品数/订单数） |
| Shops | POST | `/shops` | 绑定店铺 |
| Shops | DELETE | `/shops/{id}` | 解绑（级联） |
| Shops | POST | `/shops/{id}/sync` | 手动同步 |
| Products | GET | `/products` | 列表 `?shop_id=&keyword=&price_min=&price_max=&page=` |
| Products | GET | `/products/search` | 语义搜索 `?q=送礼` |
| Products | GET | `/products/{id}` | 详情 |
| Orders | GET | `/orders` | 列表 `?shop_id=&status=&page=` |
| Orders | GET | `/orders/{id}` | 详情 |
| Orders | POST | `/orders/{id}/refund` | 售后（Redis 并发锁） |
| Orders | GET | `/orders/pending-payment` | 未付单（催单用） |
| Orders | POST | `/orders/pending-payment/remind` | 一键催单 `{shop_id}` |
| Conv | GET | `/conversations` | 会话列表 `?shop_id=&handled_status=` |
| Conv | GET | `/conversations/{id}` | 详情（含 messages_json） |
| Conv | POST | `/conversations/{id}/assign` | 分配给我 |
| Conv | POST | `/conversations/{id}/close` | 关闭 |
| AI | POST | `/ai/suggest` | 话术建议 `{shop_id, buyer_question, product_id?}` |
| AI | POST | `/ai/campaign/pending-payment` | 催单话术 `{shop_id}` |
| AI | POST | `/ai/search` | 知识库搜索 `{query, top_k}` |
| Dash | GET | `/dashboard/metrics` | 看板指标 |
| WS | WS | `/ws/service?token=` | 实时通道（鉴权+心跳+ai_suggest） |

---

## AI Pipeline

```
买家问题
  → ChromaDB 向量检索 (商品知识 + 历史话术)
  → RRF 融合排序 (k=60)
  → Top-5 上下文 + LLM Prompt (qwen-max)
  → 3 条回复建议（各 ≤200 字）
  → 客服点击"复制/发送"→ 记录采纳
```

催单走同一 Pipeline 的 `generate_payment_reminders()` 分支：扫 pending 订单 → 每个订单查商品卖点（向量）→ LLM 生成千人千面话术。

---

## 多租户隔离

| 层 | 方式 |
|----|------|
| MySQL | 所有表 `WHERE merchant_id = ...`，JWT `Depends(get_current_merchant)` |
| ChromaDB | Collection `merchant_{merchant_id}` |
| Redis | Key 前缀 `m:{merchant_id}:...` |

一期单商户（id=1），架构已支持多商户扩展。

---

## vMall 集成

SaaS 可对接 [vMall 虚拟电商平台](../vmall_system/README.md) 获取真实业务数据。

**绑定流程：** 店铺管理 → 选择 vMall → 输入 API 地址 → 自动获取 Token → `/sync`

**物流感知 AI 话术：** `/ai/suggest` 自动查询 vMall 订单物流状态，注入 Prompt 生成精准回复
（"快递已到杭州中转站，预计2天送达"）。

**Webhook 消费：** `POST /api/v1/webhooks/vmall` 接收 ORDER_PAID / LOGISTICS_UPDATED / REFUND_SUCCESS 等事件。

**V3Connector：** `app/core/platform_connector/vmall.py` 实现 PlatformConnector ABC，对接 vMall OpenAPI。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3.4, Vite 5, Element Plus 2.5, Pinia 2, Axios, ECharts 5 |
| 后端 | Python 3.13, FastAPI 0.115, SQLAlchemy 2.0, Pydantic 2.10 |
| 数据库 | MySQL 8.0 (PyMySQL), Redis 7 (Memurai) |
| AI | DashScope text-embedding-v4 (1024维), qwen-max, ChromaDB (嵌入式) |
| Mock | Faker 33 (zh_CN)，20 条真实感商品模板，尺码/快递/质量三类会话 |

---

## 开发进度

| 阶段 | 状态 | 内容 |
|------|:---:|------|
| **一期** | ✅ 完成 | 多租户 + Mock + AI 话术 + 客服工作台 + 种子数据 |
| 二期 | ⏳ | 真实平台 API (淘宝/京东)、Celery 定时同步、话术风格自定义 |
| 三期 | ⏳ | 消费者端、智能 Agent 编排、多平台扩展 |

详细记录见 [docs/PROGRESS.md](docs/PROGRESS.md)。
