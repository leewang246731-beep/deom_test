# 配置文档 · 多平台智能托管 SaaS 平台

> 基于 D:\project_test 现有配置，多租户隔离，Mock 模式开箱即用

---

## 一、Backend .env

```env
# ===== 数据库配置 (MySQL 8.0) =====
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=121300
DB_NAME=demo_test

# ===== JWT =====
JWT_SECRET=demo-ecom-secret-2026-please-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ===== Redis =====
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_PASSWORD=

# ===== ChromaDB =====
CHROMA_PERSIST_DIR=./data/chroma

# ===== RabbitMQ (Celery) =====
RABBITMQ_HOST=127.0.0.1
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

# ===== Platform Mode =====
# mock = 使用 Faker 生成虚拟数据，无需外部平台
# real = 使用真实平台 API
PLATFORM_MODE=mock

# ===== LLM API =====
DASHSCOPE_API_KEY=sk-b67...474c

# ===== AI =====
EMBEDDING_MODEL=BAAI/bge-m3
RAG_TOP_K=20
AI_SUGGEST_COUNT=3

# ===== 可选：外部推送 =====
DINGTALK_WEBHOOK_URL=
WECOM_WEBHOOK_URL=
FEISHU_WEBHOOK_URL=
```

---

## 二、端口映射

```
demo_test 项目                  project_test 项目（已有，不冲突）
┌────────────────────┐          ┌────────────────────┐
│ Frontend :8080     │          │ Frontend :80       │
│ Backend  :8010     │          │ Backend  :8000     │
│ MySQL    :3308     │          │ MySQL    :3307     │
│ Redis    :6379 共享│←────────→│ Redis    :6379     │
│ RabbitMQ :5672     │          │                    │
│ ChromaDB :8001     │          │                    │
└────────────────────┘          └────────────────────┘
```

---

## 三、需要你提供的配置

| # | 配置项 | 来源 | 状态 |
|---|--------|------|:---:|
| 1 | MySQL root:121300 | project_test 共享 | ✅ 已有 |
| 2 | DashScope API Key | project_test 共享 | ✅ 已有 |
| 3 | Redis | 本地默认 | ✅ 已有 |
| 4 | JWT Secret | 已生成 | ✅ 已生成 |

> Mock 模式下无需任何外部平台 Key。

---

## 四、确认清单

| 检查项 | 状态 |
|--------|:---:|
| MySQL 库名不冲突 (demo_test ≠ project_test) | ✅ |
| Backend 端口不冲突 (8010 ≠ 8000) | ✅ |
| Frontend 端口不冲突 (8080 ≠ 80) | ✅ |
| Redis 共用（不同 Key 前缀 m:1: vs m:2:） | ✅ |
| ChromaDB Collection 按商户隔离 (merchant_1 / merchant_2) | ✅ |
| Mock 模式不开真实网络请求 | ✅ |
