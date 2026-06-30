# Slice 3 — Real Connector Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** 移除全局 mock 短路，per-shop 选择 connector；vmall 店铺创建时自动获取 access_token。

**Architecture:** Connector factory 改为 per-shop 模式；bind_shop 调 vmall `/openapi/auth` 取 token；调度器和手动同步自动走真实路径。

**Tech Stack:** FastAPI (Python 3.13), Vue 3 + Element Plus, MySQL, httpx

## Global Constraints

- 不改 taobao/jd（无凭证），降级 mock + warning
- `PLATFORM_MODE` 配置保留但不再控制 connector 选择
- 向后兼容：mock 店铺行为不变

---

### Task 1: Connector factory — 移除全局 mock，per-shop 模式

**Files:**
- Modify: `backend/app/core/platform_connector/__init__.py`

- [ ] **Step 1: 替换 `get_platform_connector`**

```python
def get_platform_connector(shop_id: int, db: Session) -> PlatformConnector:
    """
    工厂函数：按店铺 platform_type 返回连接器实例（per-shop 模式）。
    - platform_type=mock → MockPlatformConnector
    - platform_type=vmall + access_token → V3Connector
    - platform_type=vmall 无 token → MockPlatformConnector + warning
    - taobao/jd → MockPlatformConnector + warning（未对接真实平台）
    """
    import logging
    _log = logging.getLogger(__name__)

    shop = db.query(PlatformShop).filter(PlatformShop.id == shop_id).first()
    if shop is None:
        raise ValueError(f"店铺不存在: shop_id={shop_id}")

    if shop.platform_type == "mock":
        return MockPlatformConnector()

    if shop.platform_type == "vmall":
        if shop.access_token:
            base_url = shop.shop_url or "http://127.0.0.1:8020"
            return V3Connector(base_url, shop.access_token)
        _log.warning(f"shop {shop_id}: vmall 店铺无 access_token，降级 mock")
        return MockPlatformConnector()

    if shop.platform_type in ("taobao", "jd"):
        _log.warning(f"shop {shop_id}: {shop.platform_type} 未对接真实平台，降级 mock")
        return MockPlatformConnector()

    raise NotImplementedError(f"平台 {shop.platform_type} 暂未支持")
```

- [ ] **Step 2: 验证 import**

```bash
cd backend && python -c "from app.core.platform_connector import get_platform_connector; print('import OK')"
```

- [ ] **Step 3: Commit**

```bash
git add app/core/platform_connector/__init__.py
git commit -m "feat: connector factory — per-shop mode, remove global mock shortcut"
```

---

### Task 2: bind_shop + regenerate_token — vmall auth

**Files:**
- Modify: `backend/app/api/v1/shops.py:59-85` (bind_shop), `:181-200` (regenerate_token)

- [ ] **Step 1: 修改 `bind_shop`**

在 `db.refresh(shop)` 之后（第 84 行），`return ok(...)` 之前插入 vmall auth：

```python
    db.refresh(shop)

    # vmall 店铺：自动获取 access_token
    if shop.platform_type == "vmall" and shop.shop_url:
        try:
            import httpx
            auth_url = f"{shop.shop_url.rstrip('/')}/openapi/auth"
            resp = httpx.post(auth_url, json={
                "merchant_id": mid,
                "shop_id": shop.id,
            }, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                shop.access_token = data.get("access_token")
                shop.token_expire_at = datetime.now() + timedelta(seconds=data.get("expires_in", 86400 * 7))
                db.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"vmall auth failed for shop {shop.id}: {e}")

    return ok({"id": shop.id, "shop_name": shop.shop_name})
```

在文件顶部 import 区追加：
```python
from datetime import datetime, timedelta
```

（`httpx` lazy import 在函数内，避免模块级依赖。）

- [ ] **Step 2: 修改 `regenerate_token`**

第 189 行后补上真实 vmall auth 调用（替换现有纯 DB update）：

```python
    # vmall 店铺：重新获取 access_token
    if shop.platform_type == "vmall" and shop.shop_url:
        try:
            import httpx
            auth_url = f"{shop.shop_url.rstrip('/')}/openapi/auth"
            resp = httpx.post(auth_url, json={
                "merchant_id": mid,
                "shop_id": shop.id,
            }, timeout=10)
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                shop.access_token = data.get("access_token")
                shop.token_expire_at = datetime.now() + timedelta(seconds=data.get("expires_in", 86400 * 7))
                db.commit()
                return ok({"access_token": "refreshed", "expires_in": data.get("expires_in")}, msg="已刷新")
        except Exception as e:
            raise HTTPException(status_code=502, detail={"code": 50202, "msg": f"vmall auth 失败: {e}"})
```

（`datetime`, `timedelta` 已在 Step 1 导入。）

- [ ] **Step 3: 验证 import**

```bash
cd backend && python -c "from app.api.v1.shops import router; print('import OK')"
```

- [ ] **Step 4: Commit**

```bash
git add app/api/v1/shops.py
git commit -m "feat: bind_shop + regenerate_token — auto vmall access_token via /openapi/auth"
```

---

### Task 3: Frontend — Connectors.vue token 状态

**Files:**
- Modify: `frontend/src/views/Connectors.vue`

- [ ] **Step 1: 在店铺列表中加 token 状态标签**

在表格的"操作"列之前（或店铺名称之后）加一列：

```html
<el-table-column label="Token" width="100">
  <template #default="{ row }">
    <el-tag v-if="row.access_token" type="success" size="small">有效</el-tag>
    <el-tag v-else type="info" size="small">未获取</el-tag>
  </template>
</el-table-column>
```

（`shops` API 返回的 shop 对象包含 `access_token` 字段——确认 `_shop_dict` 已返回。）

- [ ] **Step 2: 验证 build**

```bash
cd frontend && npx vite build --mode admin 2>&1 | tail -3
```

- [ ] **Step 3: Commit**

```bash
git add src/views/Connectors.vue
git commit -m "feat: connectors page — show access_token status tag"
```

---

### Task 4: Verification

- [ ] **Step 1: 回归测试**

```bash
cd backend && python test_e2e_smoke.py 2>&1 | tail -5
```

Expected: ~75-78 passed（KB 预存问题可忽略）。

- [ ] **Step 2: 手动验证**

1. 创建 vmall 店铺 → 检查 DB `access_token` 非空
2. 同步 vmall 店铺 → 真实商品/订单同步（需 vmall 运行）
3. 创建 mock 店铺 → `access_token=NULL`，sync 走 mock

- [ ] **Step 3: Commit**

```bash
git commit --allow-empty -m "verify: slice 3 regression — E2E pass"
```
