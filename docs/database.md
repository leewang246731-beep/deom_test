# 数据库设计 · 多平台智能托管 SaaS 平台

---

## 一、ER 图（核心表）

```
┌──────────────┐       ┌──────────────────┐
│  merchants   │       │  merchant_users  │
│  id          │──┐    │  id              │
│  name        │  │    │  merchant_id (FK)│
│  status      │  ├───<│  username        │
│  created_at  │  │    │  password_hash   │
└──────────────┘  │    │  role (admin/    │
                  │    │   manager/service)│
┌─────────────────┴──┐ └──────────────────┘
│  platform_shops    │
│  id                │       ┌──────────────────┐
│  merchant_id (FK)  │──┐    │  conversations   │
│  platform_type     │  │    │  id              │
│  shop_name         │  ├───<│  shop_id (FK)    │
│  app_key/secret    │  │    │  platform_conv_id│
│  access_token      │  │    │  buyer_nick      │
│  sync_status       │  │    │  messages_json   │
└───────┬────────────┘  │    │  ai_suggest      │
        │               │    │  handled         │
┌───────┴────────────┐  │    └──────────────────┘
│  categories        │  │
│  id                │  │    ┌──────────────────┐
│  merchant_id (FK)  │  │    │  external_orders │
│  name              │  │    │  id              │
│  parent_id         │  ├───<│  shop_id (FK)    │
└────────────────────┘  │    │  platform_order_id│
                         │    │  buyer_openid    │
┌────────────────────────┴──┐ │  total_amount    │
│  external_products        │ │  status          │
│  id                       │ │  sku_details_json│
│  shop_id (FK)             │ └──────────────────┘
│  platform_product_id      │
│  title                    │
│  price / stock            │
│  description              │
│  images_json              │
│  category_path            │
│  embedding_status         │
└───────────────────────────┘
```

---

## 二、核心表结构

### 2.1 商户与员工

```sql
-- 商户表（SaaS 租户）
CREATE TABLE merchants (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    name        VARCHAR(100) NOT NULL,
    contact     VARCHAR(50),
    status      TINYINT DEFAULT 1,             -- 1:正常 0:停用
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 商户员工表（替代原 consumer user 表）
CREATE TABLE merchant_users (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    merchant_id     BIGINT NOT NULL,
    username        VARCHAR(50) NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,     -- bcrypt
    display_name    VARCHAR(50),
    role            VARCHAR(20) NOT NULL,       -- admin / manager / service
    status          TINYINT DEFAULT 1,         -- 1:正常 0:禁用
    last_login_at   DATETIME,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_merchant_username (merchant_id, username),
    FOREIGN KEY (merchant_id) REFERENCES merchants(id)
);
```

### 2.2 平台店铺

```sql
CREATE TABLE platform_shops (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    merchant_id     BIGINT NOT NULL,
    platform_type   VARCHAR(20) NOT NULL,       -- taobao / jd / douyin / mock
    shop_name       VARCHAR(100) NOT NULL,
    shop_url        VARCHAR(500),
    app_key         VARCHAR(100),
    app_secret      VARCHAR(200),
    access_token    TEXT,
    refresh_token   TEXT,
    token_expire_at DATETIME,
    sync_status     VARCHAR(20) DEFAULT 'idle', -- idle / syncing / error
    last_sync_at    DATETIME,
    is_active       TINYINT DEFAULT 1,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id)
);
```

### 2.3 商品（从外部平台同步）

```sql
CREATE TABLE external_products (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
    shop_id             BIGINT NOT NULL,
    platform_product_id VARCHAR(100) NOT NULL,
    title               VARCHAR(300) NOT NULL,
    price               DECIMAL(10,2) NOT NULL,
    stock               INT DEFAULT 0,
    description         TEXT,
    images_json         JSON,                   -- ["url1","url2",...]
    category_path       VARCHAR(300),           -- "女装/连衣裙/韩版"
    embedding_status    VARCHAR(20) DEFAULT 'pending', -- pending / done / error
    embedding_id        VARCHAR(100),           -- ChromaDB 向量ID
    status              TINYINT DEFAULT 1,      -- 1:在售 0:下架
    last_sync_at        DATETIME,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_shop_product (shop_id, platform_product_id),
    FOREIGN KEY (shop_id) REFERENCES platform_shops(id)
);
```

### 2.4 订单

```sql
CREATE TABLE external_orders (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
    shop_id             BIGINT NOT NULL,
    platform_order_id   VARCHAR(100) NOT NULL,
    buyer_openid        VARCHAR(100) NOT NULL,
    buyer_nick          VARCHAR(100),
    total_amount        DECIMAL(10,2) NOT NULL,
    discount_amount     DECIMAL(10,2) DEFAULT 0,
    pay_amount          DECIMAL(10,2) NOT NULL,
    status              VARCHAR(20) NOT NULL,   -- pending / paid / shipped / completed / refunding / refunded
    sku_details_json    JSON,                   -- [{"title":"...","price":...,"qty":1}]
    receiver_name       VARCHAR(50),
    receiver_phone      VARCHAR(20),
    receiver_address    VARCHAR(500),
    pay_time            DATETIME,
    ship_time           DATETIME,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_shop_order (shop_id, platform_order_id),
    FOREIGN KEY (shop_id) REFERENCES platform_shops(id)
);
```

### 2.5 买家会话

```sql
CREATE TABLE conversations (
    id                      BIGINT PRIMARY KEY AUTO_INCREMENT,
    shop_id                 BIGINT NOT NULL,
    platform_conversation_id VARCHAR(100) NOT NULL,
    buyer_nick              VARCHAR(100) NOT NULL,
    messages_json           JSON NOT NULL,      -- [{"role":"buyer","content":"...","time":"..."}, ...]
    ai_suggest_reply        TEXT,               -- AI 推荐的最新话术
    last_message_at         DATETIME,
    handled_status          VARCHAR(20) DEFAULT 'pending', -- pending / replied / closed
    assigned_to             BIGINT,             -- 分配的客服 user_id
    created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (shop_id)     REFERENCES platform_shops(id),
    FOREIGN KEY (assigned_to) REFERENCES merchant_users(id)
);
```

### 2.6 分类（商户自定义）

```sql
CREATE TABLE categories (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    merchant_id BIGINT NOT NULL,
    name        VARCHAR(50) NOT NULL,
    parent_id   INT DEFAULT NULL,
    level       TINYINT DEFAULT 1,
    sort_order  INT DEFAULT 0,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id),
    FOREIGN KEY (parent_id) REFERENCES categories(id)
);
```

### 2.7 AI 话术配置

```sql
CREATE TABLE ai_style_configs (
    id          INT PRIMARY KEY AUTO_INCREMENT,
    merchant_id BIGINT NOT NULL,
    name        VARCHAR(50) NOT NULL,            -- professional / warm / expert
    tone        VARCHAR(20),
    greeting    VARCHAR(200),
    features    JSON,                             -- 话术特征
    is_default  TINYINT DEFAULT 0,
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id)
);

-- 话术采纳记录（用于优化 AI）
CREATE TABLE ai_suggestion_logs (
    id              BIGINT PRIMARY KEY AUTO_INCREMENT,
    conversation_id BIGINT NOT NULL,
    buyer_question  TEXT NOT NULL,
    ai_suggestion   TEXT NOT NULL,
    was_adopted     TINYINT DEFAULT 0,           -- 0:忽略 1:采纳 2:修改后发送
    final_message   TEXT,
    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 三、ChromaDB 设计

| 配置项 | 值 |
|--------|-----|
| Collection 命名 | `merchant_{merchant_id}` |
| 向量维度 | 1024 (BGE-M3) |
| 商品向量文本 | `title + description + category_path` |
| 话术向量文本 | `conversations.messages_json` 中客服回复内容 |
| 话术元数据 | `{"type": "reply", "product_id": ..., "question": "..."}` |
| 检索方式 | 商品搜索用纯向量相似度；话术建议用混合检索（向量 + buyer_question 文本匹配） |

---

## 四、索引策略

| 表 | 索引 | 原因 |
|----|------|------|
| merchant_users | merchant_id + username (UNIQUE) | 同商户用户名唯一 |
| platform_shops | merchant_id | 商户店铺列表 |
| external_products | shop_id + platform_product_id (UNIQUE) | 防重复同步 |
| external_products | shop_id + status | 按店铺查在售商品 |
| external_products | embedding_id | ChromaDB 关联 |
| external_orders | shop_id + platform_order_id (UNIQUE) | 防重复 |
| external_orders | shop_id + status | 按店铺+状态筛选 |
| conversations | shop_id + handled_status | 客服工作台待处理会话 |
| conversations | assigned_to | 客服已分配会话 |

---

## 五、Redis 缓存设计

| Key | 类型 | TTL | 说明 |
|-----|------|:--:|------|
| `m:{mid}:token:shop_{sid}` | String | 按过期时间 | 外部平台 access_token |
| `m:{mid}:lock:refund_{oid}` | String | 30s | 售后防并发锁 |
| `m:{mid}:session:{user_id}` | Hash | 30m | 客服登录会话 |
| `m:{mid}:sync:status:{sid}` | String | 5m | 店铺同步状态 |
