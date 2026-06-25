# SaaS 智能托管平台强化拓展实施计划

> 基准日期：2026-06-25 | 所有 8 个服务已验证通过，7 个已知 bug 已修复

---

## Phase 1: 缺陷修复与基础补完（P0 — 先修后拓）

### 1.1 Products.vue — 商品 CRUD 完整化
- **现状**: 只读列表 + 筛选 + 语义搜索，无创建/编辑/删除
- **改动**:
  - 新增 `ProductDialog.vue` 弹窗组件（创建/编辑共用），含 shop_id 选择、title、price、stock、description、category_path、images_json 字段
  - Products.vue 添加"新增商品"按钮，表格行添加"编辑"/"删除"操作列
  - 修复语义搜索 API 参数遗漏：`searchProducts(searchQ.value, filters.shop_id)` 补上第二个参数
- **涉及文件**: `src/api/index.js`（新增 createProduct/updateProduct/deleteProduct）、`src/views/Products.vue`、`src/views/ProductDialog.vue`（新建）
- **后端**: `products.py` 新增 POST/PUT/DELETE 端点
- **验证**: 商品列表可新增、编辑、删除，语义搜索传入正确的 shop_id 参数

### 1.2 Categories.vue — 分类编辑功能
- **现状**: 只能创建和删除，不能改名
- **改动**: 添加"编辑"按钮 → 弹出内联编辑框 → 调用 `updateCategory` API
- **涉及文件**: `src/views/Categories.vue`
- **验证**: 分类名可修改并持久化

### 1.3 AdminKnowledge.vue — 同步按钮修复
- **现状**: "同步店铺知识"按钮调用 `kbGetStats()`（查统计），而非 `kbSyncShop()`（实际同步）
- **改动**: 按钮改为调用 `kbSyncShop`，同步完成后刷新 stats
- **涉及文件**: `src/views/AdminKnowledge.vue`
- **验证**: 点击同步按钮后知识库文档数量增长

### 1.4 SkillGroups.vue — 加载状态补全
- **现状**: 无 loading spinner，慢网络时空白
- **改动**: 添加 `loading` ref + `v-loading` 指令；清理未使用的 `getShops` import
- **涉及文件**: `src/views/SkillGroups.vue`
- **验证**: 页面加载时显示 loading 动画，import 无死代码

---

## Phase 2: 核心功能补完（P0）

### 2.1 用户管理（全新模块）
- **现状**: 系统有 admin/manager/service 三级角色但无用户管理 UI，SkillGroups 从已有成员中 hack 用户列表
- **新增**:
  - `src/views/Users.vue` — 用户列表（表格：用户名、显示名、角色、状态、最后登录），分页
  - `src/views/UserDialog.vue` — 创建/编辑用户弹窗（username、display_name、password、role、status）
  - AdminLayout + MerchantLayout 侧边栏新增"用户管理"菜单项
  - 路由 `/admin/users` + `/merchant/users` 指向同一视图
- **后端**: `users.py`（GET/POST/PUT/DELETE）、`UserCreateRequest`/`UserUpdateRequest` schema
- **涉及文件**: 后端新增 `api/v1/users.py` + schema，前端新增 2 个 view，路由新增条目
- **验证**: 可查看、新增、编辑、禁用用户；用户列表作为人群选择器的数据源

### 2.2 SLA 策略管理 UI（全新模块）
- **现状**: `getSLAPolicies`/`createSLAPolicy`/`updateSLAPolicy`/`deleteSLAPolicy` 4 个 API 已实现，无前端
- **新增**:
  - `src/views/SLAPolicies.vue` — 策略表格（priority、分类、响应/解决/升级时限、状态），分页
  - `src/views/SLADialog.vue` — 创建/编辑弹窗，含 priority/category_id/response_minutes/resolve_minutes/escalate_minutes/escalate_to 字段
  - AdminLayout 侧边栏新增"SLA 管理"菜单项
  - 路由 `/admin/sla-policies`
- **后端**: SLA 定时检查后台任务（conversation timeout + ticket SLA 到期自动标记）
- **涉及文件**: `src/views/SLAPolicies.vue`（新建）、`src/views/SLADialog.vue`（新建）、路由 + Layout
- **验证**: 可创建/编辑/删除 SLA 策略；工单列表展示 SLA 倒计时；超时自动 breach 标记

### 2.3 AI 话术采纳日志查看器
- **现状**: `getAutoReplyLogs` API 存在但无前端，统计数据在 ServiceModeConfig.vue 中展示
- **新增**: `src/views/AutoReplyLogs.vue` — 日志表格（会话 ID、买家问题、AI 回复、置信度、动作、响应时间），筛选条件（日期范围、采纳状态、mode）
- **路由**: `/admin/auto-reply-logs`、`/merchant/auto-reply-logs`
- **验证**: 可查看按日期/采纳状态/模式筛选的日志，分页正常

---

## Phase 3: 智能化增强（P1）

### 3.1 服务知识库门户增强
- **现状**: ServiceKnowledge.vue 只能问答，看不到文档列表，无法浏览
- **改动**:
  - ServiceKnowledge.vue 改为双面板：左侧文档列表（可搜索/展开），右侧 Q&A 面板
  - 支持 service 用户上传文档（manual 类型）
  - AI 回复时附带引用的文档片段和置信度
- **涉及文件**: `src/views/ServiceKnowledge.vue`
- **验证**: 客服人员可浏览文档、上传新文档、看到引用来源

### 3.2 工单分类树独立管理
- **现状**: `getTicketCategories` API 存在但无前端
- **新增**: 在工单创建表单中嵌入分类树选择器；`src/views/TicketCategories.vue` 管理页（类 Categories.vue 结构）
- **路由**: `/admin/ticket-categories`
- **验证**: 创建工单时可选择分类；分类可增删改

### 3.3 AI 话术质量评分
- **现状**: `was_adopted` 只记录 0/1/2，无质量维度
- **新增**:
  - AISuggestionLog 添加 `quality_score` (1-5) 和 `feedback_note` 字段
  - Service.vue 采纳面板添加快速评分（星级）
  - AI 话术效果分析面板（按风格/按客服/按时段的采纳率趋势图）
- **涉及文件**: 后端 model/schema、前端 Service.vue、新增 Analysis.vue 组件
- **验证**: 客服可打分；Dashboard 展示采纳率趋势

### 3.4 智能推荐引擎扩容
- **现状**: 三路融合推荐（向量 + 共购 + 规则），但关联规则仅支持手动
- **改动**:
  - Recommendations.vue 添加"自动规则"tab — 基于共购矩阵 top-N 自动生成交叉销售规则
  - 推荐规则支持编辑（目前只有创建/删除）：添加生效/停用开关
  - 添加规则批量导入（CSV 上传 product_id + recommended_product_id + rule_type + priority）
- **涉及文件**: `src/views/Recommendations.vue`、后端 recommendations.py
- **验证**: 自动规则可生成、可查看、可启用/停用

---

## Phase 4: 运营工具（P1）

### 4.1 批量操作
- **现状**: 所有操作为逐条处理
- **新增**:
  - 工单列表添加多选 → 批量分配 / 批量关闭
  - 会话列表添加多选 → 批量关闭
  - 后端 `tickets.py` 新增 `POST /tickets/batch` 端点
- **验证**: 多选功能正常，批量操作返回成功/失败计数

### 4.2 Webhook 事件监控
- **现状**: Webhook 接受 7 种事件但无前端查看投递状态
- **新增**:
  - 新建 `webhook_delivery_logs` 表（payload、event_type、status、response_code、created_at）
  - `src/views/WebhookLogs.vue` — 事件列表（类型、来源店铺、状态、响应码、耗时）
  - 支持重试单个事件
- **验证**: 可查看 webhook 投递历史，失败事件可重试

### 4.3 操作审计日志
- **新增**: `audit_logs` 表（user_id、action、target_type、target_id、detail_json、ip、created_at）
- **前端**: `src/views/AuditLogs.vue` — 按用户/操作类型/时间筛选的日志列表
- **后端**: 中间件自动记录关键操作（login/logout 除外：create/update/delete/status change）
- **验证**: 可追溯谁在什么时候做了什么操作

---

## Phase 5: 数据分析（P2）

### 5.1 增强 Dashboard
- **新增指标卡片**: 今日会话数、平均响应时间（连接真实数据，当前写死为 0）、客服在线数
- **新增图表**: 客服工作量分布饼图、商品销量排行柱状图、会话来源渠道分布
- **日期选择器**: 支持自定义日期范围（当前固定 today/week/month）

### 5.2 数据导出
- **新增**: 订单/工单/会话/商品 列表页添加"导出 CSV"按钮
- **后端**: 复用现有列表 API，添加 `export=true` 参数返回 CSV stream
- **验证**: CSV 文件正常下载，编码为 UTF-8 BOM（Excel 兼容）

### 5.3 客服实时监控面板
- **新增**: `src/views/LiveMonitor.vue`（仅 admin）
  - 在线客服列表（WebSocket 心跳）
  - 当前活跃会话数 / 等待中会话数
  - 今日各客服处理量实时排行
- **后端**: WebSocket 消息推送 `agent_status` 事件
- **验证**: 面板实时刷新，客服上下线可感知

---

## Phase 6: 平台对接扩展（P2）

### 6.1 Taobao 连接器实现
- **现状**: `taobao.py` 全部 `raise NotImplementedError`
- **改动**: 基于淘宝开放平台 TOP API 实现 `fetch_products`、`fetch_orders`、`send_message`
- **需要**: 淘宝 AppKey/AppSecret 配置项，沙箱环境测试

### 6.2 JD 连接器
- **新增**: `jd.py` 实现京东开普勒 API 对接
- **注册到工厂函数**

### 6.3 商品同步任务调度
- **现状**: 同步为手动触发或 shop bind 时一次性
- **新增**: 定时任务（APScheduler）每 30 分钟自动同步已绑定店铺
- **前端**: 同步状态面板显示最近同步时间/结果

---

## 实施顺序建议

```
Week 1: Phase 1 全部 + Phase 2.1（用户管理）
Week 2: Phase 2.2-2.3（SLA UI + 采纳日志）+ Phase 3.1（知识库增强）
Week 3: Phase 3.2-3.4（工单分类 + AI 质量 + 推荐扩容）
Week 4: Phase 4 全部（批量操作 + Webhook + 审计）
Bonus:  Phase 5-6 按需启动
```

---

## 交付物总览

| 类别 | 新建文件 | 修改文件 |
|------|---------|---------|
| 后端 API | `users.py`、`audit.py` | `products.py`、`main.py`、`models/__init__.py` |
| 后端 Model | — | `ai_suggestion_log.py`、`models/__init__.py`、新增 audit/webhook_delivery 表 |
| 后端 Schema | — | `schemas/__init__.py` |
| 前端 View | `Users.vue`、`UserDialog.vue`、`SLAPolicies.vue`、`SLADialog.vue`、`AutoReplyLogs.vue`、`TicketCategories.vue`、`WebhookLogs.vue`、`AuditLogs.vue`、`LiveMonitor.vue` | `Products.vue`、`Categories.vue`、`AdminKnowledge.vue`、`SkillGroups.vue`、`ServiceKnowledge.vue`、`Recommendations.vue`、`Service.vue`、`Dashboard.vue`、`Tickets.vue` |
| 路由 | — | `index.js`、`merchant.js`、`service.js` |
| 布局 | — | `AdminLayout.vue`、`MerchantLayout.vue` |
| API 函数 | — | `api/index.js` |

共计：**新增 ~12 个文件**，**修改 ~18 个文件**
