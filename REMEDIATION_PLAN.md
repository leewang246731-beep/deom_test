# 修复实施计划 — 多平台智能托管 SaaS 平台 v2.0.0

> 基于 [TEST_REPORT.md](TEST_REPORT.md) 的 12 个失败/阻塞项和 6 项风险评估制定。

---

## 1. 修复计划概述

### 1.1 目标

在 4 个阶段内解决自测发现的所有致命和严重缺陷，使版本达到上线标准。

### 1.2 范围

| 类别 | 数量 | 策略 |
|------|:----:|------|
| 致命缺陷 | 2 | 立即修复 |
| 严重缺陷 | 3 | 第二阶段修复 |
| 一般缺陷 | 4 | 第三阶段修复 |
| 建议改进 | 3 | 第四阶段优化 |
| 阻塞项 | 4 | 2 项修复、2 项文档化 |
| 风险缓解 | 5 | 跨阶段持续改进 |

### 1.3 团队分工建议

| 角色 | 负责 | 预估总工时 |
|------|------|:----:|
| 后端开发 A | 致命缺陷修复 + 租户隔离 | 8h |
| 后端开发 B | Pydantic Schema 统一 + AI 依赖修复 | 10h |
| 全栈/DevOps | 向量重建 + 环境验证 | 4h |
| QA | 回归测试执行 | 6h |
| **合计** | | **28 人时 (~3.5 人日)** |

---

## 2. 分阶段修复任务列表

---

### 🔴 第一阶段：致命阻断修复 (预估 6h)

> **目标**: 解除阻塞，恢复平台运营功能和工单创建链路。
> **入口条件**: 无。
> **出口条件**: platform login 可正常获取 token，工单创建全参数不报 500。

---

#### 任务 1.1 — 修复平台运营登录路由未注册 (BUG-001)

| 属性 | 内容 |
|------|------|
| **缺陷 ID** | BUG-001 |
| **严重程度** | 🔴 致命 |
| **关联用例** | TC-AUTH-002 |
| **预估工时** | 1h |
| **涉及文件** | `backend/app/models/platform_user.py`, `backend/app/models/__init__.py`, `backend/main.py` |

**根因分析**:
`auth.py:56-76` 定义了 `platform_login` 函数，`models/__init__.py` 第 7 行导入了 `PlatformUser`。但 `platform_user.py` 是最近新增文件（git status 显示 `??`），服务器是在此文件创建前启动的。Python 模块在启动时解析，`from app.models.platform_user import PlatformUser` 如果当时文件不存在，auth 模块导入失败，但 FastAPI 会静默跳过失败的路由注册，导致 3 个正常路由注册了而 `/platform/login` 缺失。

**修复方案**:

1. 确认 `backend/app/models/platform_user.py` 文件存在且内容正确（已验证，文件存在且语法正确）
2. 确认 `backend/app/models/__init__.py` 第 7 行 `from app.models.platform_user import PlatformUser` 存在
3. **重启 FastAPI 服务器**

```bash
# 在 backend/ 目录下执行
# 先杀掉现有进程，再重启
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *uvicorn*" 2>/dev/null
cd backend && python main.py
```

4. 验证修复: 重启后调用 `GET /openapi.json` 确认 `/api/v1/auth/platform/login` 出现在路径列表中

**验证方法**:
```bash
# 检查路由是否注册
curl -s http://localhost:8012/openapi.json | python -c "import sys,json; paths=json.load(sys.stdin)['paths']; print('OK' if '/api/v1/auth/platform/login' in paths else 'FAIL')"

# 功能验证
curl -s -X POST http://localhost:8012/api/v1/auth/platform/login \
  -H "Content-Type: application/json" \
  -d '{"username":"super_admin","password":"123456"}'
# 预期: 200 + platform token + user info
```

**回归范围**: 全部平台专属功能（审计日志 `/audit-logs`、跨租户商店查看等）

**回退方案**: 如果重启后仍不出现，检查 `platform_user.py` 导入链是否有循环引用；临时方案：将 `platform_login` 函数合并到 `auth.py` 其他位置，绕过独立文件导入。

---

#### 任务 1.2 — 修复工单创建 500 错误 (BUG-002 + BUG-006)

| 属性 | 内容 |
|------|------|
| **缺陷 ID** | BUG-002, BUG-006 |
| **严重程度** | 🔴 致命 (BUG-002) + 🟡 一般 (BUG-006) |
| **关联用例** | TC-TICK-006, TC-TICK-007 |
| **预估工时** | 3h |
| **涉及文件** | `backend/app/schemas/__init__.py` (新增 Schema), `backend/app/api/v1/tickets.py` (重构) |

**根因分析**:

`tickets.py:89` 使用 `body: dict` 而非 Pydantic Schema，导致三重问题：
1. **无类型校验**: 任意 JSON 都被接受，无效值直达数据库
2. **无 OpenAPI 文档**: Swagger UI 看不到请求体结构
3. **外键违规 → 500**: `category_id=1` 在 `ticket_categories` 表中不存在（当前 merchant 无分类），但请求未校验，SQLAlchemy INSERT 触发 MySQL 外键约束失败，异常未被捕获（`try/except` 仅包裹 `_auto_assign`，line 109-112）

**修复方案**:

#### Step 1: 在 `backend/app/schemas/__init__.py` 末尾新增 TicketCreate Schema

```python
# ===== 工单 =====
class TicketCreate(BaseModel):
    title: str
    description: Optional[str] = ""
    priority: Optional[str] = "P3"
    source: Optional[str] = "manual"
    source_id: Optional[int] = None
    category_id: Optional[int] = None
    buyer_openid: Optional[str] = None
    ticket_tags: Optional[List[str]] = None
```

#### Step 2: 修改 `backend/app/api/v1/tickets.py` 第 88-114 行

将 `def create_ticket(body: dict, ...)` 替换为:

```python
@router.post("")
def create_ticket(
    body: TicketCreate,
    current: CurrentUser = Depends(get_current_merchant),
    db: Session = Depends(get_db),
):
    """创建工单。必填: title。可选: description, priority, category_id, source_id, buyer_openid。"""
    # --- 分类存在性校验（防止 FK 违规） ---
    if body.category_id is not None:
        cat = db.query(TicketCategory).filter(
            TicketCategory.id == body.category_id,
            TicketCategory.merchant_id == current.merchant_id,
        ).first()
        if not cat:
            raise HTTPException(
                status_code=400,
                detail={"code": 40001, "msg": f"工单分类不存在: {body.category_id}"},
            )

    ticket_no = _gen_ticket_no(db, current.merchant_id)
    t = Ticket(
        merchant_id=current.merchant_id,
        ticket_no=ticket_no,
        title=body.title,
        description=body.description or "",
        priority=body.priority or "P3",
        source=body.source or "manual",
        source_id=body.source_id,
        buyer_openid=body.buyer_openid,
        category_id=body.category_id,
        created_by=current.user_id,
        ticket_tags=body.ticket_tags,
    )
    db.add(t)
    db.flush()
    # 分配日志
    db.add(TicketAssignment(ticket_id=t.id, action="created", to_user_id=current.user_id))
    # 智能分配：分类存在时才执行
    if body.category_id is not None:
        try:
            _auto_assign(db, current.merchant_id, t)
        except Exception:
            pass
    db.commit()
    return ok({"id": t.id, "ticket_no": t.ticket_no}, msg="工单已创建")
```

**验证方法**:
```bash
# 1. 仅标题（应成功）
curl -s -X POST http://localhost:8012/api/v1/tickets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"测试工单"}'

# 2. 含不存在 category_id（应返回 400 而非 500）
curl -s -X POST http://localhost:8012/api/v1/tickets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"测试工单","category_id":99999}'
# 预期: 400 {"detail":{"code":40001,"msg":"工单分类不存在: 99999"}}

# 3. 缺少 title（应返回 422）
curl -s -X POST http://localhost:8012/api/v1/tickets \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
# 预期: 422 Field required

# 4. priority 非法值（应返回 422，Pydantic 自动枚举校验 — 如需严格校验可加 Literal["P0","P1","P2","P3"]）
```

**回归范围**: 全部工单 CRUD 接口、工单创建的所有参数组合、`_auto_assign` 函数

---

#### 任务 1.3 — 修复用户登录跨租户查询 (BUG-005)

| 属性 | 内容 |
|------|------|
| **缺陷 ID** | BUG-005 |
| **严重程度** | 🟠 严重 |
| **关联用例** | TC-AUTH-001 ~ TC-AUTH-004 |
| **预估工时** | 2h |
| **涉及文件** | `backend/app/api/v1/auth.py`, `backend/app/schemas/__init__.py` |

**根因分析**:

`auth.py:31`:
```python
user = db.query(MerchantUser).filter(MerchantUser.username == body.username).first()
```

多商户环境下，3 个商户各有 `admin`/`manager`/`service` 用户。此查询无 `merchant_id` 过滤，始终返回 DB 中第一条匹配记录（取决于主键顺序），导致商户 B 的 admin 可能登录到商户 A 的账号。

**修复方案**:

在 `LoginRequest` Schema 中添加可选的 `merchant_id` 字段，登录时需指定商户：

#### Step 1: 修改 `LoginRequest` (schemas/__init__.py 第 7-9 行)

```python
class LoginRequest(BaseModel):
    username: str
    password: str
    merchant_id: Optional[int] = None  # 新增：多商户登录指定租户
```

#### Step 2: 修改 `auth.py` login 函数 (第 29-53 行)

```python
@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    q = db.query(MerchantUser).filter(MerchantUser.username == body.username)
    if body.merchant_id is not None:
        q = q.filter(MerchantUser.merchant_id == body.merchant_id)
    user = q.first()

    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "用户名或密码错误"})
    if user.status != 1:
        raise HTTPException(status_code=403, detail={"code": 40301, "msg": "账号已禁用"})
    # ... 其余不变
```

> **设计决策**: 如果 `merchant_id` 未提供且存在多个同名用户，返回 400 提示 "该用户名在多个商户中存在，请指定 merchant_id"。避免静默选错。

增强版:

```python
@router.post("/login")
def login(body: LoginRequest, db: Session = Depends(get_db)):
    q = db.query(MerchantUser).filter(MerchantUser.username == body.username)
    if body.merchant_id is not None:
        q = q.filter(MerchantUser.merchant_id == body.merchant_id)

    users = q.all()
    if len(users) > 1 and body.merchant_id is None:
        # 多个同名用户，要求指定商户
        merchants = [{"merchant_id": u.merchant_id, "display_name": u.display_name} for u in users]
        raise HTTPException(
            status_code=400,
            detail={
                "code": 40002,
                "msg": "该用户名在多个商户中存在，请在登录时指定 merchant_id",
                "available_merchants": merchants,
            },
        )

    user = users[0] if users else None
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "用户名或密码错误"})
    # ... 其余不变
```

> **前端联动**: 需同步修改 `Login.vue`，在登录表单增加商户选择下拉框。如当前仅单商户，可暂时跳过前端修改，先修后端。

**验证方法**:
```bash
# 单商户场景（merchant_id=11 仅一个 admin）→ 应成功
curl -s -X POST http://localhost:8012/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456"}'

# 多商户场景（如果存在多个 admin）→ 应返回 40002 提示
# （当前种子数据为每商户创建独立用户，需额外造数据验证）

# 指定 merchant_id 登录
curl -s -X POST http://localhost:8012/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456","merchant_id":11}'
```

**回归范围**: 所有登录场景、前端 Login.vue、token refresh 流程

---

### 🟠 第二阶段：严重功能修复 (预估 8h)

> **目标**: 恢复 AI 核心功能，修复数据完整性问题。

---

#### 任务 2.1 — 重建商品向量索引 (BUG-003)

| 属性 | 内容 |
|------|------|
| **缺陷 ID** | BUG-003 |
| **严重程度** | 🟠 严重 |
| **关联用例** | TC-PROD-015, TC-AI-001 |
| **预估工时** | 2h |
| **涉及文件** | `backend/seed.py`, 无代码改动 |

**根因分析**:
所有 100 个商品 `embedding_status='pending'`，向量从未生成。语义搜索 (`GET /products/search`) 和 AI 建议回复依赖 ChromaDB 向量检索，无向量则返回空结果。

**修复方案**:
执行完整回填：

```bash
cd backend
python seed.py --backfill --full
```

这会：
1. 遍历所有 `embedding_status='pending'` 的商品
2. 调用 DashScope `text-embedding-v4` 生成 1024 维向量
3. 写入 ChromaDB `merchant_{id}` collection
4. 更新商品 `embedding_status` 为 `'done'`
5. 重建 BM25 索引
6. 重建协同过滤矩阵

**前置条件检查**:
```bash
# 验证 DashScope API key 可用
curl -s -X POST "https://dashscope.aliyuncs.com/api/v1/services/embeddings/text-embedding/text-embedding-v4" \
  -H "Authorization: Bearer sk-b67a88b0601941338abadced5c03474c" \
  -H "Content-Type: application/json" \
  -d '{"model":"text-embedding-v4","input":{"texts":["test"]}}' | python -c "import sys,json; d=json.load(sys.stdin); print('OK' if d.get('output') else 'FAIL: '+str(d))"
```

**验证方法**:
```bash
# 语义搜索应有结果
curl -s "http://localhost:8012/api/v1/products/search?q=手机" \
  -H "Authorization: Bearer $TOKEN" | python -c "import sys,json; d=json.load(sys.stdin); r=d['data']['results']; print(f'结果数: {len(r)}')"

# AI 建议应有有效数据
curl -s -X POST http://localhost:8012/api/v1/ai/suggest \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"shop_id":50,"buyer_question":"这个手机什么时候发货"}' | python -c "import sys,json; d=json.load(sys.stdin); print(f'suggestions: {len(d.get(\"data\",{}).get(\"suggestions\",[]))}')"
```

**回退方案**: 如果 DashScope API 不可用，切换为纯 BM25 关键词搜索（修改 `semantic_search_products` 函数，fallback 到 SQL LIKE 查询）。

---

#### 任务 2.2 — 修复 AI 催付话术空数据 (BUG-004)

| 属性 | 内容 |
|------|------|
| **缺陷 ID** | BUG-004 |
| **严重程度** | 🟠 严重 |
| **关联用例** | TC-ORD-009 |
| **预估工时** | 3h |
| **涉及文件** | `backend/app/services/ai_suggest.py`, `backend/app/api/v1/ai.py` |

**根因分析**:
`POST /orders/pending-payment/remind` 返回 200 但 data 为空。可能原因:
1. DashScope API key 无效或额度耗尽
2. LLM 调用超时未正确处理
3. 返回数据解析逻辑有 bug

**修复方案**:

#### Step 1: 增加明确的错误返回

找到 `backend/app/api/v1/ai.py` 中 campaign 端点，确保异常时返回具体错误信息而非空数据：

```python
@router.post("/campaign/pending-payment")
def campaign_pending_payment(body: AICampaignRequest, ...):
    try:
        result = generate_payment_reminder(body.shop_id, ...)
        if not result or not result.get("reminders"):
            return ok({"reminders": [], "msg": "当前无待催付订单或AI服务暂时不可用"})
        return ok(result)
    except Exception as e:
        # 不要静默吞掉错误
        logger.error(f"催付话术生成失败: {e}")
        return ok({"reminders": [], "msg": f"AI服务调用失败: {str(e)}"}, msg="部分成功")
```

#### Step 2: 添加 API key 健康检查

在 `backend/app/core/config.py` 或新增 `health` 端点中增加 DashScope 连通性检查。

**验证方法**:
```bash
curl -s -X POST http://localhost:8012/api/v1/ai/campaign/pending-payment \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"shop_id":50}'
# 预期: 200 + 明确的 msg 说明 AI 服务状态（成功返回话术，失败返回原因）
```

---

#### 任务 2.3 — 补全缺失的 TicketCreate Schema 及同类问题排查 (BUG-006 扩展)

| 属性 | 内容 |
|------|------|
| **缺陷 ID** | BUG-006 |
| **严重程度** | 🟠 严重 |
| **关联用例** | TC-TICK-007, 潜在其他端点 |
| **预估工时** | 3h |
| **涉及文件** | 全局排查 `body: dict` 使用点 |

**根因分析**:
`tickets.py:89` 使用 `body: dict` 绕过了 Pydantic 校验。需排查全项目是否还有其他端点使用 `body: dict`。

**修复方案**:

#### Step 1: 全局搜索

```bash
cd backend
grep -rn "body:\s*dict" app/api/
grep -rn "body:\s*dict" app/kb/
```

#### Step 2: 为每个 `body: dict` 端点创建对应 Schema

已知需要添加的 Schema（在 `schemas/__init__.py` 中）：
- `TicketCreate` — 已在任务 1.2 中处理
- `TicketStatusUpdate`: `{status: str}`
- `TicketAssign`: `{user_id: int}`
- `TicketCommentCreate`: `{content: str}`
- 其他根据 grep 结果补充

#### Step 3: 更新路由函数签名

将每个 `body: dict` 替换为对应的 Pydantic Schema 类型。

**验证方法**: 检查 OpenAPI 文档 (`/docs`) 中所有 POST/PUT 端点都有完整的 Request Body Schema。

---

### 🟡 第三阶段：一般缺陷优化 (预估 6h)

---

#### 任务 3.1 — 统一 API 响应格式 (BUG-010)

| 属性 | 内容 |
|------|------|
| **缺陷 ID** | BUG-010 |
| **严重程度** | 🔵 建议 |
| **预估工时** | 2h |
| **涉及文件** | `backend/app/api/v1/shops.py`, `backend/app/api/v1/orders.py` |

**现状**:

| 端点 | 当前格式 | 目标格式 |
|------|----------|----------|
| `GET /shops` | `list` | `{items, total, page, page_size}` |
| `GET /orders/pending-payment` | `list` | `{items, total, page, page_size}` |
| `GET /ai/styles` | `list` | `{items, total}` |
| 大部分 GET | `{items, total, page, page_size}` | 不变 |

**修复方案**:

将返回 list 的端点改为使用 `page()` helper：

```python
# shops.py line 56 — 改动前:
return ok(result)

# 改动后:
return page(result, len(result), 1, len(result))
```

**影响评估**: 前端需同步修改对应的数据访问路径（`data.items` vs `data`）。**需与前端协调**。

---

#### 任务 3.2 — 修复工单分类列表为空 (BUG-009)

| 属性 | 内容 |
|------|------|
| **缺陷 ID** | BUG-009 |
| **严重程度** | 🟡 一般 |
| **预估工时** | 1h |
| **涉及文件** | `backend/app/api/v1/tickets.py` 分类查询部分 |

**根因分析**:
`GET /tickets/categories` 返回 0 条数据。需确认：
1. 分类数据是否在 seed 中创建（seed.py 创建了 10 个分类，但可能未关联 `merchant_id`）
2. 查询是否错误地过滤了 `merchant_id`

**修复方案**:

检查 `TicketCategory` 模型是否有 `merchant_id` 字段，以及查询是否正确关联。如果分类是全局的（无 merchant_id），则查询不应加租户过滤。

```python
# 排查 tickets.py 中的分类查询
# 如果 TicketCategory 是全局共享的（merchant_id=NULL），需特殊处理
def list_categories(current, db):
    cats = db.query(TicketCategory).filter(
        (TicketCategory.merchant_id == current.merchant_id) | 
        (TicketCategory.merchant_id.is_(None))
    ).all()
    ...
```

**验证方法**:
```bash
curl -s http://localhost:8012/api/v1/tickets/categories \
  -H "Authorization: Bearer $TOKEN"
# 预期: 返回 >=10 个分类
```

---

#### 任务 3.3 — 修复 Dashboard metrics 字段为 null (BUG-012)

| 属性 | 内容 |
|------|------|
| **缺陷 ID** | BUG-012 |
| **严重程度** | 🔵 建议 |
| **预估工时** | 1h |
| **涉及文件** | `backend/app/api/v1/dashboard.py` |

**根因分析**:
`metrics` 端点返回的 `total_conversations` 为 `None`。阅读 `dashboard.py` 代码，该字段仅在 `shop_ids` 非空时计算。应改为默认返回 0 而非 None。

**修复方案**:
在 `dashboard.py` metrics 函数中确保所有数值字段有默认值 0：
```python
return ok({
    "total_orders": total_orders or 0,
    "today_orders": today_orders or 0,
    "pending_conversations": pending_convs or 0,
    "total_conversations": total_convs or 0,  # 添加此行
    # ...
})
```

---

#### 任务 3.4 — 店铺绑定重名检查 (BUG-011)

| 属性 | 内容 |
|------|------|
| **缺陷 ID** | BUG-011 |
| **严重程度** | 🔵 建议 |
| **预估工时** | 0.5h |
| **涉及文件** | `backend/app/api/v1/shops.py` |

**修复方案**:
在 `bind_shop` 函数中增加重名检查：
```python
@router.post("")
def bind_shop(body: ShopCreate, ...):
    # 重名检查
    exist = db.query(PlatformShop).filter(
        PlatformShop.merchant_id == current.merchant_id,
        PlatformShop.shop_name == body.shop_name,
        PlatformShop.is_active == 1,
    ).first()
    if exist:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "店铺名称已存在"})
    # ... 其余不变
```

---

### 🔵 第四阶段：建议改进 (预估 4h)

---

#### 任务 4.1 — 前端 E2E 冒烟测试 (新增)

| 预估工时 | 4h |
| 涉及文件 | `frontend/src/views/*.vue` |

覆盖核心用户路径：
1. 登录 → 仪表盘 → 店铺列表 → 商品浏览
2. 登录 → 客服工作台 → 会话处理 → AI 建议采纳
3. 登录 → 工单创建 → 分配 → 处理 → 关闭

建议使用 Playwright 或 Cypress 录制 + 断言。

---

#### 任务 4.2 — 文档化 By-Design 决策

| 预估工时 | 0.5h |
| 涉及文件 | `README.md` 或 `docs/DESIGN-DECISIONS.md` |

明确记录以下 by-design 决策：
- 商品不支持手动 CRUD，仅通过平台同步
- WebSocket `/ws/service` 仅用于实时通信，REST 端点已覆盖数据操作
- 语义搜索依赖向量回填，首次部署需执行 `seed.py --backfill --full`

---

## 3. 阻塞项解决方案

| 阻塞项 | 处理方式 | 责任人 |
|--------|----------|:----:|
| 平台运营功能不可用 | **修复** — 见任务 1.1 | 后端 A |
| 商品手动 CRUD | **文档化** — By design，商品仅同步 | 后端 B |
| WebSocket 测试 | **文档化** — 提供 Postman Collection 或 wscat 脚本 | QA |
| 知识库 SSE 测试 | **提供测试脚本** — 使用 Python `httpx` 流式读取 | QA |

---

## 4. 风险缓解措施

| 风险 | 缓解策略 | 实施阶段 |
|------|----------|:----:|
| **AI 功能强依赖 DashScope** | (1) 所有 AI 端点增加 try/except + 降级返回 (任务 2.2) (2) 增加 `/health/ai` 端点主动探测 (3) 文档说明 AI 服务不可用时的降级行为 | 第二阶段 |
| **向量搜索不完整** | (1) seed 文档明确 `--backfill` 为必要步骤 (2) 商品同步时自动触发增量 embedding (3) 增加 `embedding_status` 看板告警 | 第二阶段 |
| **多租户隔离不完整** | (1) 修复登录查询 (任务 1.3) (2) 全量审查所有 SQL 查询的 `merchant_id` 条件 (3) 增加集成测试：商户 A 无法访问商户 B 的数据 | 第一/三阶段 |
| **输入校验缺失** | (1) 全量替换 `body: dict` 为 Pydantic Schema (任务 2.3) (2) 增加边界值单元测试 | 第二/三阶段 |
| **前端未测试** | (1) 优先覆盖核心路径 E2E (任务 4.1) (2) 后续迭代补充全页面测试 | 第四阶段 |

---

## 5. 回归测试范围

### 5.1 每次修复后的最小回归集 (耗时 ~30min)

```bash
# 1. 健康检查
curl http://localhost:8012/api/v1/health

# 2. 登录 + 获取 token
TOKEN=$(curl -s -X POST .../auth/login ... | python -c "print(...)")

# 3. 受影响模块的冒烟测试（根据修复范围选择）
#    - 工单修复 → TC-TICK-001, 006, 006b, 011, 012, 014
#    - 店铺修复 → TC-SHOP-001, 004, 009
#    - AI 修复   → TC-AI-001, 005, TC-PROD-015
```

### 5.2 全量回归测试 (耗时 ~2h)

完成所有阶段修复后，重新执行 [TEST_REPORT.md](TEST_REPORT.md) 中的全部 104 个测试用例。

---

## 6. 上线前检查清单

| # | 检查项 | 通过标准 | 验证人 |
|---|--------|----------|:----:|
| 1 | `POST /api/v1/auth/platform/login` 路由注册 | OpenAPI 可见 + 功能正常 | |
| 2 | `POST /api/v1/tickets` 全参数不报 500 | category_id 缺/在/错三种场景均正确返回 | |
| 3 | 商品语义搜索有结果 | `GET /products/search?q=手机` 返回 ≥1 条 | |
| 4 | AI 催付话术正常或明确降级 | 200 + 含有效数据或明确错误说明 | |
| 5 | 所有 `body: dict` 已替换为 Pydantic Schema | `grep -rn "body:\s*dict" backend/app/api/` 返回空 | |
| 6 | 全量回归 104 用例通过率 ≥95% | 0 致命、0 严重、≤2 一般 | |
| 7 | 数据库迁移无残留 | `alembic check` 或手动确认表结构一致 | |
| 8 | Redis / ChromaDB 可连通 | health check 通过 | |
| 9 | DashScope API key 有效 | 向量生成 + LLM 调用均成功 | |
| 10 | 前端 3 个入口可正常登录 | admin:8093 / merchant:8094 / service:8095 登录成功 | |
| 11 | 文档更新 | README 包含首次部署步骤（seed + backfill） | |
| 12 | Git tag | `v2.0.1-rc1` 标记 | |

---

## 7. 附录：修复依赖关系图

```
第一阶段 (必须先修)
├── 任务 1.1: platform_login 路由 ▸ 解除平台功能阻塞
│     └── 依赖: 无
│     └── 被依赖: 审计日志、跨租户功能回归
├── 任务 1.2: 工单创建 500 ▸ 恢复工单核心链路
│     └── 依赖: 无
│     └── 被依赖: 任务 2.3 (Schema 模板)
└── 任务 1.3: 登录跨租户修复 ▸ 数据安全
      └── 依赖: 无
      └── 被依赖: 任务 3.2 (分类查询)

第二阶段 (依赖第一阶段完成)
├── 任务 2.1: 向量重建 ▸ 恢复搜索/AI
│     └── 依赖: 任务 1.1 (需要 API key 验证)
├── 任务 2.2: AI 催付修复 ▸ 恢复 AI 功能
│     └── 依赖: 任务 2.1 (向量影响 RAG 路径)
└── 任务 2.3: Schema 全面替换
      └── 依赖: 任务 1.2 (TicketCreate 已完成)

第三阶段 (可与第二阶段并行)
├── 任务 3.1: 响应格式统一
│     └── 依赖: 无 (前端需协调)
├── 任务 3.2: 分类列表修复
│     └── 依赖: 任务 1.3
├── 任务 3.3: Dashboard null 修复
│     └── 依赖: 无
└── 任务 3.4: 店铺重名检查
      └── 依赖: 无

第四阶段 (不阻塞上线)
├── 任务 4.1: 前端 E2E
└── 任务 4.2: 文档化 by-design
```

### 甘特图（文本）

```
Day 1 (8h)              Day 2 (8h)              Day 3 (8h)              Day 4 (4h)
├─ 1.1 (1h)             ├─ 2.1 (2h)             ├─ 3.1 (2h)             ├─ 4.1 (4h, E2E)
├─ 1.2 (3h)             ├─ 2.2 (3h)             ├─ 3.2 (1h)
├─ 1.3 (2h)             ├─ 2.3 (3h)             ├─ 3.3 (1h)
│                       │                       ├─ 3.4 (0.5h)
│                       │                       ├─ 回归测试 (2h)
├─ QA: 阶段1验证 (2h)    ├─ QA: 阶段2验证 (2h)    ├─ QA: 全量回归 (2h)     ├─ 上线
```

---

*计划制定日期: 2026-06-26 | 版本: v1.0*
