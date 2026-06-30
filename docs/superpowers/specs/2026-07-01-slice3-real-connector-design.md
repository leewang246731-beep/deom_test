# Slice 3 设计 — 店铺绑定/同步 real 模式

> 约束：**可改 vmall**（已有接口足够）。改 taobao/jd 连接器代码但不接入真实平台（无凭证）。

## 1. 现状

- `PLATFORM_MODE=mock` 全局默认 → `get_platform_connector` 第一行短路返回 Mock
- `bind_shop` 创建 vmall 店铺时**不调用** `/openapi/auth` 获取 token → `access_token=NULL`
- 即使关了 mock 模式，V3Connector 也因无 token 而不可用
- 30min 调度器和手动 sync 按钮都走 mock 数据

## 2. 设计

### 2.1 Connector factory：移除全局 mock 短路

`backend/app/core/platform_connector/__init__.py`：

删掉：
```python
if settings.PLATFORM_MODE == "mock":
    return MockPlatformConnector()
```

改为 per-shop：
- `platform_type == "mock"` → MockPlatformConnector
- `platform_type == "vmall"` + 有 `access_token` → V3Connector
- `platform_type == "vmall"` + 无 token → 降级 Mock + log warning
- taobao/jd → 降级 Mock + log warning（无凭证）

`PLATFORM_MODE` 配置项保留但不再控制 connector 选择。后续可废弃。

### 2.2 `bind_shop`：自动获取 vmall token

创建 `platform_type="vmall"` 店铺后：
1. 调 vmall `POST {shop_url}/openapi/auth` — 入参 `{merchant_id, shop_id}`
2. 返回 `{access_token, expires_in}` → 存入 `PlatformShop.access_token` + `token_expire_at`
3. 失败 → 店铺仍创建但无 token，sync 时降级 mock

### 2.3 `regenerate_token`：刷新 token

已有端点 `POST /shops/{id}/regenerate-token`，补上真实 vmall 调用逻辑。

### 2.4 前端 `Connectors.vue`

展示每个店铺的 token 状态标签（有效/缺失/已过期）。

### 2.5 调度器 + 手动同步

无需改动——`get_platform_connector` 变更后，`sync_shop` / `scheduler` 自动走真实路径。

## 3. 变更清单

| 文件 | 改动 |
|---|---|
| `backend/app/core/platform_connector/__init__.py` | 移除全局 mock 短路，per-shop 模式 |
| `backend/app/api/v1/shops.py` | bind_shop + regenerate_token 调 vmall auth |
| `frontend/src/views/Connectors.vue` | token 状态标签 |
| `backend/app/core/config.py` | PLATFORM_MODE 标记 deprecated |

## 4. 测试

- `bind_shop` vmall → `access_token` 非空 + `token_expire_at` 非空
- `sync_shop` vmall → 通过 V3Connector 拉回真实商品/订单
- mock 店铺 → `sync_shop` 行为不变
- vmall 不可达时 `bind_shop` → 店铺创建成功，token 为空，sync 降级 mock
