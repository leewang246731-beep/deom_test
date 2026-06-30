# Platform Tenant Context — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 平台管理员选择目标商户后，对商户作用域资源的写操作正常持久化（消除 platform token `merchant_id=None` 导致的 500）。

**Architecture:** 后端新增 `get_effective_merchant_id` 依赖（platform token 读 `X-Merchant-Id` 头，merchant token 用自身 `merchant_id`）+ `GET /merchants` 列表。前端 AdminLayout 顶部加商户选择器，`request.js` 自动注入 `X-Merchant-Id`。pilot 三模块（categories/skill_groups/users）替换 `current.merchant_id`。

**Tech Stack:** FastAPI (Python 3.13), Vue 3 + Element Plus + Pinia, MySQL 8.0

## Global Constraints

- 商户 token 隔离：**绝不**接受请求头覆盖 `merchant_id`，只用自己 token 内值。
- 平台 `super_admin` 通过 `require_roles` 时放行（现有 `dependencies.py:106` 逻辑不动）。
- 所有修改向后兼容，商户端（8094）行为不变。
- `python test_e2e_smoke.py` 78 用例不能回归。
- 本切片：infrastructure + pilot + 前端。铺开其余 12 文件另起计划。

---

### Task 1: Backend — `get_effective_merchant_id` 依赖

**Files:**
- Modify: `backend/app/api/v1/dependencies.py` — 在 `require_platform_roles` 之后追加

**Interfaces:**
- Produces: `get_effective_merchant_id(current, x_merchant_id, db) -> int` — 返回有效的 merchant_id
- Consumes: `CurrentUser` (from `get_current_user`), `Merchant` model

- [ ] **Step 1: 追加代码到 `dependencies.py`**

在文件末尾追加（`require_platform_roles` 函数之后，第 128 行之后）：

```python
def get_effective_merchant_id(
    current: CurrentUser = Depends(get_current_user),
    x_merchant_id: str = Header(None, alias="X-Merchant-Id"),
    db: Session = Depends(get_db),
) -> int:
    """统一解析当前操作的 merchant_id。

    商户 token → 永远用 token 内 merchant_id，忽略请求头（租户隔离）。
    平台 token → 取 X-Merchant-Id 头；缺失返回 40002。
    """
    if current.token_type == "access":
        if current.merchant_id is None:
            raise HTTPException(status_code=401, detail={"code": 40102, "msg": "不是商户员工"})
        return current.merchant_id

    # platform token — 要求 X-Merchant-Id 头
    if not x_merchant_id or not x_merchant_id.strip():
        raise HTTPException(
            status_code=400,
            detail={"code": 40002, "msg": "请先选择要管理的商户"},
        )
    try:
        mid = int(x_merchant_id.strip())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail={"code": 40002, "msg": "商户 ID 格式无效"},
        )

    merchant = db.query(Merchant).filter(Merchant.id == mid, Merchant.status == 1).first()
    if not merchant:
        raise HTTPException(
            status_code=400,
            detail={"code": 40002, "msg": "商户不存在或已停用"},
        )
    return mid
```

在文件顶部 import 区追加 `Merchant` model（第 14 行附近，其他 model import 之后）：

```python
from app.models.merchant import Merchant
```

确认 `Header` 已在文件顶部导入（第 9 行已有 `from fastapi import Depends, Header, HTTPException`）。

- [ ] **Step 2: 验证 backend 启动不报错**

```bash
cd backend && python -c "from app.api.v1.dependencies import get_effective_merchant_id; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/dependencies.py
git commit -m "feat: add get_effective_merchant_id dependency — platform reads X-Merchant-Id header"
```

---

### Task 2: Backend — `GET /merchants` 端点

**Files:**
- Create: `backend/app/api/v1/merchants.py`
- Modify: `backend/main.py` — 注册路由（第 155、157 行附近）

**Interfaces:**
- Produces: `GET /api/v1/merchants` → `{code:200, data:[{id,name,status}]}`
- Consumes: `get_platform_user` (Task 0, already exists)

- [ ] **Step 1: 创建 `merchants.py`**

```python
"""商户列表接口 — 平台端商户选择器数据源"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.v1.dependencies import CurrentUser, get_platform_user
from app.core.response import ok
from app.database.session import get_db
from app.models.merchant import Merchant

router = APIRouter(prefix="/merchants", tags=["商户管理"])


@router.get("")
def list_merchants(
    current: CurrentUser = Depends(get_platform_user),
    db: Session = Depends(get_db),
):
    """仅平台端可访问。返回所有正常商户供选择器使用。"""
    merchants = (
        db.query(Merchant)
        .filter(Merchant.status == 1)
        .order_by(Merchant.id)
        .all()
    )
    return ok([{"id": m.id, "name": m.name, "status": m.status} for m in merchants])
```

- [ ] **Step 2: 注册路由到 `main.py`**

在 `main.py:155` 的 import 行，`shops` 之后插入 `merchants`：

```python
# 改前（第 155 行）:
from app.api.v1 import ai, audit, auth, categories, conversations, dashboard, orders, products, recommendations, shops, skill_groups, sla, tickets, users, webhook_logs, webhooks, service_mode, openapi

# 改后:
from app.api.v1 import ai, audit, auth, categories, conversations, dashboard, merchants, orders, products, recommendations, shops, skill_groups, sla, tickets, users, webhook_logs, webhooks, service_mode, openapi
```

在 `main.py:158`（`shops.router` 之后）插入：

```python
app.include_router(merchants.router, prefix=settings.API_PREFIX)
```

- [ ] **Step 3: 验证端点**

```bash
# 确保 backend 运行中 (uvicorn main:app --host 127.0.0.1 --port 8012)
PT=$(curl -s -X POST http://127.0.0.1:8012/api/v1/auth/platform/login \
  -H "Content-Type: application/json" \
  -d '{"username":"super_admin","password":"123456"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
curl -s http://127.0.0.1:8012/api/v1/merchants -H "Authorization: Bearer $PT" | python -m json.tool
```

Expected: `{"code": 200, "msg": "ok", "data": [{"id": 11, "name": "数码旗舰", "status": 1}, ...]}`（至少 3 个商户）

再验证商户 token 被拒：
```bash
MT=$(curl -s -X POST http://127.0.0.1:8012/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456","merchant_id":11}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")
curl -s http://127.0.0.1:8012/api/v1/merchants -H "Authorization: Bearer $MT" -w "\nHTTP=%{http_code}\n"
```

Expected: `HTTP=403`

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/merchants.py backend/main.py
git commit -m "feat: add GET /merchants endpoint — platform-only merchant list"
```

---

### Task 3: Pilot — `categories.py` 替换 `current.merchant_id`

**Files:**
- Modify: `backend/app/api/v1/categories.py`

**Interfaces:**
- Consumes: `get_effective_merchant_id` (Task 1)
- Change: 每个端点增加 `mid: int = Depends(get_effective_merchant_id)`，函数体内 `current.merchant_id` → `mid`

- [ ] **Step 1: 修改 import 和依赖声明**

[`categories.py`](backend/app/api/v1/categories.py) 当前 import：
```python
from app.api.v1.dependencies import CurrentUser, get_current_merchant, get_current_user, require_roles
```

改为：
```python
from app.api.v1.dependencies import CurrentUser, get_current_user, get_effective_merchant_id, require_roles
```

- [ ] **Step 2: 修改 `list_categories`（第 36-40 行）**

```python
# 改前:
@router.get("")
def list_categories(current: CurrentUser = Depends(get_current_user), db: Session = Depends(get_db)):
    cats = db.query(Category).filter(
        Category.merchant_id == current.merchant_id
    ).order_by(Category.level, Category.sort_order).all()

# 改后:
@router.get("")
def list_categories(current: CurrentUser = Depends(get_current_user),
                    mid: int = Depends(get_effective_merchant_id),
                    db: Session = Depends(get_db)):
    cats = db.query(Category).filter(
        Category.merchant_id == mid
    ).order_by(Category.level, Category.sort_order).all()
```

- [ ] **Step 3: 修改 `create_category`（第 43-60 行）**

```python
# 改前:
def create_category(body: CategoryCreate, current: CurrentUser = Depends(require_roles("admin", "manager")),
                    db: Session = Depends(get_db)):
    # ... (body.parent_id 校验用到 current.merchant_id)
    parent = db.query(Category).filter(Category.id == body.parent_id,
                                        Category.merchant_id == current.merchant_id).first()
    # ...
    max_order = db.query(Category.sort_order).filter(
        Category.merchant_id == current.merchant_id).order_by(Category.sort_order.desc()).first()
    # ...
    cat = Category(merchant_id=current.merchant_id, name=body.name, ...)

# 改后:
def create_category(body: CategoryCreate,
                    current: CurrentUser = Depends(require_roles("admin", "manager")),
                    mid: int = Depends(get_effective_merchant_id),
                    db: Session = Depends(get_db)):
    # ... 改 body.parent_id 校验 ...
    parent = db.query(Category).filter(Category.id == body.parent_id,
                                        Category.merchant_id == mid).first()
    # ... 改 max_order ...
    max_order = db.query(Category.sort_order).filter(
        Category.merchant_id == mid).order_by(Category.sort_order.desc()).first()
    # ... 改 cat 构造 ...
    cat = Category(merchant_id=mid, name=body.name,
                   parent_id=body.parent_id, level=level, sort_order=sort_order)
```

- [ ] **Step 4: 修改 `update_category`（第 63-76 行）**

```python
# 改前:
def update_category(cat_id: int, body: CategoryUpdate,
                    current: CurrentUser = Depends(require_roles("admin", "manager")),
                    db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == cat_id,
                                     Category.merchant_id == current.merchant_id).first()

# 改后:
def update_category(cat_id: int, body: CategoryUpdate,
                    current: CurrentUser = Depends(require_roles("admin", "manager")),
                    mid: int = Depends(get_effective_merchant_id),
                    db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == cat_id,
                                     Category.merchant_id == mid).first()
```

函数体其余不动。

- [ ] **Step 5: 修改 `delete_category`（第 79-91 行）**

```python
# 改前:
def delete_category(cat_id: int, current: CurrentUser = Depends(require_roles("admin", "manager")),
                    db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == cat_id,
                                     Category.merchant_id == current.merchant_id).first()

# 改后:
def delete_category(cat_id: int,
                    current: CurrentUser = Depends(require_roles("admin", "manager")),
                    mid: int = Depends(get_effective_merchant_id),
                    db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == cat_id,
                                     Category.merchant_id == mid).first()
```

- [ ] **Step 6: 验证 — platform 端写分类成功**

```bash
# backend 保持运行；若无则启动：uvicorn main:app --host 127.0.0.1 --port 8012
PT=$(curl -s -X POST http://127.0.0.1:8012/api/v1/auth/platform/login \
  -H "Content-Type: application/json" \
  -d '{"username":"super_admin","password":"123456"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

# 带 X-Merchant-Id=11 创建分类
curl -s -X POST http://127.0.0.1:8012/api/v1/categories \
  -H "Authorization: Bearer $PT" \
  -H "Content-Type: application/json" \
  -H "X-Merchant-Id: 11" \
  -d '{"name":"ZZ_plan_test"}' -w "\nHTTP=%{http_code}\n"
```

Expected: `HTTP=200` 且 `"msg":"已创建"`

再验证 DB：
```bash
python -c "
import pymysql
c=pymysql.connect(host='127.0.0.1',port=3306,user='root',password='121300',database='demo_test')
r=c.cursor()
r.execute(\"SELECT id,name,merchant_id FROM categories WHERE name LIKE 'ZZ_plan%'\")
print(r.fetchall())
c.close()
"
```

Expected: `merchant_id=11` 的行存在。

- [ ] **Step 7: 验证 — 缺 X-Merchant-Id 返回 40002**

```bash
curl -s -X POST http://127.0.0.1:8012/api/v1/categories \
  -H "Authorization: Bearer $PT" \
  -H "Content-Type: application/json" \
  -d '{"name":"ZZ_no_header"}' -w "\nHTTP=%{http_code}\n"
```

Expected: `HTTP=400`，`detail.msg` 包含"请先选择要管理的商户"。

- [ ] **Step 8: 验证 — 商户端不被影响**

```bash
MT=$(curl -s -X POST http://127.0.0.1:8012/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456","merchant_id":11}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

# 商户 token 创建分类（不带 X-Merchant-Id）
curl -s -X POST http://127.0.0.1:8012/api/v1/categories \
  -H "Authorization: Bearer $MT" \
  -H "Content-Type: application/json" \
  -d '{"name":"ZZ_merchant"}'
```

Expected: 200，分类落在 merchant 11。

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/v1/categories.py
git commit -m "feat: categories — use get_effective_merchant_id for platform tenant context"
```

---

### Task 4: Pilot — `skill_groups.py` 替换 `current.merchant_id`

**Files:**
- Modify: `backend/app/api/v1/skill_groups.py` — 所有 6 处 `current.merchant_id` → `mid`

**Interfaces:**
- Consumes: `get_effective_merchant_id` (Task 1)

- [ ] **Step 1: 修改 import（第 5 行）**

```python
# 改前:
from app.api.v1.dependencies import CurrentUser, get_current_merchant, get_current_user, require_roles

# 改后:
from app.api.v1.dependencies import CurrentUser, get_current_user, get_effective_merchant_id, require_roles
```

- [ ] **Step 2: 逐一改 6 个端点，增加 `mid` 参数 + 替换 `current.merchant_id` → `mid`**

`list_groups`（第 17 行）：
```python
def list_groups(current: CurrentUser = Depends(get_current_user),
                mid: int = Depends(get_effective_merchant_id),
                db: Session = Depends(get_db)):
    groups = db.query(SkillGroup).filter(SkillGroup.merchant_id == mid).all()
```

`create_group`（第 37 行）：
```python
def create_group(body: SkillGroupCreate, current: CurrentUser = Depends(require_roles("admin", "manager")),
                 mid: int = Depends(get_effective_merchant_id),
                 db: Session = Depends(get_db)):
    g = SkillGroup(merchant_id=mid, name=body.name,
                    description=body.description or "")
```

`update_group`（第 47 行）：filter `SkillGroup.merchant_id == mid`
`delete_group`（第 62 行）：filter `SkillGroup.merchant_id == mid`
`add_member`（第 75 行）：两处 filter `SkillGroup.merchant_id == mid` 和 `MerchantUser.merchant_id == mid`
`remove_member`（第 99 行）：不变（此函数不直接引用 `current.merchant_id`）

- [ ] **Step 3: 验证 — platform 端创建技能组**

```bash
PT=$(curl -s -X POST http://127.0.0.1:8012/api/v1/auth/platform/login \
  -H "Content-Type: application/json" \
  -d '{"username":"super_admin","password":"123456"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

curl -s -X POST http://127.0.0.1:8012/api/v1/skill-groups \
  -H "Authorization: Bearer $PT" \
  -H "Content-Type: application/json" \
  -H "X-Merchant-Id: 11" \
  -d '{"name":"ZZ_plan_sg"}' -w "\nHTTP=%{http_code}\n"
```

Expected: `HTTP=200`，`msg: "已创建"`。

- [ ] **Step 4: Commit**

```bash
git add backend/app/api/v1/skill_groups.py
git commit -m "feat: skill_groups — use get_effective_merchant_id"
```

---

### Task 5: Pilot — `users.py` 替换 `current.merchant_id`

**Files:**
- Modify: `backend/app/api/v1/users.py`

**注意**：`list_users` 已有平台/商户双路径（`token_type == "access"` 判断），只改写操作（create/update/delete），list 保持现有分支逻辑但也要加 `mid`。

- [ ] **Step 1: 修改 import（第 5 行）**

```python
from app.api.v1.dependencies import CurrentUser, get_current_user, get_effective_merchant_id, require_roles
```

- [ ] **Step 2: 修改 `list_users`（第 25-44 行）**

平台 token 下，若未传 `merchant_id` query param，用 `X-Merchant-Id` 头的值自动筛选：

```python
def list_users(
    page_no: int = Query(1, alias="page", ge=1),
    page_size: int = Query(20, ge=1, le=200),
    role: str = Query(None),
    merchant_id: int = Query(None),
    current: CurrentUser = Depends(get_current_user),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    q = db.query(MerchantUser)
    if current.token_type == "access":
        q = q.filter(MerchantUser.merchant_id == current.merchant_id)
    elif merchant_id:
        q = q.filter(MerchantUser.merchant_id == merchant_id)
    else:
        q = q.filter(MerchantUser.merchant_id == mid)
```

- [ ] **Step 3: 修改 `create_user`（第 47-72 行）** — `current.merchant_id` → `mid`

```python
def create_user(
    body: UserCreate,
    current: CurrentUser = Depends(require_roles("admin")),
    mid: int = Depends(get_effective_merchant_id),
    db: Session = Depends(get_db),
):
    exist = db.query(MerchantUser).filter(
        MerchantUser.merchant_id == mid,
        MerchantUser.username == body.username,
    ).first()
    # ...
    u = MerchantUser(
        merchant_id=mid,
        # ...
    )
```

- [ ] **Step 4: 修改 `update_user`（第 75-98 行）** — filter `current.merchant_id` → `mid`
- [ ] **Step 5: 修改 `delete_user`（第 101-117 行）** — filter `current.merchant_id` → `mid`

- [ ] **Step 6: 验证 — platform 端创建用户**

```bash
PT=$(curl -s -X POST http://127.0.0.1:8012/api/v1/auth/platform/login \
  -H "Content-Type: application/json" \
  -d '{"username":"super_admin","password":"123456"}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

curl -s -X POST http://127.0.0.1:8012/api/v1/users \
  -H "Authorization: Bearer $PT" \
  -H "Content-Type: application/json" \
  -H "X-Merchant-Id: 11" \
  -d '{"username":"zz_plan_user","password":"123456","role":"service"}' -w "\nHTTP=%{http_code}\n"
```

Expected: `HTTP=200`，`msg: "用户已创建"`。

- [ ] **Step 7: 验证 — 租户隔离安全**

商户 token（merchant 11）伪造 `X-Merchant-Id: 12` → 仍创建在 11：

```bash
MT=$(curl -s -X POST http://127.0.0.1:8012/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"123456","merchant_id":11}' \
  | python -c "import sys,json; print(json.load(sys.stdin)['data']['access_token'])")

curl -s -X POST http://127.0.0.1:8012/api/v1/users \
  -H "Authorization: Bearer $MT" \
  -H "Content-Type: application/json" \
  -H "X-Merchant-Id: 12" \
  -d '{"username":"zz_hack","password":"123456","role":"service"}'
```

Expected: 200，但用 python 查 DB → `merchant_id=11`（不是 12）。

- [ ] **Step 8: Commit**

```bash
git add backend/app/api/v1/users.py
git commit -m "feat: users — use get_effective_merchant_id with tenant isolation"
```

---

### Task 6: Frontend — 商户选择器 + 请求头注入

**Files:**
- Modify: `frontend/src/views/AdminLayout.vue` — header 区域加商户 `<el-select>`
- Modify: `frontend/src/api/request.js` — platform token 时注入 `X-Merchant-Id`
- Modify: `frontend/src/api/index.js` — 新增 `getMerchants` 函数

**Interfaces:**
- Consumes: `GET /api/v1/merchants` (Task 2), `useAuthStore` (已有)
- Produces: `X-Merchant-Id` header on all platform requests

- [ ] **Step 1: 在 `api/index.js` 新增 `getMerchants`**

在文件末尾追加（第 164 行之后，`kbSupportedFormats` 之后）：

```javascript
// ---- merchants (platform only) ----
export const getMerchants = () => http.get('/merchants')
```

- [ ] **Step 2: 修改 `request.js` — 注入 `X-Merchant-Id` 头**

在请求拦截器中，token 读取之后、return 之前插入（`request.js` 第 10 行之后）：

```javascript
http.interceptors.request.use((config) => {
  const token = localStorage.getItem('platform_token') || localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`

  // 平台端：注入选中商户 ID
  const mid = localStorage.getItem('active_merchant_id')
  if (mid && localStorage.getItem('platform_token')) {
    config.headers['X-Merchant-Id'] = mid
  }

  return config
})
```

- [ ] **Step 3: 修改 `AdminLayout.vue` — header 区域加商户选择器**

在 `<header class="admin-header glass-header">` 内，`header-left` 与 `header-right` 之间插入（第 57 行，`</div>` 关闭 `header-left` 之后）：

```html
<div class="header-center">
  <el-select
    v-model="activeMerchant"
    placeholder="选择商户"
    size="small"
    style="width: 200px"
    @change="onMerchantChange"
    clearable
  >
    <el-option
      v-for="m in merchantList"
      :key="m.id"
      :label="m.name"
      :value="m.id"
    />
  </el-select>
</div>
```

在 `<script setup>` 内，`const router = useRouter()` 之后插入：

```javascript
import { getMerchants } from '../api'

// ── 商户选择器 ──
const activeMerchant = ref(parseInt(localStorage.getItem('active_merchant_id')) || null)
const merchantList = ref([])

onMounted(async () => {
  try {
    const res = await getMerchants()
    merchantList.value = res.data || []
    if (!activeMerchant.value && merchantList.value.length) {
      activeMerchant.value = merchantList.value[0].id
      localStorage.setItem('active_merchant_id', String(activeMerchant.value))
    }
  } catch { /* 非平台 token 则接口返回 403，静默 */ }
})

function onMerchantChange(val) {
  if (val) {
    localStorage.setItem('active_merchant_id', String(val))
  } else {
    localStorage.removeItem('active_merchant_id')
  }
}
```

- [ ] **Step 4: 添加样式（`<style scoped>` 内 `header-right` 之前）**

```css
.header-center {
  display: flex;
  align-items: center;
  flex: 1;
  justify-content: center;
}
```

- [ ] **Step 5: 验证 — 前端 dev server 编译不报错**

```bash
cd frontend && npx vite build --mode admin 2>&1 | tail -5
```

Expected: `✓ built in ...`

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/index.js frontend/src/api/request.js frontend/src/views/AdminLayout.vue
git commit -m "feat: admin layout — add merchant selector and X-Merchant-Id injection"
```

---

### Task 7: Verification — 全链路回归

- [ ] **Step 1: 启动全栈并验证 E2E 冒烟测试**

```bash
cd backend
python test_e2e_smoke.py 2>&1 | tail -20
```

Expected: 78/78 passed（或全部通过，失败数 = 0）。

- [ ] **Step 2: 验证 RAG 回归**

```bash
cd backend && python -m pytest tests/ -q 2>&1 | tail -5
```

Expected: 10 passed。

- [ ] **Step 3: 手动全链路验证**

在浏览器访问 `http://127.0.0.1:8093`，登录 `super_admin / 123456`：
1. 顶部出现商户选择器，默认选中第一个商户
2. 切换到不同商户，分类列表刷新
3. 点击"新建分类"，填写名称，保存
4. 验证分类出现在列表中
5. 编辑分类 → 名称变更
6. 删除分类 → 消失

- [ ] **Step 4: Commit 收尾**

```bash
git commit --allow-empty -m "verify: all pilot endpoints pass — platform tenant context operational"
```

---

### Task 8 (Bonus): 铺开路线图

pilot 验证通过后，剩余 12 文件使用相同机械模式铺开：

| 文件 | `current.merchant_id` 引用 | 当前 guard | 改法 |
|---|---|---|---|
| `products.py` | 12 | `get_current_merchant` | 换 `get_current_user` + `mid` |
| `tickets.py` | 31 | `get_current_merchant` | 换 `get_current_user` + `mid` |
| `orders.py` | 8 | `get_current_merchant` | 换 `get_current_user` + `mid` |
| `recommendations.py` | 11 | `get_current_merchant` | 换 `get_current_user` + `mid` |
| `sla.py` | 4 | `get_current_merchant` | 换 `get_current_user` + `mid` |
| `service_mode.py` | 6 | `get_current_merchant` | 换 `get_current_user` + `mid` |
| `conversations.py` | 7 | `get_current_merchant` | 换 `get_current_user` + `mid` |
| `ai.py` | 10 | `get_current_merchant` | 换 `get_current_user` + `mid` |
| `shops.py` | 13 | mixed | 每个端点加 `mid` 替换 |
| `dashboard.py` | 8 | mixed | 每个端点加 `mid` 替换 |
| `openapi.py` | 2 | internal | 每个端点加 `mid` 替换 |
| `categories.py` | 6 | (已在 Task 3 改完) | ✅ done |

每个文件的改法是机械的：① import 加 `get_effective_merchant_id` ② 每个 `def` 加 `mid: int = Depends(get_effective_merchant_id)` ③ 函数体内 `current.merchant_id` → `mid`。
