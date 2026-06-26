# 部署指南 — 多平台智能托管 SaaS v2.0.1

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

### Docker 部署

```bash
# 构建镜像
docker build -t saas-backend:latest -f backend/Dockerfile .

# 启动
docker-compose up -d
```

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

# AI — 必须配置有效 Key
DASHSCOPE_API_KEY=<your-dashscope-key>

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
:8012  SaaS 后端 API
:8020  vMall 后端 API (可选)
:8093  平台管理前端
:8094  商户工作台前端
:8095  客服工作台前端
:8090  vMall 买家 H5 (可选)
:8091  vMall 商户端 (可选)
:8092  vMall 运营后台 (可选)
:3306  MySQL
:6379  Redis
```

## 常见问题

### 语义搜索返回空结果
运行 `python seed.py --backfill --full` 生成商品向量（需要有效的 DASHSCOPE_API_KEY）。

如果 DashScope API 不可用，语义搜索会自动降级为 SQL LIKE 模糊搜索。

### Platform Login 不可用
重启 FastAPI 服务器。首次启动时确保 `platform_user` 模型文件存在。

### 跨境系统同步失败
1. 确认 vMall 后端已启动 (:8020)
2. 确认已完成店铺绑定（bind_status=active）
3. 确认 access_token 已获取（检查 platform_shops 表）
4. 查看 SaaS 日志中的 connector 错误

### Redis 连接失败
Windows 环境下可使用 Memurai 或 WSL 中的 Redis。
