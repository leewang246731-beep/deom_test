# 配置文档 · 智能电商全链路平台

> 基于 D:\project_test 现有配置，调整端口/库名/容器名确保两项目零冲突

---

## 一、冲突对比与调整

| 配置项 | project_test (已有) | demo_test (新项目) | 冲突？ |
|--------|---------------------|---------------------|:---:|
| MySQL 端口 (Docker) | 3307→3306 | **3308→3306** | ✅ 避开 |
| MySQL 端口 (本地) | 3306 | 3306 (同机不同库) | ✅ 安全 |
| MySQL 数据库名 | project_test | **demo_test** | ✅ 避开 |
| Backend 端口 | 8000 | **8010** | ✅ 避开 |
| Frontend 端口 | 80 | **8080** | ✅ 避开 |
| MySQL 容器名 | machine-kb-mysql | **demo-ecom-mysql** | ✅ 避开 |
| Backend 容器名 | machine-kb-backend | **demo-ecom-backend** | ✅ 避开 |
| Frontend 容器名 | machine-kb-frontend | **demo-ecom-frontend** | ✅ 避开 |
| Docker 网络 | app-network | **demo-network** | ✅ 避开 |
| Docker Volume | mysql_data | **demo_mysql_data** | ✅ 避开 |
| Docker Volume | chroma_data | **demo_chroma_data** | ✅ 避开 |

---

## 二、共享配置（两个项目共用，无需修改）

> ⚠️ **密钥不写入文档/不入库**：下表中 MySQL 密码、DashScope Key 等敏感值一律放在本地 `.env`（已加入 `.gitignore`），此处仅说明来源，不写明文。

| 配置项 | 值 | 来源 |
|--------|-----|------|
| MySQL Host | `127.0.0.1` | project_test .env |
| MySQL User | `root` | project_test .env |
| MySQL Password | `<见本地 .env，勿入库>` | project_test .env |
| Redis Host | `127.0.0.1` | 本地默认 |
| Redis Port | `6379` | 本地默认 |
| Redis DB 编号 | `1`（project_test 用 `0`） | 用独立 DB 号隔离 |
| DashScope API Key | `<见本地 .env，勿入库>` | project_test .env |
| JWT Algorithm | `HS256` | project_test config |
| Access Token 有效期 | `30` 分钟 | project_test config |
| Refresh Token 有效期 | `7` 天 | project_test config |
| 分页大小 | `10` | project_test config |
| Bcrypt Rounds | `12` | project_test config |
| RAG Chunk Size | `384` | project_test config |
| RAG Chunk Overlap | `48` | project_test config |
| RAG Top-K | `20` | project_test config |
| RAG Rerank Top-N | `5` | project_test config |

---

## 三、差异化配置（新项目独立设置）

| 配置项 | project_test | demo_test | 说明 |
|--------|:-----------:|:---------:|------|
| 数据库名 | project_test | **demo_test** | 独立数据库 |
| Backend 端口 | 8000 | **8010** | 互不冲突 |
| Frontend 端口 | 80 | **8080** | 互不冲突 |
| API 前缀 | /api/v1 | **/api/v1** | 全项目统一带 v1 |
| Redis DB 号 | 0 | **1** | 同实例不同 DB 号隔离 |
| JWT Secret | `<本地 .env>` | `<本地 .env，勿入库>` | 独立密钥，不写明文 |
| RabbitMQ 端口 | — | **5672**（二期起用） | 一期核心链路不需要 |

---

## 四、需要你提供的新配置

以下三项是 project_test 没有的，需要你提供：

| # | 配置项 | 说明 |
|---|--------|------|
| 1 | **千问VL / GPT-4V API Key** | 商品图OCR提取特征。千问VL与 DashScope 同Key（已有），GPT-4V 需 OpenAI Key |
| 2 | **钉钉/飞书/企微 Webhook URL** | 场景策略通知推送。可选，一期可先不做 |
| 3 | **短信服务商 Key** | 用户注册短信验证。可选，一期可用 Mock |
| 4 | **支付配置** | 支付宝/微信支付。可选，一期可 Mock |

> **如果你暂时不提供以上 4 项，一期开发不受影响。** OCR 功能可延后到二期，推送/短信/支付可先用 Mock 占位。

---

## 五、Backend .env 文件（可直接使用）

```env
# ⚠️ 本文件含密钥，必须加入 .gitignore，切勿提交到版本库。
# 下方所有 <...> 占位符请在本地填写真实值。

# ===== 数据库配置 (MySQL 8.0) =====
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=<your-mysql-password>
DB_NAME=demo_test

# ===== JWT 鉴权配置 =====
JWT_SECRET=<generate-a-random-secret>
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# ===== 项目配置 =====
API_PREFIX=/api/v1
PAGE_SIZE=10
BCRYPT_ROUNDS=12

# ===== Redis 配置 =====
REDIS_HOST=127.0.0.1
REDIS_PORT=6379
REDIS_DB=1
REDIS_PASSWORD=

# ===== RabbitMQ 配置（二期起启用，一期可留空不连接） =====
RABBITMQ_HOST=127.0.0.1
RABBITMQ_PORT=5672
RABBITMQ_USER=guest
RABBITMQ_PASSWORD=guest

# ===== RAG / DashScope 配置 =====
DASHSCOPE_API_KEY=<your-dashscope-key>
CHROMA_PERSIST_DIR=./data/chroma
UPLOAD_DIR=./data/uploads
UPLOAD_MAX_MB=50
RAG_CHUNK_SIZE=384
RAG_CHUNK_OVERLAP=48
RAG_TOP_K=20
RAG_RERANK_TOP_N=5
RAG_USE_RERANK=true

# RAG 优化开关
RAG_USE_QUERY_REWRITE=true
RAG_USE_REORDER=true
RAG_USE_HYBRID=true
RAG_USE_COMPRESS=true
RAG_USE_HYDE=true

# ===== 新增：AI 增强配置 =====
# 商品图 OCR（千问VL，与 DashScope 同Key，留空则用 DashScope Key）
VISION_API_KEY=

# 外部推送 Webhook（可选）
DINGTALK_WEBHOOK_URL=
WECOM_WEBHOOK_URL=
FEISHU_WEBHOOK_URL=

# 短信服务（可选）
SMS_PROVIDER=
SMS_API_KEY=
SMS_API_SECRET=

# 支付（可选）
ALIPAY_APP_ID=
ALIPAY_PRIVATE_KEY=
ALIPAY_PUBLIC_KEY=
WECHAT_APP_ID=
WECHAT_MCH_ID=
WECHAT_API_KEY=
```

---

## 六、Docker Compose 端口映射

```
demo_test 项目（新）              project_test 项目（已有）
┌────────────────────┐           ┌────────────────────┐
│ Frontend :8080     │           │ Frontend :80       │
│ Backend  :8010     │           │ Backend  :8000     │
│ MySQL    :3308→3306│           │ MySQL    :3307→3306│
│ Redis    :6379     │  共享 ←→  │ Redis    :6379     │
│ RabbitMQ :5672     │           │                    │
│ ChromaDB :8001     │           │ ChromaDB :嵌入后端  │
└────────────────────┘           └────────────────────┘
```

---

## 七、确认清单

| 检查项 | 状态 |
|--------|:---:|
| MySQL 库名不冲突 (demo_test ≠ project_test) | ✅ |
| Backend 端口不冲突 (8010 ≠ 8000) | ✅ |
| Frontend 端口不冲突 (8080 ≠ 80) | ✅ |
| Docker 容器名不冲突 | ✅ |
| Docker 网络不冲突 | ✅ |
| Docker Volume 不冲突 | ✅ |
| DashScope Key 共用（仅存本地 .env，不入库） | ✅ |
| Redis 共用 (不同 DB 号 + key 前缀双重隔离) | ✅ |
| 本地 MySQL 共用 (不同库) | ✅ |
| 所有密钥不写入文档/不提交 git | ✅ |
