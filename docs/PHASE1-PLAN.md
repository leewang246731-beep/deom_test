# 一期实施计划 · 智能电商全链路平台

> 一期目标：跑通核心购买链路（用户 → 商品 → 推荐 → 购物车 → 订单）

---

## 一、一期范围

| 模块 | 范围 | 暂不做 |
|------|------|--------|
| 统一用户中心 | 注册/登录/JWT/角色(消费者) | 客服/管理员角色、短信验证 |
| 商品中心 | SPU/SKU、三级分类、库存、向量化 | 商品图OCR、批量导入 |
| 智能推荐引擎 | 协同过滤、语义检索、热门排行、个性化 | 卖点/尺码/搭配/比价 |
| 购物车/订单 | CRUD、结算预检、订单生命周期、支付Mock | 真实支付、物流 |

---

## 二、技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue3 + Vite + Element Plus + Pinia + Axios |
| 后端 | Python 3.10+ + FastAPI + SQLAlchemy 2.0 + Pydantic |
| 数据库 | MySQL 8.0 (demo_test) |
| 向量库 | ChromaDB |
| 缓存 | Redis 7 |

---

## 三、目录结构

```
D:\demo_test\
├── backend/
│   ├── main.py                    # FastAPI 入口
│   ├── .env                       # 环境变量
│   ├── requirements.txt
│   ├── config/
│   │   ├── __init__.py
│   │   └── config.py              # pydantic Settings
│   ├── database/
│   │   ├── __init__.py
│   │   └── session.py             # SQLAlchemy engine + session
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py                # User ORM
│   │   ├── category.py            # Category ORM
│   │   ├── product.py             # Product + SKU ORM
│   │   ├── cart.py                # (Redis only, no SQL table)
│   │   └── order.py               # Order + OrderItem ORM
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── user_schemas.py
│   │   ├── product_schemas.py
│   │   └── order_schemas.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── auth_router.py         # 注册/登录/刷新
│   │   ├── product_router.py      # 分类+商品+SKU+搜索
│   │   ├── recommend_router.py    # 推荐API
│   │   ├── cart_router.py         # 购物车API
│   │   └── order_router.py        # 订单API
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── product_service.py
│   │   ├── recommend_service.py   # 推荐算法
│   │   ├── cart_service.py
│   │   └── order_service.py
│   ├── utils/
│   │   ├── __init__.py
│   │   └── security.py            # JWT + 密码哈希
│   └── data/
│       ├── chroma/                # ChromaDB 持久化
│       └── uploads/               # 商品图片
├── frontend/
│   ├── index.html
│   ├── vite.config.js
│   ├── package.json
│   ├── src/
│   │   ├── main.js
│   │   ├── App.vue
│   │   ├── router/index.js
│   │   ├── stores/                # Pinia stores
│   │   │   ├── auth.js
│   │   │   ├── cart.js
│   │   │   └── product.js
│   │   ├── api/                   # Axios 封装
│   │   │   ├── index.js
│   │   │   ├── auth.js
│   │   │   ├── product.js
│   │   │   ├── recommend.js
│   │   │   ├── cart.js
│   │   │   └── order.js
│   │   ├── views/
│   │   │   ├── Home.vue           # 首页（推荐+热门）
│   │   │   ├── ProductList.vue    # 商品列表
│   │   │   ├── ProductDetail.vue  # 商品详情+SKU选择
│   │   │   ├── Cart.vue           # 购物车
│   │   │   ├── Checkout.vue       # 结算页
│   │   │   ├── Orders.vue         # 我的订单
│   │   │   ├── Login.vue          # 登录
│   │   │   └── Register.vue       # 注册
│   │   ├── components/
│   │   │   ├── NavBar.vue
│   │   │   ├── ProductCard.vue
│   │   │   └── SkuSelector.vue
│   │   └── assets/
│   └── .env.development
├── docs/                          # 已生成的设计文档
├── README.md
└── VIBE-CODING-PROMPTS.md
```

---

## 四、分步实施计划

---

### 步骤 1：数据库建表

**目标：** 在 MySQL 中创建 demo_test 数据库，执行所有表 DDL。

**任务：**

| # | 动作 | 验证方式 |
|---|------|---------|
| 1.1 | 连接 MySQL，创建数据库 `CREATE DATABASE demo_test` | `SHOW DATABASES` 能看到 demo_test |
| 1.2 | 执行 [数据库设计文档](database.md) 中一期相关的 9 张表：`users`, `roles`, `user_roles`, `categories`, `products`, `product_skus`, `orders`, `order_items`, `user_behaviors` | `SHOW TABLES` 能看到全部表 |
| 1.3 | 插入种子数据：3 个分类、8 个商品、对应 SKU | `SELECT COUNT(*) FROM products` ≥ 8 |
| 1.4 | 插入默认角色：consumer | `SELECT * FROM roles` |

> **为什么一期就要建 `user_behaviors`：** 步骤 5 的协同过滤 / 个性化推荐依赖用户浏览、加购行为数据。新系统初期该表为空，因此一期推荐**以"热门 + 语义相似"为主、协同过滤随行为数据积累逐步生效**（见步骤 5 说明）。

**✅ 验证点：** MySQL demo_test 库中 9 张表全部存在，种子数据可查询。

---

### 步骤 2：后端项目骨架

**目标：** FastAPI 项目能启动，连接 MySQL + Redis + ChromaDB 正常。

**任务：**

| # | 动作 | 验证方式 |
|---|------|---------|
| 2.1 | 创建 `backend/` 目录结构，初始化 `.env` | 文件存在 |
| 2.2 | 编写 `config/config.py`（pydantic Settings） | `python -c "from config.config import settings; print(settings.DB_NAME)"` 输出 demo_test |
| 2.3 | 编写 `database/session.py`（SQLAlchemy async engine） | 启动时无报错 |
| 2.4 | 编写 `utils/security.py`（JWT + bcrypt） | `python utils/security.py` 能生成/验证 token |
| 2.5 | 编写 `main.py`，挂载路由，`uvicorn` 启动 | `curl http://127.0.0.1:8010/docs` 能看到 Swagger |
| 2.6 | 连接 Redis 测试 | 后端启动日志显示 Redis 连接成功 |
| 2.7 | 连接 ChromaDB 测试 | 后端启动日志显示 ChromaDB 连接成功 |

**✅ 验证点：** `http://127.0.0.1:8010/docs` 可访问，Swagger 页面展示所有 API 路由。

---

### 步骤 3：用户系统（注册 + 登录 + JWT）

**目标：** 用户可以注册账号，登录后拿到 Token，前端用 Token 访问 API。

**后端任务：**

| # | 动作 | 验证方式 |
|---|------|---------|
| 3.1 | 编写 `models/user.py`（User ORM） | 数据库表已存在 |
| 3.2 | 编写 `schemas/user_schemas.py`（RegisterRequest, LoginRequest, TokenResponse） | 类型校验通过 |
| 3.3 | 编写 `services/auth_service.py`（注册/登录逻辑） | 单元测试 |
| 3.4 | 编写 `routers/auth_router.py`（/auth/register, /auth/login, /auth/me） | `curl -X POST http://127.0.0.1:8010/api/v1/auth/register -d '{"username":"test","password":"123456"}'` 返回 200 |
| 3.5 | 注册接口：检查用户名唯一、加密密码、返回 user id | 重复用户名返回 409 |
| 3.6 | 登录接口：验证密码、生成 JWT access_token + refresh_token | 错误密码返回 401 |
| 3.7 | /auth/me：验证 JWT，返回当前用户信息 | 无 Token 返回 401 |

**前端任务：**

| # | 动作 | 验证方式 |
|---|------|---------|
| 3.8 | `api/auth.js` Axios 封装 | 网络请求正常 |
| 3.9 | `stores/auth.js` Pinia store（token 存储+自动刷新） | 登录后 localStorage 有 token |
| 3.10 | `Login.vue` 登录页面 | 输入用户名密码 → 登录成功 → 跳转首页 |
| 3.11 | `Register.vue` 注册页面 | 注册成功 → 自动登录 → 跳转首页 |
| 3.12 | `NavBar.vue` 显示登录状态 | 未登录显示"登录"按钮，已登录显示用户名 |

**✅ 验证点：** 浏览器注册账号 → 登录 → NavBar 显示用户名 → 刷新页面不丢失登录状态。

---

### 步骤 4：商品中心（分类 + SPU/SKU + 搜索）

**目标：** 三层分类树、商品列表（分页+筛选）、商品详情（SKU 切换）、关键词搜索。

**后端任务：**

| # | 动作 | 验证方式 |
|---|------|---------|
| 4.1 | 编写 `models/category.py` + `models/product.py` | ORM 模型正确 |
| 4.2 | 编写 `schemas/product_schemas.py` | Pydantic 校验 |
| 4.3 | `GET /api/v1/categories` 返回树形分类 | curl 返回三级树 JSON |
| 4.4 | `GET /api/v1/products?category=&keyword=&sort=&page=` | 分页+筛选+排序 |
| 4.5 | `GET /api/v1/products/{id}` 返回 SPU 详情 + SKU 列表 | 含所有规格组合 |
| 4.6 | `GET /api/v1/products/search?q=手机` 关键词+语义搜索 | 返回相关商品 |
| 4.7 | 商品创建时自动生成 BGE-M3 Embedding 写入 ChromaDB | ChromaDB 有向量数据 |
| 4.8 | 为种子数据批量生成 Embedding | 8 个种子商品全部可被语义搜索 |

**前端任务：**

| # | 动作 | 验证方式 |
|---|------|---------|
| 4.9 | `api/product.js` | API 连通 |
| 4.10 | `stores/product.js`（商品列表缓存） | 切换分类不重复请求 |
| 4.11 | `ProductList.vue` 商品列表页（分类侧边栏 + 分页 + 排序） | 点击分类过滤商品 |
| 4.12 | `ProductCard.vue` 商品卡片组件（图片+名称+价格） | 列表展示正常 |
| 4.13 | `ProductDetail.vue` 商品详情页（图文+SKU选择器） | 切换 SKU 更新价格/库存 |
| 4.14 | `SkuSelector.vue` 规格选择组件 | 选择颜色+内存，显示对应 SKU |
| 4.15 | `Home.vue` 首页展示热门推荐 | 商品卡片渲染 |

**✅ 验证点：** 首页→点击商品→详情页切换SKU→价格变化→点击搜索→返回相关商品。

---

### 步骤 5：智能推荐引擎

**目标：** 首页混合推荐（热门+个性化+协同过滤）、商品详情页关联推荐。

> **冷启动策略：** 新系统初期无行为/订单数据，协同过滤无数据可算。一期推荐**以"热门 + 语义相似"为主**作为兜底，随 `user_behaviors` 与 `orders` 数据积累，个性化与协同过滤逐步生效。因此先做埋点（5.2），再做依赖数据的算法。

**后端任务：**

| # | 动作 | 验证方式 |
|---|------|---------|
| 5.1 | 编写 `services/recommend_service.py` | — |
| 5.2 | 行为埋点：浏览/搜索/加购写入 `user_behaviors`（详情页、加购接口埋点） | `SELECT COUNT(*) FROM user_behaviors` 随操作增长 |
| 5.3 | 语义检索：基于 ChromaDB 查询相似商品（无行为数据也可用） | `GET /api/v1/recommend/similar/{id}` 返回相似商品 |
| 5.4 | 热门排行：从 orders 表聚合销量写入 Redis ZSet，无订单时按 `sold_count` 兜底 | `GET /api/v1/recommend/hot` 返回排行榜 |
| 5.5 | 协同过滤：基于 `user_behaviors` 行为矩阵计算 ItemCF，数据不足时回退热门 | 有行为后 `GET /api/v1/recommend/home` 出现协同过滤 Section |
| 5.6 | 个性化推荐：基于用户浏览历史加权，新用户回退热门 | 浏览商品后推荐偏好变化 |
| 5.7 | `GET /api/v1/recommend/home` 混合返回多 Section（热门/个性化/协同） | 响应含 sections 数组 |
| 5.8 | `GET /api/v1/recommend/product/{id}` 商品详情页推荐 | 含"看了又看""买了又买" |

**前端任务：**

| # | 动作 | 验证方式 |
|---|------|---------|
| 5.9 | `api/recommend.js` | API 连通 |
| 5.10 | `Home.vue` 推荐 Section 渲染 | 可看到"为你推荐""热门商品"等分区 |
| 5.11 | `ProductDetail.vue` 底部推荐区域 | 详情页下方展示推荐商品 |
| 5.12 | 推荐商品卡片点击跳转 | 点击推荐商品进入对应详情页 |

**✅ 验证点：** 首页有多个推荐分区、详情页有"看了又看"、浏览某类商品后推荐偏好变化。

---

### 步骤 6：购物车（Redis）

**目标：** 用户可加购、修改数量、删除、看到实时库存。

**后端任务：**

| # | 动作 | 验证方式 |
|---|------|---------|
| 6.1 | 编写 `services/cart_service.py`（Redis Hash 操作） | — |
| 6.2 | `GET /api/v1/cart` 返回购物车商品列表 + 库存状态 | curl 返回 [{sku_id, name, specs, price, quantity, stock}] |
| 6.3 | `POST /api/v1/cart/items` 添加商品，检查库存 | 超库存返回 409 |
| 6.4 | `PUT /api/v1/cart/items/{sku_id}` 修改数量 | 数量变化 |
| 6.5 | `DELETE /api/v1/cart/items/{sku_id}` 删除 | 购物车移除 |
| 6.6 | 未登录购物车存 localStorage，登录后合并到 Redis | 合并逻辑正确 |
| 6.7 | `POST /api/v1/cart/checkout-check` 结算预检（价格/库存/优惠） | 返回可结算/不可结算+原因 |

**前端任务：**

| # | 动作 | 验证方式 |
|---|------|---------|
| 6.8 | `api/cart.js` + `stores/cart.js` | 状态管理正确 |
| 6.9 | `Cart.vue` 购物车页面（列表+数量调整+总价） | 修改数量，总价实时更新 |
| 6.10 | 商品详情页"加入购物车"按钮 + Toast 提示 | 加购成功提示 |
| 6.11 | NavBar 购物车图标 + 数量角标 | 加购后角标数字变化 |

**✅ 验证点：** 详情页加购 → NavBar 角标+1 → 购物车页看到商品 → 修改数量总价变化 → 删除商品。

---

### 步骤 7：订单系统（Mock 支付）

**目标：** 购物车结算 → 生成订单 → Mock 支付 → 订单状态流转。

**后端任务：**

| # | 动作 | 验证方式 |
|---|------|---------|
| 7.1 | 编写 `models/order.py`（Order + OrderItem） | ORM 正确 |
| 7.2 | 编写 `services/order_service.py` | — |
| 7.3 | `POST /api/v1/orders` 创建订单：扣减库存(Redis分布式锁)、生成订单号、清空购物车 | 并发创建不超卖 |
| 7.4 | `GET /api/v1/orders` 订单列表 ?status=&page= | 分页过滤 |
| 7.5 | `GET /api/v1/orders/{id}` 订单详情（含商品明细） | 完整订单数据 |
| 7.6 | `POST /api/v1/orders/{id}/pay` Mock 支付：直接标记已支付 | 状态变为"已支付" |
| 7.7 | `POST /api/v1/orders/{id}/cancel` 取消订单：恢复库存 | 库存恢复 |
| 7.8 | `POST /api/v1/orders/{id}/confirm` 确认收货 | 状态→已完成 |

**前端任务：**

| # | 动作 | 验证方式 |
|---|------|---------|
| 7.9 | `api/order.js` | API 连通 |
| 7.10 | `Checkout.vue` 结算页（收货地址+商品清单+Mock支付按钮） | 从购物车跳转，清单一致 |
| 7.11 | 支付按钮 → POST /pay → 提示"支付成功" → 跳转订单列表 | 订单状态变为已支付 |
| 7.12 | `Orders.vue` 订单列表（Tab切换状态） | 待支付/已支付/已完成 分Tab |
| 7.13 | 订单详情（商品+金额+状态+时间线） | 取消按钮在待支付状态可见 |

**✅ 验证点：** 购物车 → 结算 → Mock支付 → 订单列表看到已支付订单 → 确认收货 → 状态变成已完成。

---

## 五、实施顺序依赖

```
步骤1: 数据库建表
  └─→ 步骤2: 后端骨架
        ├─→ 步骤3: 用户系统
        │     └─→ 步骤4: 商品中心 (需要 /auth/me)
        │           ├─→ 步骤5: 推荐引擎 (需要商品+ChromaDB向量)
        │           │     └─→ 步骤6: 购物车 (需要商品+用户)
        │           │           └─→ 步骤7: 订单 (需要购物车+商品)
        │           └─→ 步骤6: 购物车
        │                 └─→ 步骤7: 订单
        └─→ 步骤4: 商品中心 (非依赖用户系统的接口可并行)
```

**不能跳过的依赖链：** DB → 后端骨架 → 用户 → 商品 → 推荐/购物车 → 订单

---

## 六、每个步骤的验证检查表

### 步骤1 验证
- [ ] `mysql -u root -p -e "USE demo_test; SHOW TABLES;"` 显示 9 张表（密码交互输入，勿写命令行）
- [ ] `SELECT COUNT(*) FROM products` ≥ 8

### 步骤2 验证
- [ ] `http://127.0.0.1:8010/docs` 可访问
- [ ] `http://127.0.0.1:8010/api/v1/health` 返回 `{"status":"ok"}`
- [ ] 后端日志无 MySQL/Redis/ChromaDB 连接错误

### 步骤3 验证
- [ ] 注册新用户返回 200
- [ ] 重复用户名返回 409
- [ ] 错误密码返回 401
- [ ] 登录后 `/auth/me` 返回用户信息
- [ ] 无 Token 请求 `/auth/me` 返回 401

### 步骤4 验证
- [ ] `/api/v1/categories` 返回树形 JSON（3级）
- [ ] `/api/v1/products?category=1` 返回该分类商品
- [ ] `/api/v1/products?keyword=手机` 返回匹配商品
- [ ] `/api/v1/products/{id}` 含 SKU 列表+库存
- [ ] `/api/v1/products/search?q=拍照` 语义搜索返回相关商品

### 步骤5 验证
- [ ] `/api/v1/recommend/home` 返回 sections 数组
- [ ] `/api/v1/recommend/product/{id}` 返回关联推荐
- [ ] `/api/v1/recommend/similar/{id}` 返回语义相似商品
- [ ] `/api/v1/recommend/hot` 返回热门排行
- [ ] 浏览/加购后 `user_behaviors` 有数据写入

### 步骤6 验证
- [ ] 加购后 `GET /api/v1/cart` 返回商品列表
- [ ] 超出库存加购返回 409
- [ ] 结算预检返回可结算状态
- [ ] 前端购物车角标数字正确

### 步骤7 验证
- [ ] 创建订单后库存减少
- [ ] 并发下单不超卖
- [ ] Mock 支付后状态更新
- [ ] 取消订单库存恢复
- [ ] 确认收货后状态→已完成

---

## 七、时间估算

| 步骤 | 内容 | 预计 |
|:---:|------|:---:|
| 1 | 数据库建表 + 种子数据 | 0.5天 |
| 2 | 后端骨架 | 1天 |
| 3 | 用户系统（前后端） | 1.5天 |
| 4 | 商品中心（前后端） | 2天 |
| 5 | 推荐引擎（前后端） | 2天 |
| 6 | 购物车（前后端） | 1天 |
| 7 | 订单系统（前后端） | 1.5天 |
| **总计** | | **9.5天 ≈ 2周** |

---

## 八、注意事项

1. **所有 API 返回格式统一：** `{"code": 200, "data": {...}, "message": "success"}`
2. **Redis key 前缀：** 统一用 `demo:` 隔离（如 `demo:cart:1`、`demo:hot_products`），避免与 project_test 的 Redis 数据冲突
3. **MySQL 库隔离：** demo_test 与 project_test 是不同数据库，不会互相影响
4. **种子商品数据用真实品类：** 手机/电脑/耳机等，让推荐效果可见
5. **前端先不做响应式移动端：** 一期只做 PC 端
6. **支付用 Mock：** 点击"支付"直接调用 `/pay` 接口标记已支付，不做真实对接
