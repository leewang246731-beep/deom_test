# vMall 虚拟电商平台

> 独立运行的虚拟电商平台，为"多平台智能托管 SaaS"提供真实业务数据源。
> **可完全抽离独立部署，与 SaaS 项目零耦合。**

---

## 快速启动

```bash
cd backend
pip install -r requirements.txt
python seed_vmall.py
uvicorn main:app --port 8020

# 消费者端 (买家 H5) :8090
cd ../frontend_consumer && npm install && npm run dev

# 运营后台 :8091
cd ../frontend_admin && npm install && npm run dev
```

| 角色 | 账号 | 密码 |
|------|------|------|
| 买家 | buyer_test | 123456 |
| 管理员 | admin_vmall | 123456 |

---

## 端口隔离

| 系统 | 端口 | 数据库 |
|------|:---:|------|
| vMall Backend | 8020 | vmall_db |
| vMall Consumer | 8090 | — |
| vMall Admin | 8091 | — |
| SaaS Backend | 8010 | demo_test |
| SaaS Frontend | 8080 | — |

---

## 功能模块

### 消费者端 (7 页面)
| 页面 | 路由 | 功能 |
|------|------|------|
| 登录 | /login | buyer_test / 123456 |
| 首页 | /home | 商品瀑布流 + 类目筛选 + 排序 + 导航入口 |
| 商品详情 | /product/:id | SKU 选择器 + 联动价格库存 + 立即购买 + 联系客服 |
| 我的订单 | /orders | 状态筛选 + 支付 + 申请售后 |
| **个人中心** | /profile | **钱包余额 + 交易记录 + 个人信息编辑** |
| 客服会话 | /chat/:id | 收发消息 |

### 运营后台 (7 页面)
| 页面 | 路由 | 功能 |
|------|------|------|
| 登录 | /login | admin_vmall / 123456 |
| 总览 | /dashboard | 今日订单 / 待发货 / 待审核售后 / GMV |
| 订单管理 | /orders | 列表 + 发货(填物流,查看轨迹) |
| 售后审核 | /after-sales | 审核(通过/拒绝) + 确认收货 |
| 客服消息 | /messages | 会话列表 + 回复买家 |
| **钱包管理** | /wallets | **买家列表 + 充值(金额/备注) + 交易记录查询** |
| 系统设置 | /settings | 店铺信息 + Webhook 地址 |

---

## 物流系统

### 状态机
```
PENDING → PICKED → IN_TRANSIT → OUT_FOR_DELIVERY → DELIVERED
                                    ↓                  (终态)
                                  FAILED → 重新派送/退回
                                    ↓
                                  STUCK → 加急/取消
```

### 运营管理 API
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/admin/logistics/{order_id}` | 查看物流详情 + 完整轨迹 |
| POST | `/api/v1/admin/logistics/{order_id}/ship` | 发货 |
| POST | `/api/v1/admin/logistics/{log_id}/advance` | 手动推进一节点 |
| POST | `/api/v1/admin/logistics/{log_id}/exception` | 设置异常(FAILED/STUCK) |
| POST | `/api/v1/admin/logistics/{log_id}/resolve` | 解决异常 |

### 钱包管理 API
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/consumer/profile` | 获取个人信息 + 钱包余额 |
| PUT | `/api/v1/consumer/profile` | 更新个人信息 |
| GET | `/api/v1/consumer/wallet` | 查询钱包余额 |
| GET | `/api/v1/consumer/wallet/transactions` | 查询交易记录(分页) |
| GET | `/api/v1/admin/wallets` | 所有买家钱包列表 |
| GET | `/api/v1/admin/wallets/{buyer_id}` | 单个买家钱包 |
| POST | `/api/v1/admin/wallets/{buyer_id}/recharge` | **充值** `{amount,remark}` |
| GET | `/api/v1/admin/wallets/{buyer_id}/transactions` | 该买家交易记录 |

### 自动推进
后台 asyncio 循环每30秒扫描活跃物流并推进一个节点。配置: `.env` 中 `LOGISTICS_INTERVAL_SECONDS=30`。

---

## OpenAPI（SaaS 对接）

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/openapi/auth` | 获取 Token `{merchant_id,shop_id}` |
| GET | `/openapi/products` | 商品同步(分页+增量+SKU) |
| GET | `/openapi/orders` | 订单同步(状态+售后+分页) |
| POST | `/openapi/orders/{id}/deliver` | SaaS 发货指令 |
| POST | `/openapi/after-sales/{id}/approve` | SaaS 审核售后 |
| GET | `/openapi/logistics/{order_id}` | **物流查询(含完整轨迹)** |
| GET | `/openapi/conversations` | 会话同步 |
| POST | `/openapi/messages` | SaaS 发送消息 |

### Webhook 事件

| 事件 | 触发时机 |
|------|---------|
| `ORDER_PAID` | 支付成功 |
| `ORDER_SHIPPED` | 发货 |
| `LOGISTICS_UPDATED` | **物流节点变化** |
| `ORDER_COMPLETED` | 签收完成 |
| `AFTER_SALE_CREATED` | 售后申请 |
| `REFUND_SUCCESS` | 退款完成 |
| `NEW_MESSAGE` | 买家新消息 |

SaaS Webhook 接收端点: `POST /api/v1/webhooks/vmall`

---

## 数据库 (vmall_db, 15 表)

| 表 | 用途 |
|----|------|
| vm_buyers | 买家 |
| vm_products | 商品(含SKU JSON) |
| vm_orders | 订单(7状态+售后状态) |
| vm_order_items | 订单明细 |
| vm_after_sales | 售后申请 |
| vm_logistics | 物流主表(状态机+异常+快递员) |
| vm_logistics_tracks | 物流轨迹节点 |
| vm_logistics_script_templates | 物流话术模板 |
| vm_conversations | 会话 |
| vm_messages | 消息 |
| **vm_wallets** | **买家钱包(余额/累计充值/累计消费)** |
| **vm_wallet_transactions** | **充值/消费/退款交易记录** |
| vm_platform_settings | 平台配置 |
| vm_platform_admins | 管理员 |
| vm_webhook_logs | Webhook 推送日志 |

---

## 种子数据

`seed_vmall.py`（幂等）:
- 50 商品 (含 SKU 规格: 颜色/尺码/内存)
- 60 订单 (6 pending_payment + 6 paid + 30 shipped + 6 received + 10 completed + 2 closed)
- 测试买家初始余额 500 元 (含注册赠送记录)
- 45 单已发货含完整物流轨迹 (PICKED/IN_TRANSIT/OUT_FOR_DELIVERY/DELIVERED/FAILED/STUCK)
- 6 条物流话术模板
- 10 条会话
- 物流自动推进器在服务启动时运行

---

## 目录结构

```
vmall_system/
├── backend/
│   ├── main.py                       # FastAPI :8020 (含物流模拟器)
│   ├── seed_vmall.py                 # 种子脚本(幂等)
│   ├── requirements.txt / .env
│   └── app/
│       ├── core/                     # config / security / database / redis / response
│       ├── models/                   # 13 表 ORM
│       ├── api/
│       │   ├── consumer/             # 买家端 (auth/products/orders/conversations/after_sales)
│       │   ├── admin/                # 运营端 (auth/orders/after_sales/conversations/settings/logistics)
│       │   └── openapi/              # SaaS 对接 (router + logistics)
│       ├── services/                 # order_state / logistics_engine / fake_logistics / webhook
│       └── tasks/                    # logistics_simulator (asyncio 自动推进)
├── frontend_consumer/                # Vue3 买家 H5 :8090
├── frontend_admin/                   # Vue3 运营后台 :8091
└── README.md                         # 本文档
```
