# 多平台智能托管 SaaS 平台 — V2 重构设计文档

> 2026-06-25 | 基于当前代码库架构全面审计
> 知识库设计参考 D:\project_test 机械工厂知识库项目的已验证架构模式（非代码迁移，按电商 SaaS 场景重新设计）

---

## 一、现状分析与系统边界

### 1.1 当前系统拓扑

```
┌─────────────────────────────────────────────────────────────────┐
│                    vMall 虚拟电商平台 (:8020)                      │
│                                                                   │
│  consumer前端 (:8090)  ←买家购物                                │
│  admin前端 (:8091)     ←平台运营管理                             │
│  ❌ 商户端 (缺失)       ←商户自管理、绑定SaaS                     │
│                                                                   │
│  后端: FastAPI :8020  MySQL(vmall_db)  Redis                     │
│  模型: Buyer/Product/Order/AfterSale/Conversation/Logistics/     │
│        Wallet/WalletTx/PlatformSetting/PlatformAdmin              │
└─────────────────────────────────────────────────────────────────┘
                              │
                    OpenAPI + Webhook
                              │
┌─────────────────────────────────────────────────────────────────┐
│                  SaaS 多平台智能托管 (:8000)                       │
│                                                                   │
│  admin前端 (:8092)  ←管理平台 + 客服工作台(混在一起)              │
│  ❌ 缺少独立的客服工作台界面                                      │
│  ❌ 缺少企业知识库                                                │
│                                                                   │
│  后端: FastAPI :8000  MySQL(demo_test)  Redis  ChromaDB          │
│  模型: Merchant/MerchantUser/PlatformShop/ExternalProduct/       │
│        ExternalOrder/Conversation/Ticket/SkillGroup/...           │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 核心问题

| # | 问题 | 影响 |
|---|------|------|
| 1 | vMall 缺少商户端，商户无法自助管理店铺 | 绑定SaaS只能由管理员手动操作 |
| 2 | SaaS 管理平台和客服工作台混在一个前端 | 角色权限混乱，客服不应看到管理功能 |
| 3 | 商户绑定后无知识库学习能力 | AI托管只能基于模板，无法理解店铺知识 |
| 4 | 缺少企业知识库系统 | 客服无法查询店铺产品/政策知识 |

### 1.3 目标架构

```
┌────────────────────────────────────────────────────────────────────┐
│                     vMall 虚拟电商平台 (3前端)                       │
│                                                                     │
│  :8090 消费者端    :8091 管理员端    :8093 商户端 (NEW)             │
│  买家浏览/下单      平台运营管理      商品/订单管理                   │
│                                      店铺信息设置                    │
│                                      → 绑定SaaS托管 ←               │
└──────────────────────────────────────┬──────────────────────────────┘
                                       │ OpenAPI 绑定
                                       ▼
┌────────────────────────────────────────────────────────────────────┐
│                   SaaS 多平台智能托管 (2前端)                        │
│                                                                     │
│  :8092 托管管理平台          :8094 客服工作台 (NEW 独立)            │
│  店铺/商品/订单/工单管理      会话列表/聊天/AI话术                   │
│  技能组/SLA/推荐/AI配置      企业知识库问答                         │
│  企业知识库管理              智能体模式切换                         │
│  企业知识库问答              物流查询/商品推荐                      │
└────────────────────────────────────────────────────────────────────┘
```

---

## 二、vMall 商户端设计 (NEW :8093)

### 2.1 路由规划

| 路由 | 视图 | 说明 |
|------|------|------|
| `/login` | `Login.vue` | 商户登录 |
| `/` → `/dashboard` | `Dashboard.vue` | 经营概况（今日订单/收入/访客） |
| `/products` | `Products.vue` | 商品管理（CRUD、上下架） |
| `/products/add` | `ProductForm.vue` | 新增/编辑商品 |
| `/orders` | `Orders.vue` | 订单列表（筛选、发货、退款） |
| `/orders/:id` | `OrderDetail.vue` | 订单详情 + 物流 |
| `/service` | `Service.vue` | 客服消息（回复买家） |
| `/settings` | `Settings.vue` | 店铺设置（名称、Logo、简介） |
| `/binding` | `Binding.vue` | **SaaS 托管绑定**（核心新增） |

### 2.2 后端新增 API

```
POST   /api/v1/merchant/auth/login        # 商户登录
POST   /api/v1/merchant/auth/register     # 商户注册
GET    /api/v1/merchant/dashboard          # 经营概况
GET    /api/v1/merchant/products           # 商品列表（含分页/筛选）
POST   /api/v1/merchant/products           # 新增商品
PUT    /api/v1/merchant/products/{id}      # 编辑商品
PUT    /api/v1/merchant/products/{id}/status  # 上下架
DELETE /api/v1/merchant/products/{id}      # 删除商品
GET    /api/v1/merchant/orders             # 订单列表
GET    /api/v1/merchant/orders/{id}        # 订单详情
POST   /api/v1/merchant/orders/{id}/ship   # 发货
POST   /api/v1/merchant/orders/{id}/refund # 退款
GET    /api/v1/merchant/conversations      # 客服会话列表
GET    /api/v1/merchant/conversations/{id}/messages  # 会话消息
POST   /api/v1/merchant/conversations/{id}/messages  # 回复消息
GET    /api/v1/merchant/settings           # 店铺设置
PUT    /api/v1/merchant/settings           # 更新店铺设置
POST   /api/v1/merchant/binding/apply      # 申请绑定 SaaS（核心）
GET    /api/v1/merchant/binding/status     # 查询绑定状态
DELETE /api/v1/merchant/binding            # 解绑
```

### 2.3 新增数据模型

```python
# vmall_system/backend/app/models/vm_merchant.py
class VmMerchant(Base):
    __tablename__ = "vm_merchants"
    id              # 商户ID
    username        # 登录用户名
    password_hash   # bcrypt
    shop_name       # 店铺名称
    shop_logo       # 店铺Logo URL
    shop_desc       # 店铺简介
    contact_name    # 联系人
    contact_phone   # 联系电话
    contact_email   # 联系邮箱
    saas_bound      # 是否已绑定SaaS (bool)
    saas_shop_id    # 在SaaS中的shop_id (绑定后回填)
    saas_bind_time  # 绑定时间
    status          # 1=正常 0=禁用
    created_at / updated_at
```

### 2.4 商户端技术栈

```
frontend_merchant/
  package.json     # vue3 + vite + element-plus + pinia + vue-router + axios
  vite.config.js   # port: 8093, proxy /api → :8020
  src/
    main.js        # 复用现有模式（全局errorHandler + ElementPlus图标）
    router/index.js
    stores/merchant.js  # Pinia auth store
    api/index.js        # Axios + 拦截器
    api/request.js
    views/
      Login.vue, Dashboard.vue, Products.vue, ProductForm.vue,
      Orders.vue, OrderDetail.vue, Service.vue,
      Settings.vue, Binding.vue
```

---

## 三、SaaS 前端拆分

### 3.1 当前状态

`:8092` 单一前端混杂两类功能：
- **管理功能**: 工作台、店铺管理、商品库、订单中心、工单管理、技能组、分类、推荐、AI配置
- **客服功能**: 客服工作台（会话列表 + 聊天窗口 + AI话术面板）

### 3.2 拆分方案

**方案 A（推荐）**: 同一个入口 + 角色路由隔离
- 保留 `:8092` 入口
- router guard 根据 `role` 跳转不同 Layout：
  - `admin/manager` → `AdminLayout.vue`（管理侧边栏）
  - `service` → `ServiceLayout.vue`（最小化导航，直接客服工作台）
- 最小改动，无需新增端口/进程

**方案 B**: 两个独立前端
- `:8092` 管理平台
- `:8094` 客服工作台（新建独立 Vite 项目）
- 彻底隔离，但多一个进程

**推荐方案 A**，理由：
- 代码复用（API模块、auth store、ElementPlus配置）
- 部署简单（单进程）
- 客服角色登录后直接进入工作台，不暴露管理菜单
- 后续如需拆分为独立部署，Layout组件已是独立的

### 3.3 方案A实现细节

```
router/index.js:
  / → 判断 role:
    admin/manager → /admin/dashboard
    service       → /service/dashboard (客服工作台)

  /admin/dashboard   → AdminLayout → 管理功能
  /admin/shops       → AdminLayout
  ...

  /service/dashboard → ServiceLayout → 客服工作台（直接全屏工作台）
  /service/kb        → ServiceLayout → 知识库问答

  /login → Login（公开）
```

`ServiceLayout.vue` 设计：
- 顶部栏：工作台标题 + 模式切换 + 用户信息 + 退出
- 主体：全屏客服工作台（左栏会话列表 + 中栏聊天 + 右栏AI/KB面板）
- 无管理侧边栏

---

## 四、商户绑定 SaaS 流程

### 4.1 完整时序

```
商户端(:8093)              vMall API(:8020)           SaaS API(:8000)
     │                          │                         │
     │  POST /binding/apply     │                         │
     │  {saas_url, shop_info}   │                         │
     │─────────────────────────►│                         │
     │                          │  POST {saas_url}/openapi/v1/shops/register
     │                          │  {platform: "vmall",    │
     │                          │   shop_name,            │
     │                          │   shop_desc,            │
     │                          │   webhook_url,          │
     │                          │   access_token}         │
     │                          │────────────────────────►│
     │                          │                         │ 创建 PlatformShop
     │                          │                         │ 创建 Merchant(如需要)
     │                          │                         │ 触发全量同步
     │                          │       {shop_id, status} │
     │                          │◄────────────────────────│
     │                          │                         │
     │  {bound: true, shop_id}  │                         │
     │◄─────────────────────────│                         │
     │                          │                         │
     │                          │  ← Webhook: SHOP_BOUND  │
     │                          │     (后续事件通知)       │
```

### 4.2 SaaS 新增 OpenAPI

```
POST /openapi/v1/shops/register     # 商户自助注册（无需SaaS管理员手动操作）
  请求: { platform, shop_name, shop_desc, webhook_url, access_token }
  响应: { shop_id, status, sync_job_id }
  鉴权: 商户JWT（由vMall签发，SaaS验证签名）

GET  /openapi/v1/shops/{id}/sync-status  # 查询同步进度
DELETE /openapi/v1/shops/{id}            # 商户主动解绑
```

### 4.3 vMall 侧变更

- `VmPlatformSetting` 新增字段: `saas_register_url`
- 商户绑定页输入 SaaS 地址后，vMall 后端调用 SaaS OpenAPI
- 绑定成功后 `VmMerchant.saas_bound = True`

---

## 五、企业知识库设计（核心新增）

### 5.1 设计理念

企业知识库的设计遵循以下核心设计模式（源自机械工厂知识库项目的架构验证，按电商 SaaS 场景重新设计）：

**管道式处理（Pipeline Pattern）**：文档从入库到可检索，经过解析→分块→向量化→存储四个阶段，每个阶段有明确的状态流转，任意阶段失败可独立重试。

**分层检索（Layered Retrieval）**：检索不是一步完成的。稠密向量检索作为基线，BM25 稀疏检索作为互补信号，RRF 融合两者。在此之上叠加查询优化（Rewrite/HyDE）、重排序（Rerank）、纠错（CRAG）、后处理（压缩/重排）四个可选增强层，每层可独立开关。

**租户隔离前置（Tenant-First Filtering）**：所有检索操作在执行向量搜索前，先计算当前商户的可见文档 ID 集合，通过 Chroma 的 `where` 过滤条件在数据库层面隔离，而非检索后再过滤。

**流式生成与可观测（Streaming + Observability）**：问答采用 SSE 逐 token 输出，每次问答记录来源引用、置信度、响应耗时，支持反馈闭环。

### 5.2 与现有 SaaS AI 管道的关系

企业知识库 RAG 管道是现有 `ai_suggest.py` 客服话术管道的**独立互补模块**，而非替代：

| 维度 | 客服话术管道 (现有) | 企业知识库 (新增) |
|------|-------------------|-------------------|
| 知识来源 | ChromaDB 商品向量 + 回复模板向量 | 结构化商品知识 + 店铺信息 + 政策文档 |
| 检索目标 | 匹配买家问题→推荐客服回复话术 | 匹配用户问题→检索事实性知识片段 |
| 输出形式 | 3条建议话术 + 置信度（同步返回） | SSE流式回答 + 来源引用 + 置信度 |
| 使用场景 | 客服工作台右侧 AI 建议面板 | 客服工作台知识库 Tab / 管理后台知识库问答 |
| Collection | `merchant_{id}` | `kb_merchant_{id}`（独立 collection，互不干扰） |

### 5.3 知识来源与入库策略

电商场景的知识来源分为三层，入库优先级不同：

**L1 — 自动同步（绑定即入库，无需人工）**

| 来源 | doc_type | 内容结构化方式 | 更新触发 |
|------|----------|---------------|---------|
| 平台商品 | `product` | title + description + category_path + 每个SKU规格拼接为一段结构化文本 | 商品新增/编辑/下架 Webhook |
| 店铺信息 | `shop_info` | 店铺名称 + 简介 + 经营范围 + 联系方式 | 商户修改店铺设置 |
| 售后政策 | `policy` | 从 vMall 平台配置中提取退货/退款/保修规则 | 平台设置变更 |

**L2 — 半自动同步（延迟处理，异步后台）**

| 来源 | doc_type | 处理方式 | 触发时机 |
|------|----------|---------|---------|
| 优质客服回复 | `conversation` | 筛选 buyer 问题 + service 回复对，提取为 FAQ 格式 | 每日定时任务，限制最近200条，只取人工确认采纳的回复 |

**L3 — 手动上传（管理后台操作）**

| 来源 | doc_type | 格式支持 | 处理方式 |
|------|----------|---------|---------|
| 产品手册 | `manual` | PDF / Word / Markdown / TXT | 用户上传→后台异步处理 |
| 自定义FAQ | `faq` | 纯文本（管理后台表单录入） | 直接入库 |

### 5.4 数据模型

```sql
-- 知识文档（逻辑知识单元，一个产品 = 一个 document）
CREATE TABLE kb_documents (
    id INT AUTO_INCREMENT PRIMARY KEY,
    merchant_id INT NOT NULL,             -- 租户隔离（来自JWT）
    shop_id INT,                          -- 关联店铺，NULL=商户级
    title VARCHAR(200) NOT NULL,          -- 文档标题（产品名/文件名）
    doc_type ENUM('product','shop_info','policy','faq','manual','conversation') NOT NULL,
    source_type ENUM('auto_sync','manual_upload') NOT NULL DEFAULT 'auto_sync',
    source_ref VARCHAR(500),              -- 来源标识符 "product:{product_id}" 或文件路径
    content_text LONGTEXT,               -- 原始全文（入库前结构化文本）
    chunk_count INT DEFAULT 0,           -- 分块数量（向量化完成后回填）
    process_status ENUM('pending','parsing','vectorizing','done','failed') DEFAULT 'pending',
    process_error TEXT,                   -- 失败时的错误信息
    is_active TINYINT(1) DEFAULT 1,      -- 软删除标记
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW(),
    INDEX idx_merchant (merchant_id),
    INDEX idx_merchant_shop (merchant_id, shop_id),
    INDEX idx_merchant_type (merchant_id, doc_type),
    INDEX idx_merchant_status (merchant_id, process_status)
);

-- 知识分块（向量化后的最小检索单元）
CREATE TABLE kb_chunks (
    id INT AUTO_INCREMENT PRIMARY KEY,
    document_id INT NOT NULL,
    merchant_id INT NOT NULL,             -- 冗余加速过滤
    chunk_index INT NOT NULL,            -- 在文档内的序号（0-based）
    chunk_text TEXT NOT NULL,            -- 分块文本内容
    heading_context VARCHAR(200),         -- 标题注入前缀 "[产品名]"
    chroma_id VARCHAR(64),               -- ChromaDB 中对应向量的 ID
    token_count INT,                     -- token 计数（用于上下文窗口计算）
    meta_json JSON,                      -- {product_id, category_path, sku_spec, ...}
    created_at DATETIME DEFAULT NOW(),
    INDEX idx_document (document_id),
    INDEX idx_merchant (merchant_id),
    FOREIGN KEY (document_id) REFERENCES kb_documents(id) ON DELETE CASCADE
);

-- 知识库问答会话
CREATE TABLE kb_conversations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    merchant_id INT NOT NULL,
    user_id INT NOT NULL,                 -- merchant_user.id
    title VARCHAR(200),                   -- 首条问题截断
    created_at DATETIME DEFAULT NOW(),
    updated_at DATETIME DEFAULT NOW() ON UPDATE NOW(),
    INDEX idx_merchant_user (merchant_id, user_id)
);

-- 知识库问答消息
CREATE TABLE kb_messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    conversation_id INT NOT NULL,
    role ENUM('user','assistant') NOT NULL,
    question TEXT,                        -- role=user 时的问题
    answer TEXT,                          -- role=assistant 时的回答
    sources JSON,                         -- [{chunk_id, doc_title, score, snippet}]
    confidence ENUM('high','medium','low'),
    feedback TINYINT(1) DEFAULT 0,       -- 0=无, 1=有用, -1=无用
    response_time_ms INT,                 -- 端到端响应耗时
    created_at DATETIME DEFAULT NOW(),
    FOREIGN KEY (conversation_id) REFERENCES kb_conversations(id) ON DELETE CASCADE
);
```

### 5.5 核心 RAG 管道设计

#### 5.5.1 文档处理管道（Ingestion Pipeline）

设计原则：**状态机驱动 + 幂等覆盖 + 租户感知**

```
┌──────────────────────────────────────────────────────────────┐
│              kb_processor.process_document(doc_id)            │
│                                                               │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌─────────┐│
│  │ pending   │───►│ parsing  │───►│vectorizing│───►│  done   ││
│  └──────────┘    └──────────┘    └──────────┘    └─────────┘│
│       │               │               │               │      │
│       ▼               ▼               ▼               ▼      │
│   新建文档      提取结构化文本    调用embed API    写入Chroma │
│   (或reprocess)  LlamaIndex解析   批量25条/组     写入MySQL  │
│                 (仅手动上传文件)                           │      │
│                                                               │
│  任意阶段异常 → process_status = 'failed' + process_error    │
│  re-process 时：先 delete Chroma where doc_id → 再 upsert    │
└──────────────────────────────────────────────────────────────┘
```

**关键技术决策**：

1. **产品结构化文本生成**：vMall 商品数据格式为 `{title, description, category_path, skus_json: [{spec, price, stock, sku_code}]}`。入库前不经过 LlamaIndex 解析，而是直接用模板拼接为结构化文本：
   ```
   [华为 Mate70 Pro]
   分类: 数码/手机
   简介: 麒麟芯片，超光变影像
   规格与价格:
     - 曜石黑 / ¥6999 / 库存15 / SKU-...
     - 冰霜银 / ¥7499 / 库存10 / SKU-...
   ```
   这样每个产品生成 1 个 document，按 SKU 数量分 2-3 个 chunk。

2. **分块策略（TokenTextSplitter）**：使用精确 token 计数而非字符数估算。chunk_size=384 tokens（约中文400-500字），overlap=48 tokens。每个 chunk 注入标题前缀 `[{产品名}]`（Heading Context 模式），让 chunk 在向量空间中保留来源归属信息。

3. **批量向量化**：复用 SaaS 已有的 `embedding.py`（DashScope text-embedding-v4，1024维，批量25条/组）。不新建 embed 客户端。

4. **幂等重处理**：re-process 时先 `collection.delete(where={"document_id": doc_id})` 清 Chroma 旧向量，再 `delete from kb_chunks where document_id=?` 清 MySQL 旧记录，最后 upsert 新数据。

#### 5.5.2 检索管道（Retrieval Pipeline）

设计原则：**分层可插拔 + 商户隔离前置 + 降级保障**

```
┌─────────────────────────────────────────────────────────────────┐
│                     retrieve(merchant_id, question, top_k)       │
│                                                                  │
│  Step 0: 商户过滤                                                │
│    SELECT id FROM kb_documents                                  │
│    WHERE merchant_id=? AND process_status='done' AND is_active=1│
│    → allowed_ids: [1,2,5,8,12,...]                              │
│                                                                  │
│  Step 1: 双路召回（并行）                                        │
│    ┌── 稠密路 (Chroma) ──┐   ┌── 稀疏路 (BM25) ──┐             │
│    │ collection.query(   │   │ bm25.search(       │             │
│    │  query_embeddings,  │   │  question,         │             │
│    │  where={doc_id $in  │   │  allowed_ids,      │             │
│    │   allowed_ids},     │   │  top_k)            │             │
│    │  n_results=top_k*2) │   │                    │             │
│    └─────────┬───────────┘   └─────────┬──────────┘             │
│              │                         │                        │
│              └──────┬──────────────────┘                        │
│                     ▼                                           │
│  Step 2: RRF 融合 (k=60)                                        │
│    rrf_fusion(dense, sparse, k=60, top_n=top_k)                 │
│                                                                  │
│  Step 3: 重排序 (DashScope gte-rerank-v2, 可选)                  │
│    将融合结果用原始问题重排序，取 top_n                          │
│    rerank 失败 → 自动降级为按 RRF 得分取 top_n                  │
│                                                                  │
│  Step 4: CRAG 纠错检索 (可选)                                     │
│    LLM评估前5个chunk相关性 → 大部分无关则HyDE重检 →              │
│    不足3个则Step-Back补充                                        │
│                                                                  │
│  Step 5: 后处理（压缩→重排）                                     │
│    压缩: 裁掉 chunk 中与问题无关的句子                            │
│    重排: 最相关首尾、次相关中间 (Lost-in-the-Middle 缓解)       │
│                                                                  │
│  返回: [{id, content, metadata, distance}]                      │
└─────────────────────────────────────────────────────────────────┘
```

**各层开关（通过 settings 控制，默认关闭高级功能以保证稳定性）**：

| 开关 | 默认值 | 说明 |
|------|--------|------|
| `KB_USE_HYBRID` | `True` | 混合检索（稠密+BM25） |
| `KB_USE_RERANK` | `False` | DashScope 重排序 |
| `KB_USE_CRAG` | `False` | 纠错式检索 |
| `KB_USE_QUERY_REWRITE` | `True` | Prompt Rewrite 查询改写 |
| `KB_USE_HYDE` | `False` | HyDE 假设文档嵌入 |
| `KB_USE_REORDER` | `True` | 长上下文重排 |
| `KB_USE_COMPRESS` | `False` | 句子级上下文压缩 |

#### 5.5.3 问答生成管道（QA Pipeline）

```
┌─────────────────────────────────────────────────────────────────┐
│                   kb_ask(merchant_id, user_id, question)        │
│                                                                  │
│  1. 查询优化 (query_optimizer)                                   │
│     ├── 原始问题（始终保留）                                     │
│     ├── Prompt Rewrite: LLM 将口语化问题改写为检索友好形式       │
│     │   触发条件: 问题<15字 或 含"怎么/为什么/这个/那个"等词     │
│     └── HyDE: LLM 生成假设答案，用假设答案做向量检索             │
│         触发条件: 问题<15字 且 KB_USE_HYDE=True                  │
│                                                                  │
│  2. 去重检索                                                     │
│     每个优化查询各自检索 → 按 chunk_id 去重合并                  │
│                                                                  │
│  3. 构建 Prompt                                                  │
│     system: "你是{店铺名}的智能客服知识助手。严格基于以下        │
│             参考信息回答买家问题..."                             │
│     context: "[来源:{产品名} {分类}] chunk内容..." (拼接top_n)   │
│     history: 最近3轮对话（从 kb_messages 读取）                  │
│                                                                  │
│  4. SSE 流式输出                                                 │
│     event: data {"type":"token","content":"华"}                  │
│     event: data {"type":"token","content":"为"}                  │
│     ...                                                          │
│     event: data {"type":"done","confidence":"high",              │
│                  "sources":[...], "message_id":42}               │
│                                                                  │
│  5. 异步保存                                                     │
│     回答完成后独立 DB 会话写入 kb_messages                       │
│     (避免 StreamingResponse 阻塞在 DB I/O)                       │
└─────────────────────────────────────────────────────────────────┘
```

**电商客服场景 System Prompt 设计**：

```
你是{shop_name}的智能客服知识助手。
请严格基于以下参考信息回答用户问题。

规则：
1. 只基于参考信息回答，不要编造价格、规格、库存、政策。
2. 如果参考信息中没有答案，回答"知识库中暂无相关信息，
   建议联系店铺客服确认"。
3. 涉及具体商品参数（价格、配置、颜色），给出精确数据。
4. 涉及售后政策（退换货、保修），引用具体规则原文。
5. 语气亲切专业，使用买家能理解的表述。
6. 如果用户问题指向明确的产品，优先使用该产品的信息。

参考信息：
{context}
```

**置信度计算**：

```
基于 Chroma cosine 距离（0~2，越小越相似）：
  best_distance < 0.4  → "high"
  0.4 ≤ best < 0.7     → "medium"
  best ≥ 0.7           → "low"
  无检索结果            → "low"
```

### 5.6 多租户隔离方案

| 隔离层 | 方案 | 关键实现 |
|--------|------|---------|
| ChromaDB | 每个商户独立 collection `kb_merchant_{id}` | `get_kb_collection(merchant_id)` 按需创建 |
| BM25 索引 | `bm25_indexes: dict[int, BM25Searcher]` | 首次使用时构建，同步更新时重建 |
| MySQL | 所有查询 `WHERE merchant_id = ?` | service 层统一注入 `merchant_id` |
| 向量化 | 共享 embedding 服务，chroma_id 包含 `m{merchant_id}_` 前缀 | 向量无租户信息，隔离靠 collection |

### 5.7 自动同步编排

商户绑定 SaaS 后，`kb_sync_service.py` 编排以下流程：

```
Phase 1 — 产品目录同步（同步、BlockingBackgroundTasks）
  ├── 调用 V3Connector.get_products(shop_id)
  ├── 每个产品生成结构化文本
  ├── 为每个产品创建 kb_document (type='product', source='auto_sync')
  ├── 批量调用 process_document() → 分块 + 向量化
  └── 预计耗时: 50产品 × (2-3 chunks/产品) ≈ 5-8秒

Phase 2 — 店铺信息同步（同步）
  ├── 提取 shop_name, shop_desc, 经营类目
  ├── 创建 kb_document (type='shop_info')
  └── process_document()

Phase 3 — 历史会话学习（延迟，独立 asyncio task）
  ├── 延迟 30 秒（等待同步完成）
  ├── 拉取最近 200 条已回复会话
  ├── 提取 buyer_question + service_reply 对
  ├── LLM 将回复归纳为 FAQ 格式
  └── 创建 kb_document (type='conversation')

Phase 4 — 持续增量（事件驱动）
  ├── Webhook PRODUCT_CREATED → 单产品 process
  ├── Webhook PRODUCT_UPDATED → re-process 该产品
  ├── Webhook PRODUCT_DELETED → is_active=0
  └── 每日凌晨：增量会话学习（前24小时内优质回复）
```

### 5.8 API 设计

```
POST   /api/v1/kb/ask
  功能: 知识库问答（SSE流式）
  请求: { question: str, conversation_id?: int, top_k?: int }
  响应: text/event-stream
    data: {"type":"token","content":"..."}
    data: {"type":"done","confidence":"high","sources":[...],"message_id":42,"conversation_id":5}
  鉴权: 所有已登录角色

POST   /api/v1/kb/documents
  功能: 上传文档（手动）
  请求: multipart/form-data { file, title?, doc_type? }
  响应: { code:200, data: { document_id, status: 'pending' } }
  鉴权: admin/manager

GET    /api/v1/kb/documents
  功能: 文档列表
  请求: ?page=1&page_size=20&doc_type=&shop_id=&status=
  响应: { code:200, data: { items:[...], total, page, page_size } }

GET    /api/v1/kb/documents/{id}
  功能: 文档详情
  响应: { code:200, data: { ...document, chunks_preview: [...] } }

DELETE /api/v1/kb/documents/{id}
  功能: 删除文档（软删除 + Chroma delete）
  鉴权: admin/manager

POST   /api/v1/kb/documents/{id}/reprocess
  功能: 重新处理文档
  鉴权: admin/manager

GET    /api/v1/kb/conversations
  功能: 问答历史列表
  请求: ?page=1&page_size=20

GET    /api/v1/kb/conversations/{id}
  功能: 问答详情（含消息列表）

POST   /api/v1/kb/messages/{id}/feedback
  功能: 提交反馈
  请求: { feedback: 1 | -1 }

GET    /api/v1/kb/stats
  功能: 知识库统计
  响应: { total_docs, total_chunks, total_qa, avg_confidence, docs_by_type }

POST   /api/v1/kb/sync/{shop_id}
  功能: 手动触发全量同步
  鉴权: admin/manager
```

### 5.9 前端组件设计

#### 客服工作台 — 知识库问答面板

在现有客服工作台右侧面板新增 "知识库" Tab：

```
客服工作台 (ServiceLayout.vue)
┌──────────┬─────────────────┬──────────────────┐
│ 会话列表  │    聊天窗口      │  AI话术 | 知识库  │
│          │                 │                  │
│ ● 买家A  │  买家: 这个手机  │  [Tab: AI话术]   │
│   买家B   │  支持5G吗？     │  [Tab: 📚知识库]  │
│   买家C   │                 │                  │
│          │  客服:  是的     │  Q: 这款手机支持  │
│          │  Mate70 Pro支持  │  5G吗？          │
│          │  5G全网通       │                  │
│          │                 │  A: (streaming)   │
│          │                 │  Mate70 Pro支持   │
│          │                 │  5G全网通...      │
│          │                 │                  │
│          │                 │  来源: 商品详情页  │
│          │                 │  置信度: 95%      │
│          │  [输入框] [发送] │                  │
└──────────┴─────────────────┴──────────────────┘
```

#### 管理后台 — 知识库管理

新增路由 `/admin/knowledge`:

```
知识库管理页面
┌─────────────────────────────────────────────┐
│  [统计卡片] 文档总数 | 向量总数 | 问答次数    │
├─────────────────────────────────────────────┤
│  [标签页] 文档管理 | 知识库问答 | 同步管理    │
│                                             │
│  文档管理 Tab:                               │
│  ┌─────────────────────────────────────┐    │
│  │ [上传文档] [筛选: 类型▼] [搜索]      │    │
│  ├─────────────────────────────────────┤    │
│  │ 文档名称      │ 类型   │ 状态 │ 操作  │    │
│  │ Mate70 Pro   │ 商品   │ ✓    │ 删除  │    │
│  │ 店铺简介     │ 店铺   │ ✓    │ 删除  │    │
│  │ 售后政策.pdf │ 手册   │ 处理中│ ...  │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  知识库问答 Tab:                             │
│  ┌─────────────────────────────────────┐    │
│  │  (类似客服工作台的KB问答界面)         │    │
│  │  Q&A Chat + sources                 │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  同步管理 Tab:                               │
│  ┌─────────────────────────────────────┐    │
│  │  店铺: [vMall官方旗舰店]             │    │
│  │  上次同步: 2026-06-25 10:30         │    │
│  │  [全量同步] [增量同步]               │    │
│  └─────────────────────────────────────┘    │
└─────────────────────────────────────────────┘
```

---

## 六、技术实现要点

### 6.1 后端新增模块架构

所有知识库代码放在 `backend/app/kb/` 下，与现有 `services/`、`api/v1/` 解耦：

```
backend/app/
  kb/                                # 知识库子系统（独立于现有 services/）
    __init__.py
    processor.py                     # 文档处理总控（状态机 + 分派）
    splitter.py                      # TokenTextSplitter + 标题注入
    retriever.py                     # 分层检索入口（商户过滤 + 稠密/混合/多路）
    bm25_index.py                    # BM25 稀疏索引（per-merchant + jieba）
    fusion.py                        # RRF / 加权融合
    rewriter.py                      # 查询改写（Prompt Rewrite / HyDE / Step-Back）
    optimizer.py                     # 查询优化总入口（fast/auto/comprehensive）
    crag.py                          # CRAG 纠错（相关性评估 + 补充检索）
    reranker.py                      # DashScope gte-rerank-v2 封装
    postproc.py                      # 后处理管线（压缩 + 重排）
    prompt.py                        # System prompt + context 拼接 + 置信度

  models/
    kb_document.py                   # KbDocument ORM
    kb_chunk.py                      # KbChunk ORM
    kb_conversation.py               # KbConversation ORM
    kb_message.py                    # KbMessage ORM

  api/v1/
    kb.py                            # 知识库路由（/api/v1/kb/*）
    openapi_shops.py                 # OpenAPI 商户自助注册

  services/
    kb_sync_service.py               # 自动同步编排（绑定后 + 持续增量）
```

### 6.2 各模块设计要点

#### processor.py — 文档处理总控

```
设计模式: 参考工厂知识库的状态机处理流程
输入: document_id
输出: 状态流转 (pending→parsing→vectorizing→done|failed)

核心流程:
  1. 读取 kb_document，校验 doc_type 和 source_type
  2. 按 doc_type 分派提取策略:
     - product:   结构化模板拼接（不经过 LlamaIndex）
     - shop_info: 结构化模板拼接
     - policy:   结构化模板拼接
     - manual:    LlamaIndex SimpleDirectoryReader 解析文件
     - faq:       直接使用 content_text（用户在表单中录入的结构化文本）
     - conversation: LLM 将 QA 对归纳为 FAQ 格式
  3. 调用 splitter.create_splitter() 分块
  4. 调用 splitter.inject_heading() 注入标题前缀
  5. 调用 embedding.embed_texts() 批量向量化（复用现有 embedding.py）
  6. 获取 per-merchant Chroma collection: kb_merchant_{id}
  7. 幂等覆盖: collection.delete(where={"document_id": doc_id}) → collection.upsert(...)
  8. 写入 kb_chunks 表
  9. 更新 kb_document.process_status = 'done', chunk_count = N
```

#### splitter.py — 分块策略

```
设计模式: 参考 TokenTextSplitter + heading context 注入模式

create_splitter(chunk_size=384, chunk_overlap=48):
  - 使用 tiktoken cl100k_base 编码器（与 DashScope text-embedding-v4 兼容）
  - 主分隔符: " "（英文空格）
  - 后备分隔符: ["\n", "。", "！", "？", "；"]（中文句子边界）
  - 返回 LlamaIndex TokenTextSplitter 实例

inject_heading(chunks, document_title):
  - 给每个 chunk 文本前添加 "[{产品名/文档标题}]\n"
  - 例如 "[华为 Mate70 Pro]\n分类: 数码/手机\n..."
  - 作用: chunk 在向量空间中保留来源文档的语义信号
  - 这样问"Mate70价格"时，向量更容易命中该产品的 chunk
```

#### retriever.py — 分层检索

```
设计模式: 参考多阶段检索管线（可见ID过滤→双路召回→融合→rerank→CRAG→后处理）

商户过滤 (第一步，在所有检索之前):
  def get_allowed_ids(merchant_id):
    return db.query(KbDocument.id).filter(
      KbDocument.merchant_id == merchant_id,
      KbDocument.process_status == 'done',
      KbDocument.is_active == True
    ).all()
  → Chroma query 时传入 where={"document_id": {"$in": allowed_ids}}

稠密检索 (_dense_search):
  - 复用 embedding.embed_query()（已有函数）
  - collection.query(query_embeddings=[vec], n_results=top_k*2, where={...})

混合检索 (retrieve_hybrid):
  - 稠密路 + BM25 路 并行执行
  - RRF 融合: k=60, top_n=top_k
  - BM25 索引未就绪 → 自动降级为纯稠密

检索主入口 retrieve(merchant_id, question, top_k):
  - Step 0: 计算 allowed_ids → 空则返回 []
  - Step 1: 双路召回 → RRF 融合
  - Step 2: 可选 rerank → 失败降级取 top_n
  - Step 3: 可选 CRAG → 质量校验/补充检索
  - Step 4: 后处理（压缩+重排）
```

#### bm25_index.py — 稀疏检索

```
设计模式: 参考 per-merchant BM25 索引字典模式

数据结构:
  bm25_indexes: dict[int, BM25Searcher]
    key: merchant_id
    value: 该商户的 BM25 检索器实例

构建逻辑:
  def build_index(merchant_id):
    1. SELECT chunk_text FROM kb_chunks WHERE merchant_id=? AND document active
    2. jieba 分词（中文）+ 空格分词（英文数字混合）
    3. rank_bm25.BM25Okapi 构建
    4. bm25_indexes[merchant_id] = BM25Searcher(index, chunks)

检索:
  def search(merchant_id, question, allowed_ids, top_k):
    if merchant_id not in bm25_indexes:
      build_index(merchant_id)
    分词 question → BM25 打分 → 过滤 allowed_ids → 返回 top_k
```

#### optimizer.py — 查询优化

```
设计模式: 参考 escalating complexity 模式（fast→auto→comprehensive）

optimize_query(question, mode="auto") → list[str]:
  - 始终保留原始问题在第一位
  - fast: 短问题/口语词触发 Prompt Rewrite，追加一条改写查询
  - auto: 短问题加 HyDE（假设答案→用假设答案做向量检索）
  - comprehensive: 再加 Step-Back（上位概念查询）+ 子问题分解

触发规则:
  - Prompt Rewrite: 问题<15字 或 含"怎么/为什么/这个/啥"等
  - HyDE: 问题<15字（短问题缺乏检索信号）
  - Step-Back: 仅 comprehensive 模式

去重: 改写结果可能与原始问题或彼此相同，返回前 dedup
```

#### crag.py — 纠错式检索

```
设计模式: 参考 评估→判决→行动 三段式 CRAG

流程:
  1. 评估: LLM 对 Top-5 chunk 逐一判定"相关/无关"（只传前200字给LLM）
  2. 判决:
     - 60%+ 无关 → 检索劣化 → 用 HyDE 重新检索补充
     - 相关不足3个 → 信号不足 → 用 Step-Back 扩展查询补充
     - 否则 → 质量良好，直接返回
  3. 行动: 执行补充检索 → 返回修正后的 chunk 列表

降级: 评估失败的 chunk 保守保留（宁可多给不可漏掉）
```

#### prompt.py — Prompt 构建

```
设计模式: 参考 上下文拼接 + 对话历史 + 置信度计算 的模板化模式

build_messages(question, chunks, shop_info, history):
  - 构建 system prompt（注入店铺名 + 参考信息）
  - context: "[来源:{doc_title} {category}]\n{chunk_text}" 逐个拼接
  - history: 从 kb_messages 取最近3轮（6条消息）
  - 返回 messages list 可直接喂给 LLM

build_references(chunks):
  - 去重合并相同文档的 chunk
  - 返回 [{doc_title, doc_type, chunk_index, snippet}]

calc_confidence(distances):
  - best_distance < 0.4 → "high"
  - 0.4 ≤ best < 0.7 → "medium"
  - best ≥ 0.7 → "low"
```

### 6.3 复用现有基础设施

知识库子系统不重复造轮子，直接依赖 SaaS 已有的以下组件：

| 现有组件 | 位置 | 知识库使用方式 |
|---------|------|-------------|
| `embed_query()` / `embed_texts()` | `app/services/embedding.py` | 分块向量化 + 查询向量化 |
| `stream_chat()` / `chat()` | `app/services/llm.py` | SSE 流式回答 + CRAG 评估 |
| `get_or_create_collection()` | `app/services/chroma_client.py` | 扩展：按 merchant_id 创建命名 collection |
| `get_current_merchant()` | `app/core/deps.py` (需确认) | 从 JWT 提取 merchant_id，注入请求上下文 |
| `ok()` / `page()` | `app/core/response.py` | API 统一响应格式 |

### 6.4 多租户改造（对现有 ChromaDB 客户端的扩展）

现有 `chroma_client.py` 管理 `merchant_{id}` 单一 collection（用于话术管道）。知识库需要第二个 collection `kb_merchant_{id}`：

```python
# 扩展后
def get_kb_collection(merchant_id: int):
    """获取知识库向量 collection（每个商户独立）"""
    return _client.get_or_create_collection(
        name=f"kb_merchant_{merchant_id}",
        metadata={"hnsw:space": "cosine"},
    )
```

两个 collection 互不干扰：话术管道继续使用 `merchant_{id}`，知识库使用 `kb_merchant_{id}`。

### 6.5 新增依赖

```txt
# requirements.txt 新增

# 文档解析（仅 manual 类型文档需要）
llama-index-core>=0.10.0
llama-index-readers-file>=0.1.0
docx2txt>=0.8
openpyxl>=3.1.0
python-pptx>=0.6.21

# 中文分词 + BM25 稀疏检索
rank-bm25>=0.2.2
jieba>=0.42.1

# 精确 token 计数（TokenTextSplitter）
tiktoken>=0.5.0

# DashScope rerank（已有 embedding 和 llm，此项新增）
# dashscope SDK 已安装，gte-rerank-v2 通过现有 SDK 调用
```

### 6.6 SSE 流式问答客户端

客服工作台和管理后台都需要 SSE 流式输出，设计一个通用的 `useKBStream` composable：

```javascript
// frontend/src/api/stream.js
// 核心: 基于 fetch + ReadableStream 的 SSE 消费（非 WebSocket）
// 参考模式: D:\project_test 的 EventSource 模式，改用 fetch 以支持 POST + Authorization header

export async function streamKBAsk({ question, conversationId, topK }, token, callbacks) {
  const response = await fetch('/api/v1/kb/ask', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({ question, conversation_id: conversationId, top_k: topK }),
  })

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop()  // 未完成的行保留到下次

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = JSON.parse(line.slice(6))
        if (data.type === 'token') {
          callbacks.onToken(data.content)
        } else if (data.type === 'done') {
          callbacks.onDone({
            confidence: data.confidence,
            sources: data.sources,
            messageId: data.message_id,
            conversationId: data.conversation_id,
          })
        } else if (data.type === 'error') {
          callbacks.onError(data.message)
        }
      }
    }
  }
}
```

此客户端在客服工作台的知识库 Tab 和管理后台的知识库问答 Tab 中复用。

---

## 七、实施计划（6阶段，预估 9 天）

### 阶段 1: 系统边界整理（0.5天）

| 任务 | 详细内容 | 产出物 |
|------|---------|--------|
| 1.1 SaaS 前端角色路由拆分 | 新建 `AdminLayout.vue`、`ServiceLayout.vue`，router guard 按 role 分流 | 两个 Layout 组件，路由重构 |
| 1.2 vMall 商户模型 + seed | `vm_merchants` 表，seed 插入测试商户 | model + migration + seed |
| 1.3 vMall 商户端脚手架 | `frontend_merchant/` Vite 项目搭建 | 项目目录 + 基础配置 |

### 阶段 2: vMall 商户端（2天）

| 任务 | 详细内容 | 产出物 |
|------|---------|--------|
| 2.1 商户认证 API + 后端路由框架 | `merchant/auth.py` 登录/注册 + JWT 签发 | 3 个 auth 端点 |
| 2.2 商品管理 | `POST/PUT/DELETE /merchant/products`，绑定前管理自有商品 | 5 个 product 端点 |
| 2.3 订单管理 + 客服消息 | 订单列表/详情/发货/退款 + 会话回复 | 6 个端点 |
| 2.4 店铺设置 + SaaS 绑定 | settings CRUD + `POST /merchant/binding/apply` | 绑定流程打通 |
| 2.5 商户端前端页面 | Login/Dashboard/Products/Orders/Service/Settings/Binding | 9 个 Vue 页面 |

### 阶段 3: SaaS OpenAPI 商户注册（0.5天）

| 任务 | 详细内容 | 产出物 |
|------|---------|--------|
| 3.1 `POST /openapi/v1/shops/register` | 接收 vMall 转发请求，创建 PlatformShop + 初始化 KB 同步 | OpenAPI 端点 |
| 3.2 同步任务编排 | 绑定后自动触发 Phase 1+2 同步（产品+店铺信息） | `kb_sync_service.py` |

### 阶段 4: 知识库核心引擎（3天）

| 任务 | 详细内容 | 产出物 |
|------|---------|--------|
| 4.1 数据模型建表 | 4 张 KB 表 + SQLAlchemy ORM | `kb/models/*.py` |
| 4.2 splitter + processor | TokenTextSplitter + heading 注入 + 状态机 + 产品结构化模板 | `kb/splitter.py` + `kb/processor.py` |
| 4.3 retriever + fusion | 商户过滤→稠密/BM25→RRF→rank→后处理 全管线 | `kb/retriever.py` + `kb/bm25_index.py` + `kb/fusion.py` |
| 4.4 optimizer + crag + prompt | 查询优化 + 纠错 + LLM prompt 构建 | `kb/optimizer.py` + `kb/crag.py` + `kb/prompt.py` |
| 4.5 API 路由 + SSE 流式问答 | `POST /kb/ask` SSE 端点 + 文档 CRUD + 统计 | `api/v1/kb.py`（10+ 端点） |
| 4.6 自动同步编排 | 绑定触发→全量→会话学习→持续增量 | `kb_sync_service.py` 完整实现 |

### 阶段 5: 前端实现（1.5天）

| 任务 | 详细内容 | 产出物 |
|------|---------|--------|
| 5.1 SSE 流式客户端 | `stream.js` — fetch + ReadableStream | 通用 composable |
| 5.2 管理后台知识库页 | 文档列表/上传/管理 + 问答聊天界面 + 同步管理 | `AdminKnowledge.vue` |
| 5.3 客服工作台 KB Tab | ServiceLayout 右侧面板新增知识库 Tab | 集成到 `ServiceLayout.vue` |
| 5.4 Sass 前端角色路由 | admin → AdminLayout / service → ServiceLayout | `router/index.js` 改造 |

### 阶段 6: 集成测试（1.5天）

| 任务 | 详细内容 |
|------|---------|
| 6.1 端到端流程 | 商户注册→绑定 SaaS→自动同步→KB 问答→反馈闭环 |
| 6.2 多租户隔离验证 | 商户 A 的 KB 数据对商户 B 不可见 |
| 6.3 降级验证 | 关闭 rerank/crag/hyde 等开关，确保基础检索正常 |
| 6.4 性能验证 | 50 产品同步耗时 < 10s，KB 检索 < 500ms，SSE 首 token < 2s |
| 6.5 现有功能回归 | 120+ API 端点全量回归 |

**总预估: 9 天**

---

## 八、端口与访问地址规划

| 地址 | 系统 | 角色 | 登录凭据 |
|------|------|------|---------|
| `http://127.0.0.1:8090` | vMall 消费者端 | 买家 | buyer_test / 123456 |
| `http://127.0.0.1:8091` | vMall 管理员端 | 平台运营 | admin_vmall / 123456 |
| `http://127.0.0.1:8093` | **vMall 商户端 (NEW)** | 商户 | merchant01 / 123456 |
| `http://127.0.0.1:8092` | SaaS 管理平台 | 管理员/经理 | admin / 123456 |
| `http://127.0.0.1:8092` | SaaS 客服工作台 | 客服 | service / 123456 |

> 注：SaaS 管理平台和客服工作台共用 :8092 入口，通过角色路由自动分流到不同 Layout。

---

## 九、风险与依赖

| 风险 | 等级 | 缓解措施 |
|------|------|---------|
| DashScope API Key 未配置 | 高 | 确认 `.env` 中 `DASHSCOPE_API_KEY` 有效；知识库与话术管道共用同一 Key |
| ChromaDB 多 collection 内存占用 | 低 | PersistentClient 磁盘模式，collection 按需加载；50 商户以内无压力 |
| BM25 索引首次构建耗时长 | 低 | 异步后台构建，构建期间自动降级为纯稠密检索 |
| 产品结构化文本质量影响检索精度 | 中 | 模板覆盖 title/desc/category/specs 全部字段，保证信息密度 |
| 会话历史量大时自动同步慢 | 低 | 限制首次同步 200 条；增量同步仅处理 24 小时内回复 |
| LlamaIndex 版本兼容（仅 manual 上传用到） | 低 | 锁定 0.10.x 版本；不影响 auto_sync 路径（产品走模板拼接） |

---

## 十、验收标准

1. vMall 商户可独立登录 :8093，管理商品（CRUD+上下架）、订单（查看+发货+退款）、客服消息（回复买家）、店铺设置
2. 商户在绑定页面输入 SaaS 地址后一键绑定，SaaS 自动创建 PlatformShop 记录
3. 绑定后自动触发产品目录同步：50个产品 → kb_documents → kb_chunks → ChromaDB，全程 10 秒内完成
4. SaaS :8092 按角色自动分流：admin/manager 看到管理侧边栏 + 完整菜单，service 直接进入客服工作台
5. 客服工作台右侧面板"知识库"Tab：输入问题 → SSE 流式输出回答 → 显示商品来源和置信度
6. 管理后台 `/admin/knowledge`：文档 Tab（列表+上传+删除）+ 问答 Tab（聊天界面）+ 同步 Tab（触发全量/查看状态）
7. KB 问答 SSE 每个 token 逐字渲染，"done"事件附带 sources 数组（含 doc_title、chunk_index、置信度）
8. 商户 A 的 `kb_merchant_1` collection 数据对商户 B 的 `kb_merchant_2` 完全隔离（ChromaDB + MySQL 双重隔离）
9. 关闭 KB_USE_RERANK 等开关后，基础稠密检索依然正常工作（降级保障）
10. 所有现有 120+ API 端点回归通过
