# 架构设计 · 多平台智能托管 SaaS 平台

---

## 一、系统架构

```
┌──────────────────────────────────────────────────────────────┐
│                      Frontend (管理后台)                      │
│  Vue3 + Vite + Element Plus + Pinia + Axios + WebSocket      │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│  │ 工作台  │ │ 店铺管理 │ │ 商品库  │ │ 订单中心 │ │客服工作台│   │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘   │
│  ┌────────┐                                                │
│  │ AI配置  │                                                │
│  └────────┘                                                │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTPS/WSS
┌──────────────────────────┴───────────────────────────────────┐
│                      Gateway                                 │
│  Nginx 反向代理 · JWT 认证 · CORS · 限流                     │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────┐
│                   Service Layer (FastAPI)                     │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐   │
│  │Auth    │ │Shop    │ │Product │ │Order   │ │AI      │   │
│  │Service │ │Service │ │Service │ │Service │ │Service │   │
│  └────────┘ └────────┘ └────────┘ └────────┘ └────────┘   │
│  ┌──────────────┐ ┌──────────────┐                          │
│  │Platform Sync │ │AI Suggest   │  Celery 异步任务          │
│  │(Celery Beat) │ │(向量检索+LLM)│                          │
│  └──────────────┘ └──────────────┘                          │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────┐
│                   Platform Connector Layer                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           PlatformConnector (Abstract Base)           │   │
│  │  + fetch_products()  + fetch_orders()                │   │
│  │  + send_message()    + get_conversations()           │   │
│  └─────┬──────────┬──────────┬──────────────────────────┘   │
│  ┌─────┴──┐ ┌─────┴──┐ ┌─────┴──────┐                       │
│  │ Mock   │ │ Taobao │ │ JD         │  (一期: Mock 完整)    │
│  │(一期)  │ │(二期)  │ │(二期)     │                       │
│  └────────┘ └────────┘ └────────────┘                       │
└──────────────────────────┬───────────────────────────────────┘
                           │
┌──────────────────────────┴───────────────────────────────────┐
│                       Data Layer                              │
│  MySQL 8.0 │ ChromaDB │ Redis 7 │ Celery + RabbitMQ          │
└──────────────────────────────────────────────────────────────┘
```

---

## 二、多租户架构

```
Tenant A (merchant_id=1)          Tenant B (merchant_id=2)
┌──────────────────────┐        ┌──────────────────────┐
│  Shop 1 (Mock女装)    │        │  Shop 3 (Mock数码)    │
│  Shop 2 (Mock数码)    │        │  Shop 4 (抖音·二期)   │
│                      │        │                      │
│  Employee:           │        │  Employee:           │
│   admin / manager    │        │   admin / service    │
│   / service          │        │                      │
│                      │        │                      │
│  ChromaDB:           │        │  ChromaDB:           │
│   merchant_1         │        │   merchant_2         │
│                      │        │                      │
│  Redis: m:1:*        │        │  Redis: m:2:*        │
└──────────────────────┘        └──────────────────────┘
```

**隔离规则：**
- 所有 SQL 查询强制 `WHERE merchant_id = current_merchant.id`
- ChromaDB Collection 命名 `merchant_{merchant_id}`
- Redis Key 前缀 `m:{merchant_id}:`
- JWT 中携带 `merchant_id`，所有 API 通过 `Depends(get_current_merchant)` 校验

---

## 三、Platform Connector 设计

### 抽象基类

```python
# core/platform_connector/base.py
from abc import ABC, abstractmethod

class PlatformConnector(ABC):
    """Abstract base for all e-commerce platform connectors."""
    
    @abstractmethod
    async def fetch_products(self, shop_id: int) -> List[dict]:
        """Pull latest products from the platform."""
        ...
    
    @abstractmethod
    async def fetch_orders(self, shop_id: int, start_time: datetime) -> List[dict]:
        """Pull orders since a given time."""
        ...
    
    @abstractmethod
    async def send_message(self, shop_id: int, buyer_openid: str, content: str) -> bool:
        """Send a message to a buyer on the platform."""
        ...
    
    @abstractmethod
    async def get_conversations(self, shop_id: int) -> List[dict]:
        """Get active conversations for customer service."""
        ...
```

### Mock 连接器

```python
# core/platform_connector/mock.py
class MockPlatformConnector(PlatformConnector):
    """Generate realistic demo data with Faker. No external API calls."""
    
    def __init__(self):
        self.fake = Faker('zh_CN')
    
    async def fetch_products(self, shop_id: int) -> List[dict]:
        """Generate 50 products matching the shop's category."""
        ...
    
    async def get_conversations(self, shop_id: int) -> List[dict]:
        """Generate 30 conversations with realistic buyer questions."""
        ...
```

### 工厂函数

```python
# api/v1/dependencies.py
def get_platform_connector(shop_id: int) -> PlatformConnector:
    shop = db.query(PlatformShop).filter(PlatformShop.id == shop_id).first()
    if settings.PLATFORM_MODE == "mock" or shop.platform_type == "mock":
        return MockPlatformConnector()
    # Real platform connectors (Phase 2)
    if shop.platform_type == "taobao":
        return TaobaoConnector(shop.app_key, shop.app_secret)
    raise NotImplementedError(f"Platform {shop.platform_type} not yet supported")
```

---

## 四、技术选型

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue 3 | 3.4+ | 管理后台 SPA |
| Vite | 5.0+ | 构建工具 |
| Element Plus | 2.4+ | 后台 UI 组件库（Table/Form/Dialog） |
| Pinia | 2.1+ | 状态管理（user/merchant 信息） |
| Axios | 1.6+ | HTTP 请求 |
| WebSocket | 原生 | 客服工作台实时消息 |
| ECharts | 5.5+ | 数据看板图表 |

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.10+ | — |
| FastAPI | 0.109+ | Web 框架 + WebSocket |
| SQLAlchemy | 2.0+ | ORM + 异步查询 |
| Pydantic | 2.5+ | 数据验证 |
| Celery | 5.3+ | 异步任务（同步、AI话术生成） |
| Redis | 7.0+ | 缓存 + Session + 分布式锁 + Token 存储 |
| RabbitMQ | 3.12+ | Celery 消息队列 |

### AI 引擎

| 技术 | 用途 |
|------|------|
| BGE-M3 | 商品描述 + 历史话术向量化 (1024维) |
| ChromaDB | 向量存储与语义检索（按商户隔离 Collection） |
| 千问 / GPT | LLM 话术生成（将检索结果 + 买家问题 → 生成回复） |
| Faker (zh_CN) | Mock 模式生成中文虚拟数据 |

### 部署

| 技术 | 用途 |
|------|------|
| Docker Compose | 本地开发一键启动 |
| Nginx | 反向代理 |

---

## 五、性能指标

| 指标 | 目标 |
|------|:---:|
| 商品列表 API (P95) | < 500ms |
| AI 话术建议 (向量检索+LLM) | < 2s |
| 语义搜索 | < 1s |
| 平台同步 (Celery) | 每30分钟 |
| 并发商户 | 50+ |
