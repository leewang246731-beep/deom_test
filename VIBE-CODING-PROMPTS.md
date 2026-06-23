# Vibe Coding 提示词

> 使用以下提示词快速用 AI 编程助手搭建项目

---

## 一期：SaaS 骨架 + Mock 模式 + AI 话术

```
项目：多平台智能托管 SaaS 平台
技术栈：Vue3 + Vite + Element Plus + FastAPI + SQLAlchemy + MySQL + ChromaDB + Redis + Celery

核心架构：
1. 多租户：merchants 表 + merchant_users（admin/manager/service），所有查询强制 merchant_id 过滤
2. Platform Connector 抽象层：base.py ABC → mock.py (Faker) / taobao.py (NotImplemented)
3. Mock 模式：Faker zh_CN 生成真实感中文数据，无需外部平台
4. AI 引擎：BGE-M3 向量化 + ChromaDB 语义检索 + 千问 LLM 生成话术

后端：
1. 商户系统：merchants / merchant_users（admin/manager/service，删除 consumer）
2. 店铺管理：platform_shops 绑定/解绑/同步，Mock 模式一键创建
3. 商品库：external_products 同步→向量化，支持语义搜索
4. 订单中心：external_orders 列表/详情/售后(Mock)/催单
5. 客服工作台：WebSocket 实时推送，conversations 会话管理
6. AI 话术：POST /ai/suggest（商品知识+历史话术→3条建议，<2s）
7. 催单：POST /ai/campaign/pending-payment（千人千面话术+模拟发送）
8. Celery 定时同步：每30分钟拉取最新数据
9. 种子脚本：1商户+2店铺+100商品+60会话+200订单

前端（管理后台）：
1. 左侧菜单 + 顶部导航布局，删除所有 C 端页面
2. 工作台 /dashboard：统计卡片（订单量/会话数/AI采纳率/同步状态）
3. 店铺管理 /shops：列表 + Mock 一键绑定弹窗
4. 商品库 /products：表格 + 语义搜索框
5. 订单中心 /orders：按平台筛选 + 售后操作
6. 客服工作台 /service：三栏（会话列表 | 聊天窗口 | AI话术面板）
7. AI配置 /ai-config：占位页面

请搭建完整项目骨架，从目录结构开始...
```

---

## 快速启动（种子脚本后）

```
# 1. 安装依赖
cd backend && pip install -r requirements.txt

# 2. 初始化种子数据
python seed.py
# 输出: 种子数据生成成功！请使用 admin/123456 登录

# 3. 启动后端
uvicorn app.main:app --reload --port 8010

# 4. 启动前端
cd frontend && npm install && npm run dev -- --port 8080

# 5. 浏览器打开 http://localhost:8080
# 登录 admin/123456 → 所有页面有 Mock 数据 → AI 话术可正常演示
```
