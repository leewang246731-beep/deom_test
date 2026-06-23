# 数据库设计 · 智能电商全链路平台

---

## 一、ER 图（核心表）

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   users     │────<│ user_profiles │     │   roles     │
│  id         │     │  user_id (FK) │     │  id         │
│  username   │     │  gender       │     │  name       │
│  password   │     │  age_range    │     │  code       │
│  phone      │     │  preferences  │     └──────┬──────┘
│  role_id    │──┐  │  rfm_score    │            │
└─────────────┘  │  └──────────────┘     ┌──────┴──────┐
                 └────────────────────────│user_roles   │
                                          │ user_id     │
┌─────────────┐     ┌──────────────┐     │ role_id     │
│ categories  │────<│  products    │     └─────────────┘
│  id         │     │  id          │
│  name       │     │  category_id │     ┌──────────────┐
│  parent_id  │     │  name        │     │ product_skus │
│  level      │     │  description │────<│  id          │
└─────────────┘     │  brand       │     │  product_id  │
                    │  status      │     │  sku_code    │
                    └──────┬───────┘     │  specs       │
                           │             │  price       │
┌─────────────┐     ┌──────┴───────┐     │  stock       │
│   orders    │────<│ order_items  │     └──────────────┘
│  id         │     │  id          │
│  user_id    │     │  order_id    │     ┌──────────────┐
│  total      │     │  sku_id      │────>│   tickets    │
│  status     │     │  quantity    │     │  id          │
│  payment_id │     │  price       │     │  user_id     │
└─────────────┘     └──────────────┘     │  order_id    │
                                         │  type        │
┌──────────────┐     ┌──────────────┐    │  status      │
│ user_behaviors│    │  chat_history│    │  priority    │
│  id          │     │  id          │    │  agent_id    │
│  user_id     │     │  user_id     │    └──────────────┘
│  action      │     │  session_id  │
│  target_id   │     │  role        │    ┌──────────────┐
│  context     │     │  content     │    │  coupons     │
│  created_at  │     │  intent      │    │  id          │
└──────────────┘     │  created_at  │    │  code        │
                     └──────────────┘    │  type        │
                                         │  value       │
┌───────────────┐    ┌──────────────┐    │  min_amount  │
│ knowledge_base│    │  promotions  │    │  valid_from  │
│  id           │    │  id          │    │  valid_to    │
│  title        │    │  name        │    │  used_count  │
│  content      │    │  type        │    └──────────────┘
│  category     │    │  rules       │
│  embedding_id │    │  start_time  │
│  tags         │    │  end_time    │
│  status       │    │  status      │
└───────────────┘    └──────────────┘
```

---

## 二、核心表结构

### 2.1 用户体系

```sql
-- 用户主表
CREATE TABLE users (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    username    VARCHAR(50)  NOT NULL UNIQUE,
    password    VARCHAR(255) NOT NULL,         -- bcrypt 哈希
    phone       VARCHAR(20)  UNIQUE,
    email       VARCHAR(100) UNIQUE,
    avatar      VARCHAR(500),
    status      TINYINT DEFAULT 1,             -- 1:正常 0:禁用
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 角色表
CREATE TABLE roles (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(30) NOT NULL UNIQUE,   -- admin / customer_service / consumer
    code        VARCHAR(30) NOT NULL UNIQUE,
    description VARCHAR(200)
);

-- 用户角色关联
CREATE TABLE user_roles (
    user_id BIGINT NOT NULL,
    role_id INT    NOT NULL,
    PRIMARY KEY (user_id, role_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (role_id) REFERENCES roles(id)
);

-- 用户画像表（融合项目八优势）
CREATE TABLE user_profiles (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id         BIGINT UNIQUE NOT NULL,
    gender          TINYINT,                   -- 0:未知 1:男 2:女
    age_range       VARCHAR(20),               -- 18-24 / 25-34 / ...
    preferences     JSON,                      -- 偏好标签 {"品牌":["Apple"],"品类":["手机"]}
    price_sensitive DECIMAL(3,2),              -- 价格敏感度 0-1
    rfm_r           INT DEFAULT 0,             -- Recency 最近购买天数(越小越近)
    rfm_f           INT DEFAULT 0,             -- Frequency 购买次数
    rfm_m           DECIMAL(10,2) DEFAULT 0,   -- Monetary 累计消费金额
    rfm_score       VARCHAR(5),                -- RFM分层: 重要价值/重要发展/重要保持/一般价值
    tags            JSON,                      -- 动态标签
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 2.2 商品体系（融合升级：项目八 SPU/SKU + 项目一分类树）

```sql
-- 分类表（树形结构）
CREATE TABLE categories (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(50) NOT NULL,
    parent_id   INT DEFAULT NULL,
    level       TINYINT DEFAULT 1,             -- 1:一级 2:二级 3:三级
    sort_order  INT DEFAULT 0,
    icon        VARCHAR(500),
    status      TINYINT DEFAULT 1,
    FOREIGN KEY (parent_id) REFERENCES categories(id)
);

-- 商品主表 (SPU)
CREATE TABLE products (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    category_id     INT NOT NULL,
    name            VARCHAR(200) NOT NULL,
    sub_title       VARCHAR(200),
    description     TEXT,
    brand           VARCHAR(100),
    main_image      VARCHAR(500),
    images          JSON,                      -- ["url1","url2"]
    detail_html     TEXT,                      -- 商品详情富文本
    status          TINYINT DEFAULT 1,         -- 1:上架 0:下架
    is_hot          TINYINT DEFAULT 0,
    is_new          TINYINT DEFAULT 0,
    sort_order      INT DEFAULT 0,
    embedding_id    VARCHAR(100),              -- ChromaDB 向量 ID
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- SKU 表
CREATE TABLE product_skus (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_id  BIGINT NOT NULL,
    sku_code    VARCHAR(50) UNIQUE NOT NULL,
    specs       JSON NOT NULL,                 -- {"颜色":"黑色","内存":"256GB"}
    price       DECIMAL(10,2) NOT NULL,        -- 售价（元，全项目金额统一用元）
    cost_price  DECIMAL(10,2),                 -- 成本价（元，仅内部，API 不返回）
    stock       INT DEFAULT 0,
    sold_count  INT DEFAULT 0,
    status      TINYINT DEFAULT 1,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- 商品属性模板（可选）
CREATE TABLE product_attributes (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    product_id  BIGINT NOT NULL,
    name        VARCHAR(50),                   -- e.g. "屏幕尺寸"
    value       VARCHAR(200),                  -- e.g. "6.7英寸"
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

### 2.3 订单体系

```sql
CREATE TABLE orders (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_no        VARCHAR(32) UNIQUE NOT NULL,
    user_id         BIGINT NOT NULL,
    total_amount    DECIMAL(10,2) NOT NULL,
    discount_amount DECIMAL(10,2) DEFAULT 0,
    pay_amount      DECIMAL(10,2) NOT NULL,
    status          TINYINT DEFAULT 1,         -- 1:待支付 2:已支付 3:已发货 4:已完成 5:已取消 6:退款中 7:已退款
    payment_method  VARCHAR(20),               -- alipay / wechat / card
    payment_time    DATETIME,
    shipping_name   VARCHAR(50),
    shipping_phone  VARCHAR(20),
    shipping_address VARCHAR(500),
    logistics_no    VARCHAR(50),
    logistics_co    VARCHAR(50),
    remark          VARCHAR(500),
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE order_items (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id    BIGINT NOT NULL,
    sku_id      BIGINT NOT NULL,
    product_name VARCHAR(200),
    sku_specs   JSON,
    quantity    INT NOT NULL,
    price       DECIMAL(10,2) NOT NULL,
    FOREIGN KEY (order_id) REFERENCES orders(id),
    FOREIGN KEY (sku_id)   REFERENCES product_skus(id)
);
```

### 2.4 工单体系

```sql
CREATE TABLE tickets (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    ticket_no   VARCHAR(32) UNIQUE NOT NULL,
    user_id     BIGINT NOT NULL,
    order_id    BIGINT,
    type        TINYINT NOT NULL,              -- 1:咨询 2:退货 3:换货 4:维修 5:投诉 6:其他
    title       VARCHAR(200) NOT NULL,
    description TEXT,
    status      TINYINT DEFAULT 1,             -- 1:待处理 2:处理中 3:已解决 4:已关闭
    priority    TINYINT DEFAULT 2,             -- 1:紧急 2:普通 3:低
    assignee_id BIGINT,                        -- 分配的客服 ID
    satisfaction TINYINT,                      -- 1-5 星
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id)     REFERENCES users(id),
    FOREIGN KEY (order_id)    REFERENCES orders(id),
    FOREIGN KEY (assignee_id) REFERENCES users(id)
);

CREATE TABLE ticket_comments (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    ticket_id   BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    content     TEXT NOT NULL,
    attachments JSON,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ticket_id) REFERENCES tickets(id),
    FOREIGN KEY (user_id)   REFERENCES users(id)
);
```

### 2.5 用户行为分析

```sql
CREATE TABLE user_behaviors (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id     BIGINT NOT NULL,
    action      VARCHAR(30) NOT NULL,          -- view / search / add_cart / buy / chat
    target_type VARCHAR(30),                   -- product / category / coupon
    target_id   BIGINT,
    context     JSON,                          -- {"keyword":"手机","source":"recommend"}
    ip          VARCHAR(50),
    user_agent  VARCHAR(500),
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_time (user_id, created_at),
    INDEX idx_action_time (action, created_at),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 2.6 AI 相关

```sql
-- 知识库（客服 RAG 数据源）
CREATE TABLE knowledge_base (
    id           BIGINT PRIMARY KEY AUTO_INCREMENT,
    title        VARCHAR(200) NOT NULL,
    content      TEXT NOT NULL,
    category     VARCHAR(50),                  -- product / policy / faq / manual
    product_id   BIGINT,                       -- 关联商品
    chunk_index  INT DEFAULT 0,                -- 分块序号
    embedding_id VARCHAR(100),                 -- ChromaDB ID
    tags         JSON,
    status       TINYINT DEFAULT 1,
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- 对话历史
CREATE TABLE chat_history (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id     BIGINT NOT NULL,
    session_id  VARCHAR(64) NOT NULL,
    role        VARCHAR(20) NOT NULL,           -- user / assistant / agent
    content     TEXT NOT NULL,
    intent      VARCHAR(30),                    -- 识别的意图
    agent       VARCHAR(30),                    -- 处理Agent: customer_service / recommendation / order
    metadata    JSON,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_session (session_id, created_at),
    FOREIGN KEY (user_id) REFERENCES users(id)
);
```

### 2.7 营销活动

```sql
CREATE TABLE coupons (...);  -- 同前

CREATE TABLE promotions (...);  -- 同前

CREATE TABLE promotion_products (...);  -- 同前
```

### 2.8 AI 增强（新增表）

```sql
-- 话术风格配置
CREATE TABLE style_configs (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(50) NOT NULL,            -- professional / warm / expert
    tone        VARCHAR(20),                      -- 语气
    greeting    VARCHAR(200),                     -- 开头语模板
    features    JSON,                             -- 话术特征
    examples    JSON,                             -- 示例对话
    scene_map   JSON,                             -- 场景映射
    role_map    JSON,                             -- 角色映射
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 场景策略
CREATE TABLE scene_strategies (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(50) NOT NULL,            -- pre_sale / post_sale / complaint
    triggers    JSON NOT NULL,                   -- 触发条件
    actions     JSON,                            -- 执行动作
    auto_send   TINYINT DEFAULT 0,               -- 是否自动发送
    template    TEXT,                             -- 自动回复模板
    notify_targets JSON,                         -- 通知目标 {platform: [ids]}
    status      TINYINT DEFAULT 1
);

-- 话术修正记录（采纳学习）
CREATE TABLE script_corrections (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    agent       VARCHAR(30),                     -- 哪个Agent
    session_id  VARCHAR(64),
    original    TEXT NOT NULL,                   -- AI原文
    corrected   TEXT NOT NULL,                   -- 客服修正后
    intent      VARCHAR(30),
    scene       VARCHAR(50),
    user_id     BIGINT,                          -- 修正的客服
    merged      TINYINT DEFAULT 0,               -- 是否已融入知识库
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 素材图库
CREATE TABLE material_images (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    product_id  BIGINT,
    type        VARCHAR(30) NOT NULL,            -- size_chart / fabric / detail / manual
    url         VARCHAR(500) NOT NULL,
    label       VARCHAR(100),
    tags        JSON,
    embedding_id VARCHAR(100),                   -- ChromaDB 多模态向量ID
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id)
);
```

---

## 三、索引策略

| 表 | 索引 | 类型 | 原因 |
|---|------|------|------|
| products | category_id + status | 复合 | 按分类查上架商品 |
| products | embedding_id | 唯一 | ChromaDB 关联 |
| product_skus | product_id | 普通 | 商品 SKU 列表 |
| orders | user_id + status | 复合 | 用户订单列表 |
| orders | order_no | 唯一 | 订单号查询 |
| chat_history | session_id + created_at | 复合 | 会话时间线 |
| user_behaviors | user_id + created_at | 复合 | 用户行为时间线 |
| tickets | user_id + status | 复合 | 用户工单 |
| knowledge_base | product_id + status | 复合 | 商品知识 |

---

## 四、Redis 缓存设计

| Key | 类型 | TTL | 说明 |
|-----|------|:--:|------|
| `cart:{user_id}` | Hash | 7d | 购物车 {sku_id: quantity} |
| `session:{user_id}` | Hash | 30m | Agent 上下文 |
| `hot_products` | ZSet | 1h | 热门排行 |
| `product:{id}` | String | 1h | 商品详情缓存 |
| `user_profile:{id}` | Hash | 1h | 用户画像缓存 |
| `rate_limit:{ip}` | String | 1m | 限流计数器 |
| `lock:order:{order_no}` | String | 10s | 订单防重 |
