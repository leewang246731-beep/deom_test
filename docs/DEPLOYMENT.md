# 部署指南 — 多平台智能托管 SaaS v2.2.0

## 环境要求

| 组件 | 最低版本 | 用途 |
|------|:------:|------|
| Python | 3.10+ | 后端运行时 |
| MySQL | 8.0 | 主数据库 |
| Redis | 6.0+ | 缓存 + 分布式锁 |
| Node.js | 18+ | 前端构建 |
| ChromaDB | (嵌入式) | 向量存储 |

## 快速启动（开发环境）

### 1. 验证环境

```bash
cd backend
python verify.py
```

### 2. 安装依赖

```bash
# 后端
cd backend
pip install -r requirements.txt

# 前端
cd ../frontend
npm install
```

### 3. 配置环境变量

```bash
cd backend
# 编辑 .env，确保以下配置正确：
#   DB_HOST, DB_PORT, DB_USER, DB_PASSWORD, DB_NAME
#   REDIS_HOST, REDIS_PORT
#   DASHSCOPE_API_KEY  (AI 功能必需)
#   PLATFORM_MODE=mock (开发模式)
```

### 4. 初始化数据库

```bash
cd backend
# 基础数据（商户/用户/商品/订单）
python seed.py --backfill --full

# 验证
python verify.py
```

### 5. 启动服务

```bash
# 终端1: 后端
cd backend
uvicorn main:app --host 0.0.0.0 --port 8012

# 终端2: 平台管理前端
cd frontend
npm run dev:admin      # :8093

# 终端3: 商户工作台
npm run dev:merchant   # :8094

# 终端4: 客服工作台
npm run dev:service    # :8095
```

### 6. 验证启动

```bash
# 健康检查
curl http://localhost:8012/api/v1/health

# 冒烟测试
cd backend
python test_e2e_smoke.py
```

### 7. 登录验证

| 入口 | 地址 | 账号 | 密码 |
|------|------|------|------|
| 平台管理 | http://localhost:8093 | super_admin | 123456 |
| 商户工作台 | http://localhost:8094 | admin | 123456 |
| 客服工作台 | http://localhost:8095 | service | 123456 |

## vMall 系统启动（跨系统联调）

```bash
# 终端5: vMall 后端
cd vmall_system/backend
pip install -r requirements.txt
python seed_vmall.py
uvicorn main:app --host 0.0.0.0 --port 8020

# 终端6: vMall 买家H5
cd vmall_system/frontend_consumer
npm install && npm run dev     # :8090

# 终端7: vMall 商户端
cd vmall_system/frontend_merchant
npm install && npm run dev     # :8091
```

### 跨系统绑定流程

1. SaaS 管理后台 (:8093) → 店铺管理 → 绑定 vMall 店铺 → 生成绑定码
2. vMall 商户端 (:8091) → SaaS 绑定 → 输入 SaaS URL + 绑定码 → 确认
3. 绑定成功后，SaaS 侧自动获取 access_token
4. 回到 SaaS 店铺管理 → 点击同步 → 拉取 vMall 商品/订单数据

## 生产部署

### Docker 部署（推荐，一键起栈）

整个栈（MySQL/Redis/后端/前端，可选 vMall）由 `docker-compose.yml` 编排。后端容器启动时自动建表 + 迁移 + `seed.py --backfill --full`（幂等），无需手动初始化。

```bash
# 在仓库根目录
# 仅 SaaS 栈
docker compose up -d --build

# SaaS + vMall 完整栈
docker compose --profile full up -d --build

# 全新重建（清空数据卷，重新 seed）：
docker compose --profile full down -v
docker compose --profile full up -d --build
```

> **API Key 注入**：compose 通过 `${DASHSCOPE_API_KEY}` 从宿主环境或仓库根 `.env`（已 gitignore）读取，会覆盖镜像内 `backend/.env`。确保起栈前该变量为有效 key，否则 AI 功能走降级兜底。MySQL/Redis 仅在内部网络，不暴露宿主端口。

> **跨系统 URL（容器互通必读）**：vMall→SaaS 的 webhook 与 SaaS→vMall 的回流，使用容器服务名而非 localhost。由 `SAAS_BASE_URL`（默认 `http://saas-backend:8012`）与 `VMALL_BASE_URL`（默认 `http://vmall-backend:8020`）控制，compose 已注入；seed 据此写入。**宿主裸跑（非 Docker）时**需把这两个变量改为 `http://127.0.0.1:8012` / `http://127.0.0.1:8020`，否则跨系统消息/事件无法互达。

#### 容器内验证

```bash
docker compose ps                                    # 全部 healthy
docker exec saas-backend python verify.py            # 环境自检 27 项
docker exec saas-backend pip install -q pytest       # 生产镜像不含 pytest，按需安装
docker exec saas-backend python -m pytest tests/ -q  # RAG 回归 10 项
docker exec saas-backend python test_e2e_smoke.py    # E2E 冒烟 78 项（容器内直连）
docker exec saas-backend python test_edge_cases.py   # 跨系统边缘场景 16 项（钱包/售后/越权/校验/AI兜底）
curl http://localhost:8012/api/v1/health             # llm/db/redis/chromadb 均 connected
```

> **AI 兜底链**：主模型 qwen 失败时自动切 DeepSeek，再不行走场景化模板，端点不会返回空。配置 `DEEPSEEK_API_KEY`（compose 注入）即生效。
> **客服模式**：客服工作台（:8095）会话头部可切「人工 / 辅助 / 全自动」；切到全自动后，买家消息由 AI（含 DeepSeek 兜底）自动回复并回流消费端。

### 环境变量（生产）

```ini
# 数据库
DB_HOST=your-mysql-host
DB_PORT=3306
DB_USER=saas_user
DB_PASSWORD=<strong-password>
DB_NAME=saas_prod

# JWT — 必须修改！
JWT_SECRET=<random-64-char-string>
JWT_ALGORITHM=HS256

# Redis
REDIS_HOST=your-redis-host
REDIS_PORT=6379
REDIS_PASSWORD=<redis-password>

# 平台模式
PLATFORM_MODE=real

# AI — 必须配置有效 Key (DashScope OpenAI 兼容模式)
DASHSCOPE_API_KEY=<your-dashscope-key>
LLM_MODEL=qwen-plus                   # qwen-plus / qwen-max / qwen-turbo
LLM_API_BASE=https://dashscope.aliyuncs.com/compatible-mode/v1

# vMall 集成
OPENAPI_KEY=<shared-secret-with-vmall>
```

### 安全检查清单

- [ ] JWT_SECRET 已更换为强随机字符串
- [ ] MySQL 密码已更换
- [ ] Redis 密码已设置
- [ ] OPENAPI_KEY 已与 vMall 协商
- [ ] CORS origins 已限制为前端域名
- [ ] HTTPS 已配置
- [ ] 日志级别设为 INFO 或以上

## 端口布局

```
:8012  SaaS 后端 API (含 KB 文件上传、文档解析)
:8020  vMall 后端 API (可选)
:8093  平台管理前端 (含企业知识库多格式文档上传)
:8094  商户工作台前端
:8095  客服工作台前端 (含知识库文件上传)
:8090  vMall 买家 H5 (可选)
:8091  vMall 商户端 (可选)
:8092  vMall 运营后台 (可选)
:3306  MySQL (内部)
:6379  Redis (内部)
```

## 优惠券系统（v2.2.0 新增）

### 功能概述

- **售后补偿**：物流延迟 / 质量问题 / 服务投诉 3 种场景，自动校验订单状态+冷却期+次数上限
- **售前营销**：新用户 / VIP / 全场 3 种活动类型，库存扣减+用户定向+每人限领
- **Agent 集成**：LLM 自动判断意图，调用 `compensate` / `issue_promo` 工具发券
- **降级开关**：`.env` 中 `ENABLE_AUTO_COUPON=False` 可一键关闭 AI 自动发券，全部转人工

### API 端点

```
GET    /api/v1/coupons/compensation-policies    # 补偿策略列表
POST   /api/v1/coupons/compensation-policies    # 创建策略
PUT    /api/v1/coupons/compensation-policies/{id} # 更新策略
DELETE /api/v1/coupons/compensation-policies/{id} # 删除策略
GET    /api/v1/coupons/marketing-campaigns      # 营销活动列表
POST   /api/v1/coupons/marketing-campaigns      # 创建活动
PUT    /api/v1/coupons/marketing-campaigns/{id} # 更新活动
DELETE /api/v1/coupons/marketing-campaigns/{id} # 删除活动
GET    /api/v1/coupons/grant-logs               # 发放日志（支持按 type/user/order 筛选）
GET    /api/v1/coupons/active-campaigns         # 当前有效活动
```

### 环境变量

```ini
ENABLE_AUTO_COUPON=True   # AI 自动发券开关，False 时全部转人工
```

## 增强商品推荐引擎（v2.2.0 新增）

### 功能概述

- **多维画像**：基础属性 + 兴趣标签 + 消费特征 + 偏好事实 + 近期意图 + 活跃度 6 维融合
- **记忆压缩**：会话中提取关键信息（噪音过滤→LLM提取→合并长期记忆），Snippets 上限 5，Tags 上限 20
- **多路召回**：标签向量 + 协同过滤 + 规则匹配 + 消费带 + 热门兜底 5 路并行
- **策略排序**：个性化匹配(0.4) + 价格匹配(0.2) + 商户策略(0.2) + 时效性(0.2) 4 因子加权
- **个性化理由**：基于画像与商品属性规则模板生成，避免 LLM 幻觉

### Agent 工具

```
recommend(user_id, need_tags, top_k)         # 基于画像推荐商品
get_profile_summary(user_id)                 # 获取用户多维画像摘要
update_user_fact(user_id, key, value)        # 更新用户偏好事实
compress_conversation_tool(user_id, snippet) # 记忆压缩（会话结束调用）
```

### 数据表

- `long_term_memories` — 跨会话用户画像（facts/tags/snippets/stats）
- 4 个 Agent 工具已注册到 ToolRegistry（tags: profile/recommendation/memory）

## 会话去重（v2.2.0 修复）

vMall 消费者端创建会话时，同 buyer + 同 product + status=open 的会话自动复用，避免同一商品重复创建会话窗口。已关闭的会话不受影响。
```
PDF (.pdf)    — pypdf
Word (.docx)  — python-docx
Excel (.xlsx) — openpyxl
PPT (.pptx)   — python-pptx
MD/TXT/CSV    — 内置解析
```
文件最大 50MB，上传后在后台异步处理。上传目录：`backend/data/uploads/`，Docker 中为 `upload_data` volume。

## 常见问题

### 语义搜索返回空结果
运行 `python seed.py --backfill --full` 生成商品向量。v2.1.1 起商品同步/创建后自动触发向量回填，无需手动操作。

如果 DashScope API 不可用，语义搜索会自动降级为 SQL LIKE 模糊搜索。LLM 调用失败时自动降级为场景化模板话术。

### Platform Login 不可用
重启 FastAPI 服务器。首次启动时确保 `platform_user` 模型文件存在且服务器已重启加载。

### LLM 调用返回空或超时
1. 确认 `.env` 中 `DASHSCOPE_API_KEY` 有效
2. 确认 `LLM_MODEL` 模型名称正确（默认 `qwen-plus`）
3. 系统内置 2 次自动重试 + 降级兜底，不会因单次失败而返回空数据

### 跨境系统同步失败
1. 确认 vMall 后端已启动 (:8020)
2. 确认已完成店铺绑定（bind_status=active）
3. 确认 access_token 已获取（检查 platform_shops 表）
4. 查看 SaaS 日志中的 connector 错误

### Redis 连接失败
Windows 环境下可使用 Memurai 或 WSL 中的 Redis。
