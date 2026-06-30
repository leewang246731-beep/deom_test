# 设计 — 平台端多租户上下文（修复"操作没效果"的真因）

> **本文件取代** `2026-06-30-slice1-orders-aftersale-design.md` 作为**第一个切片**。订单/售后联动顺延到后续切片。
> 依据：运行时复现（后端 8012 + 真实 MySQL/Redis）确诊，"业务逻辑没跑通"不是 Mock 连接器问题，而是平台端缺租户上下文。

## 1. 根因（已复现，附 traceback）

- 平台运营用户（`super_admin`）token `type=platform`、`merchant_id=None`（按 `dependencies.py` 设计为跨租户）。
- 但商户作用域资源表 `merchant_id NOT NULL`，所有 create 写死 `merchant_id=current.merchant_id`（=None）。
- 平台端写操作 → `IntegrityError (1048, "Column 'merchant_id' cannot be null")` → 500 → 零效果。
- 实测：平台端 分类/技能组/用户 create = 500；工单 create = 403（`get_current_merchant` 直接拒平台）。商户端同操作 = 200。

**影响面（全量）**：`current.merchant_id` 使用 **131 处 / 15 文件**；`get_current_merchant` 硬门 **39 处**。

## 2. 方案：选择商户上下文（已确认）

平台管理员先选定一个目标商户，之后对商户作用域资源的增删改查都用选中的 `merchant_id`。

### 2.1 后端：统一解析依赖 `effective_merchant_id`
新增 `app/api/v1/dependencies.py::get_effective_merchant_id`：
- **商户 token** → 永远用 token 内 `merchant_id`，**忽略任何请求头**（租户隔离，安全关键）。
- **平台 token** → 取请求头 `X-Merchant-Id`；缺失时对"商户作用域写/查"返回 `400 code=40002 "请先选择要管理的商户"`。
- 校验该 merchant 存在且 `status` 正常，否则 `404/400`。

替换策略：把商户作用域端点里的 `current.merchant_id` 与 `get_current_merchant` 替换为 `get_effective_merchant_id`。**纯跨租户聚合读**（如平台总览看板）保持可不选商户。

### 2.2 后端：新增 `GET /merchants`（平台专用）
供选择器拉取商户列表 `[{id,name,status}]`。仅 platform token 可访问。

### 2.3 前端（8093 平台端）
- Layout 顶部全局**商户选择器**：挂载时拉 `GET /merchants`，选中值存 `localStorage(active_merchant_id)` + 轻量 store。
- `request.js` 请求拦截器：当持有 `platform_token` 时，自动注入头 `X-Merchant-Id: <active_merchant_id>`。
- 守卫：未选商户时，商户作用域页面提示"请先在顶部选择商户"。

## 3. 范围与推进

| 阶段 | 内容 | 验收 |
|---|---|---|
| **基础设施** | `get_effective_merchant_id` + `GET /merchants` + 前端选择器 + 头注入 | 平台 token+头 → 写成功落库 |
| **试点（带测试）** | categories / skill_groups / users（已证实 500 的三个） | 三者平台端 create 由 500→200，DB 落 merchant_id |
| **铺开** | products / tickets / orders / recommendations / sla / service_mode / conversations / ai / shops / dashboard 中的商户作用域端点 | 逐文件替换，回归不破坏商户端 |

## 4. 错误码
- `40002` 平台用户未选择商户（商户作用域操作缺 `X-Merchant-Id`）。
- 其余沿用既有码。

## 5. 测试计划
- **复现→修复**：平台 token + `X-Merchant-Id=11` 创建分类 → 200，DB 出现 `merchant_id=11` 行。
- **缺上下文**：平台 token 无头 → 400/40002。
- **隔离安全**：商户 token（merchant 11）伪造 `X-Merchant-Id=12` → 仍写入 11，绝不越权到 12。
- **回归**：商户端各 create 维持 200；`python test_e2e_smoke.py`（78 用例）通过。

## 6. 不做（后续切片）
- 订单/售后对 vmall 真实联动（顺延，见被取代的 spec）。
- 商户端 UI 刷新类问题：待"全量实测状态表"确认后单列。
- Mock→real 连接器切换。
