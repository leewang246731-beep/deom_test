# 客服工作台智能协同模式 — 深度改造方案

> 基于现有 SaaS 客服工作台 (Service.vue) + AI Pipeline + 工单系统，
> 扩展为**三模式切换**（纯人工 / 人机协同 / 智能体全自动）+ **角色分工**（售前/售中/售后）+ **兜底机制**。

---

## 一、当前系统完成度评估

### 已具备的能力

| 能力 | 现状 | 复用度 |
|------|------|:---:|
| AI 话术生成 | `/ai/suggest` 完整 Pipeline (向量检索+RRF+LLM) | 100% |
| 物流感知话术 | Prompt 注入物流状态，物流异常自动生成安抚话术 | 100% |
| WebSocket 实时通道 | `/ws/service` 鉴权+ping+ai_suggest | 90% |
| 会话列表+详情 | conversations REST + messages_json | 100% |
| 工单系统 | tickets CRUD + 状态机 + AI分类/总结 | 100% |
| 技能组 | skill_groups + members + 智能分配 | 100% |
| 采纳记录 | ai_suggestion_logs (was_adopted 0/1/2) | 100% |
| 商品推荐 | recommendations/similar (三路融合) | 80% |
| 角色体系 | admin/manager/service 三级权限 | 70%（需扩展为售前/售中/售后）|

### 需要新建/改造的

| 模块 | 工作量 | 说明 |
|------|:---:|------|
| 客服角色细分（售前/售中/售后） | 小 | merchant_users.role 扩展 或 skill_tags 复用 |
| 三模式切换引擎 | 中 | 新增 service_mode 配置 + 模式状态机 |
| 智能体全自动回复 | 中 | 自动调 AI→自动发送→自动记录，无人值守 |
| 人机协同（AI 草稿→人工确认） | 小 | 在现有 AI suggest 基础上加"自动填入输入框" |
| 兜底机制（LLM 不确定→转人工→超时→兜底话术） | 中 | 新增 confidence 阈值 + 超时定时器 + 兜底模板 |
| 前端 Service.vue 模式切换 UI | 中 | 顶部 Tab/开关 + 模式指示器 + 自动回复日志 |

---

## 二、三模式定义

### 2.1 模式一：纯人工

```
买家消息 → 推送给客服 → 客服手动回复
AI 不介入（右侧面板隐藏或仅展示历史话术参考）
```

**适用场景：** 高客单价 VIP 客户、复杂投诉、敏感问题
**前端表现：** 右侧 AI 面板折叠/隐藏，输入框无自动填充

### 2.2 模式二：人机协同（推荐默认）

```
买家消息 → AI 自动生成 3 条建议 → 客服审阅 → 点击"发送"或编辑后发送
AI 辅助但不自主发送
```

**适用场景：** 日常客服工作，大部分会话
**前端表现：**
- 买家新消息到达时，AI 自动生成建议（无需手动点按钮）
- 建议直接展示在输入框上方（inline suggestion）
- 客服点击"采纳发送" / "编辑后发送" / "忽略"
- 采纳率自动记录

### 2.3 模式三：智能体全自动

```
买家消息 → AI 生成回复 → 判断 confidence
  ├─ confidence >= 0.8 → 自动发送 → 记录日志
  ├─ confidence < 0.8 且 < 0.5 → 转人工（挂起等待）
  └─ confidence >= 0.5 且 < 0.8 → 发送兜底话术 + 标记待复核
```

**适用场景：** 非工作时间值守、高频重复问题（尺码/快递/退货政策）
**前端表现：**
- 会话列表显示"🤖"图标标记全自动会话
- 自动回复消息带"[AI]"前缀
- 客服可随时接管（切换为人机协同）

---

## 三、客服角色细分

### 3.1 角色扩展方案

**方案：复用 skill_groups 而非新增 role 枚举**

| 角色 | 实现方式 | 典型场景 |
|------|---------|---------|
| 售前客服 | skill_group "售前咨询组" + skill_tags "商品咨询,价格谈判" | 商品详情咨询、优惠活动、推荐搭配 |
| 售中客服 | skill_group "售中服务组" + skill_tags "物流查询,催发货" | 物流追踪、催发货、修改地址 |
| 售后客服 | skill_group "售后处理组" + skill_tags "退换货,投诉处理" | 退货退款、质量投诉、赔偿方案 |

**AI 行为差异：**

| 角色 | AI Prompt 侧重 | 自动回复 confidence 阈值 |
|------|---------------|:---:|
| 售前 | 产品推荐+促单+价格优势 | 0.85 |
| 售中 | 物流信息+时效承诺+安抚 | 0.80 |
| 售后 | 流程引导+方案提供+补偿权限 | 0.70（更谨慎） |

### 3.2 会话智能路由（扩展现有技能组分配）

```
新会话到达 → 分析买家意图（LLM 意图分类）
  ├─ "这个多少钱" / "有优惠吗" → 售前组
  ├─ "快递到哪了" / "什么时候发货" → 售中组
  └─ "要退货" / "质量问题" / "投诉" → 售后组

售后组内分配：技能匹配 → 负载均衡 → 兜底给主管
```

---

## 四、兜底机制设计

### 4.1 三级兜底链路

```
Level 1: AI 自动回复（confidence >= threshold）
    ↓ 失败（confidence < 0.5 或 LLM 异常）
Level 2: 转人工（推送给匹配的客服，等待接管）
    ↓ 超时（人工 N 分钟未响应）
Level 3: 兜底话术（预设模板，安抚买家 + 承诺回复时间）
    ↓ 继续超时
Level 4: 升级工单（自动创建 P1 工单 + 通知管理员）
```

### 4.2 配置化参数

```sql
CREATE TABLE service_mode_configs (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    merchant_id     BIGINT NOT NULL,
    -- 模式开关
    default_mode    VARCHAR(20) DEFAULT 'copilot',     -- manual / copilot / auto
    auto_mode_hours VARCHAR(100) DEFAULT '22:00-08:00', -- 自动模式时段（非工作时间）
    -- 阈值
    auto_confidence_threshold DECIMAL(3,2) DEFAULT 0.80, -- 自动发送阈值
    fallback_confidence_threshold DECIMAL(3,2) DEFAULT 0.50, -- 低于此值转人工
    -- 超时
    human_response_timeout_seconds INT DEFAULT 180,    -- 人工响应超时（秒）
    fallback_escalate_timeout_seconds INT DEFAULT 600, -- 兜底后升级工单超时
    -- 兜底话术
    fallback_template TEXT DEFAULT '亲，客服正在为您查询中，请稍等片刻，我们会尽快回复您~',
    busy_template TEXT DEFAULT '当前咨询较多，已为您排队，预计{wait_minutes}分钟内有客服为您服务',
    offline_template TEXT DEFAULT '当前为非工作时间，您的问题已记录，工作时间将第一时间回复您~',
    FOREIGN KEY (merchant_id) REFERENCES merchants(id)
);
```

### 4.3 超时处理流程

```
买家发送消息
    │
    ▼
当前模式判断：
    ├─ manual → 推送给客服，不做任何自动操作
    │
    ├─ copilot → AI 生成建议推送给客服
    │              └─ 启动人工响应计时器 (180s)
    │              └─ 超时未回复 → 自动发送兜底话术 + 标记"待处理"
    │
    └─ auto → AI 生成回复
                ├─ confidence >= 0.8 → 自动发送
                ├─ 0.5 <= conf < 0.8 → 发兜底话术 + 转人工
                └─ conf < 0.5 → 直接转人工 + 启动超时器
                         └─ 人工 180s 未响应 → 发兜底话术
                         └─ 继续 600s 未响应 → 创建 P1 工单
```

---

## 五、数据模型新增

### 5.1 模式配置表

```sql
CREATE TABLE service_mode_configs (
    id                              INT PRIMARY KEY AUTO_INCREMENT,
    merchant_id                     BIGINT NOT NULL,
    default_mode                    VARCHAR(20) DEFAULT 'copilot',
    auto_mode_hours                 VARCHAR(100) DEFAULT '22:00-08:00',
    auto_confidence_threshold       DECIMAL(3,2) DEFAULT 0.80,
    fallback_confidence_threshold   DECIMAL(3,2) DEFAULT 0.50,
    human_response_timeout_seconds  INT DEFAULT 180,
    fallback_escalate_timeout_seconds INT DEFAULT 600,
    fallback_template               TEXT,
    busy_template                   TEXT,
    offline_template                TEXT,
    created_at                      DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at                      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (merchant_id) REFERENCES merchants(id)
);
```

### 5.2 自动回复日志表

```sql
CREATE TABLE auto_reply_logs (
    id                  BIGINT PRIMARY KEY AUTO_INCREMENT,
    conversation_id     BIGINT NOT NULL,
    merchant_id         BIGINT NOT NULL,
    mode                VARCHAR(20) NOT NULL,          -- copilot / auto
    buyer_question      TEXT NOT NULL,
    ai_reply            TEXT NOT NULL,
    confidence          DECIMAL(3,2),
    action_taken        VARCHAR(30) NOT NULL,          -- auto_sent / fallback_sent / transferred / escalated
    human_override      TINYINT DEFAULT 0,             -- 1=人工后续覆盖了AI回复
    response_time_ms    INT,                           -- AI 响应耗时
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id),
    INDEX idx_merchant_time (merchant_id, created_at)
);
```

### 5.3 会话模式状态（扩展 conversations 表）

```sql
ALTER TABLE conversations ADD COLUMN current_mode VARCHAR(20) DEFAULT NULL COMMENT '当前会话模式 manual/copilot/auto';
ALTER TABLE conversations ADD COLUMN auto_reply_count INT DEFAULT 0 COMMENT '本会话AI自动回复次数';
ALTER TABLE conversations ADD COLUMN last_human_at DATETIME DEFAULT NULL COMMENT '最后一次人工回复时间';
ALTER TABLE conversations ADD COLUMN pending_timeout_at DATETIME DEFAULT NULL COMMENT '超时触发时间点';
```

---

## 六、API 新增/改造

### 6.1 新增接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/service-mode/config` | 获取当前商户模式配置 |
| PUT | `/api/v1/service-mode/config` | 更新模式配置（阈值/超时/话术模板） |
| POST | `/api/v1/conversations/{id}/mode` | 切换单个会话模式 `{mode: "manual"/"copilot"/"auto"}` |
| POST | `/api/v1/conversations/{id}/takeover` | 人工接管（从 auto 切为 copilot） |
| GET | `/api/v1/auto-reply-logs` | 自动回复日志（管理员审计用） |
| GET | `/api/v1/dashboard/auto-reply-stats` | 自动回复统计（自动率/转人工率/兜底率） |

### 6.2 现有接口改造

| 接口 | 改造 |
|------|------|
| `POST /ai/suggest` | 返回增加 `confidence` 字段（0-1），用于前端/自动模式判断 |
| `WS /ws/service` | 新增推送类型: `auto_reply`（AI自动回复通知）、`timeout_warning`（即将超时）、`mode_changed` |
| `GET /conversations` | 返回增加 `current_mode`、`auto_reply_count` 字段 |
| `GET /dashboard/service-stats` | 新增 `auto_reply_rate`、`transfer_rate`、`avg_auto_response_ms` |

---

## 七、AI Pipeline 改造

### 7.1 Confidence 评分

在 `ai_suggest.py` 的 `get_ai_suggestions()` 中增加置信度计算：

```python
def _calc_confidence(fused: list, llm_response: str, buyer_question: str) -> float:
    """计算 AI 回复的置信度（0-1）。"""
    score = 0.5  # base

    # 检索命中质量
    if fused:
        top_rrf = fused[0]["rrf"]
        if top_rrf > 0.02: score += 0.15  # 强匹配
        if top_rrf > 0.03: score += 0.10

    # 回复长度合理性
    if 20 < len(llm_response) < 300: score += 0.05

    # 是否包含具体信息（非泛泛而谈）
    specifics = ["¥", "元", "码", "天", "小时", "快递", "已", "可以"]
    if any(s in llm_response for s in specifics): score += 0.10

    # 问题类型匹配度（简单问题更自信）
    simple_patterns = ["有货", "多少钱", "几天到", "什么快递", "支持"]
    if any(p in buyer_question for p in simple_patterns): score += 0.10

    return min(score, 0.99)
```

### 7.2 角色感知 Prompt

```python
ROLE_PROMPTS = {
    "pre_sale": """你是售前客服助手。重点：
- 突出商品卖点和优势
- 适当推荐搭配商品
- 制造紧迫感促成下单
- 回答价格/优惠/规格问题""",

    "in_sale": """你是售中客服助手。重点：
- 提供准确的物流信息
- 安抚等待焦虑
- 处理地址修改/加急请求
- 引用具体的快递状态""",

    "after_sale": """你是售后客服助手。重点：
- 表达歉意和理解
- 提供明确的解决方案（退/换/补）
- 说明流程和时效
- 适当提供补偿方案（优惠券/红包）
- 态度温和但不过度承诺""",
}
```

---

## 八、前端改造 (Service.vue)

### 8.1 顶部模式切换

```
┌─────────────────────────────────────────────────────────────┐
│ 客服工作台     [纯人工 ○] [人机协同 ●] [智能体自动 ○]  全局模式 │
│                                         当前角色：售中客服    │
├─────────────────────────────────────────────────────────────┤
│ 会话列表 │ 聊天窗口 │ AI 面板                                │
│          │          │                                        │
│ ○ 张三 🤖│          │ [模式: 人机协同]                        │
│ ● 李四   │          │ ┌──────────────┐                      │
│ ○ 王五 ⏰│          │ │ AI 建议 (0.92)│                      │
│          │          │ │ 亲，您的...   │                      │
│          │          │ │ [采纳] [编辑] │                      │
│          │          │ └──────────────┘                      │
└─────────────────────────────────────────────────────────────┘

图标说明：
🤖 = 该会话当前为全自动模式
⏰ = 该会话等待人工响应中（即将超时）
🔴 = 该会话已超时，需要立即处理
```

### 8.2 人机协同模式 UI

```
┌──────────────────────────────────────────────────┐
│ 聊天窗口                                          │
│                                                    │
│ [买家] 这个快递到哪了？                           │
│                                                    │
│ ┌─ AI 建议 ──────────────────────────────┐       │
│ │ 🤖 置信度: 92%                          │       │
│ │ 亲，您的包裹已到达杭州中转站，         │       │
│ │ 预计明天送达，请保持电话畅通~           │       │
│ │                                         │       │
│ │ [✅ 采纳发送] [✏️ 编辑后发送] [❌ 忽略]  │       │
│ └─────────────────────────────────────────┘       │
│                                                    │
│ [输入框...                          ] [发送]      │
└──────────────────────────────────────────────────┘
```

### 8.3 全自动模式 UI

```
┌──────────────────────────────────────────────────┐
│ 聊天窗口  [🤖 自动模式运行中] [接管为人工▶]       │
│                                                    │
│ [买家] 几天能到？                                 │
│ [AI🤖] 预计2-3天送达哦~（置信度:0.95,已自动发送）│
│                                                    │
│ [买家] 可以快一点吗                               │
│ [AI🤖] 已帮您备注加急，优先发出~（0.88）         │
│                                                    │
│ [买家] 我要退货（置信度仅0.42→已转人工）         │
│ [系统] ⚠️ AI 无法确认处理，已转人工客服           │
│                                                    │
│ [输入框 — 自动模式下灰显]           [接管] [设置]  │
└──────────────────────────────────────────────────┘
```

---

## 九、WebSocket 协议扩展

### 9.1 服务端推送新消息类型

```json
// AI 自动回复通知
{"type": "auto_reply", "conversation_id": 123, "content": "亲...", "confidence": 0.92}

// 超时预警
{"type": "timeout_warning", "conversation_id": 123, "seconds_left": 30, "level": "warning"}

// 超时触发
{"type": "timeout_triggered", "conversation_id": 123, "action": "fallback_sent", "fallback_content": "亲..."}

// 模式变更
{"type": "mode_changed", "conversation_id": 123, "from": "auto", "to": "copilot", "reason": "low_confidence"}

// 转人工
{"type": "transfer_to_human", "conversation_id": 123, "reason": "confidence_too_low", "buyer_question": "..."}
```

### 9.2 客户端发送新指令

```json
// 切换会话模式
{"type": "set_mode", "conversation_id": 123, "mode": "manual"}

// 人工接管
{"type": "takeover", "conversation_id": 123}

// 确认/拒绝 AI 建议
{"type": "ai_decision", "conversation_id": 123, "suggestion_id": 1, "action": "accept"/"reject"/"edit", "edited_content": "..."}
```

---

## 十、后台定时任务

### 10.1 超时检测器（asyncio，每 10 秒）

```python
async def timeout_checker():
    """扫描等待人工响应的会话，触发超时兜底。"""
    while True:
        await asyncio.sleep(10)
        db = SessionLocal()
        try:
            config = get_service_mode_config(db, merchant_id=1)
            timeout_secs = config.human_response_timeout_seconds

            # 查找超时会话
            pending = db.query(Conversation).filter(
                Conversation.handled_status == "pending",
                Conversation.pending_timeout_at != None,
                Conversation.pending_timeout_at < datetime.now(),
            ).all()

            for conv in pending:
                # 发送兜底话术
                send_fallback(db, conv, config.fallback_template)
                # 记录日志
                log_auto_reply(db, conv, "fallback_sent", config.fallback_template, confidence=0)
                # 清除超时标记
                conv.pending_timeout_at = None

            # 长时间无响应 → 升级工单
            escalate_timeout = config.fallback_escalate_timeout_seconds
            stuck = db.query(Conversation).filter(
                Conversation.handled_status == "pending",
                Conversation.last_message_at < datetime.now() - timedelta(seconds=escalate_timeout),
            ).all()
            for conv in stuck:
                create_ticket_from_conv(db, conv, priority="P1", reason="客服超时未响应")

            db.commit()
        finally:
            db.close()
```

---

## 十一、实施步骤（8 步，约 5 天）

| 步骤 | 内容 | 工期 | 验证 |
|------|------|:---:|------|
| 1 | 数据模型：service_mode_configs + auto_reply_logs + conversations 扩展字段 | 0.5天 | 表建成 |
| 2 | AI confidence 评分 + 角色感知 Prompt | 0.5天 | suggest 返回 confidence 字段 |
| 3 | 模式引擎服务 (mode_engine.py): 判断模式→执行对应逻辑→记录日志 | 1天 | 单元测试通过 |
| 4 | 兜底机制：超时检测器 + 兜底话术发送 + 升级工单 | 1天 | 模拟超时→自动发兜底 |
| 5 | API：模式配置 CRUD + 会话模式切换 + 接管 + 日志查询 | 0.5天 | curl 全部通过 |
| 6 | WebSocket 扩展：auto_reply/timeout_warning/mode_changed 推送 | 0.5天 | WS 接收正确消息 |
| 7 | 前端 Service.vue 改造：模式切换 UI + inline suggestion + 自动回复标记 | 1天 | 三种模式可切换 |
| 8 | 看板统计 + 联调 | 0.5天 | 自动回复率/转人工率/平均响应时间可查 |

---

## 十二、与现有系统的融合点

| 现有模块 | 融合方式 |
|----------|---------|
| `ai_suggest.py` | 增加 confidence 返回 + 角色 Prompt 注入 |
| `conversations.py` WS | 扩展消息类型 (auto_reply/timeout) |
| `skill_groups` | 复用技能组做售前/售中/售后路由 |
| `ticket_ai.py` | 超时升级时调用 `create_ticket()` |
| `ai_suggestion_logs` | 自动回复也写入此表（was_adopted=3 表示 auto_sent） |
| `service_mode_configs` | 种子数据预设默认配置 |

---

## 十三、KPI 指标（看板展示）

| 指标 | 计算方式 | 目标 |
|------|---------|:---:|
| AI 自动解决率 | auto_sent 且未转人工 / 总会话 | > 60% |
| 平均首响时间 | 买家消息→第一条回复（含AI）的间隔 | < 5s (auto) / < 60s (copilot) |
| 人工接管率 | 转人工次数 / AI 处理总次数 | < 30% |
| 兜底触发率 | fallback_sent / 总会话 | < 10% |
| 工单升级率 | 超时创建工单 / 总会话 | < 2% |
| 客服采纳率 | (accepted + edited) / total suggestions | > 75% |

---

## 十四、演示场景（验证脚本）

```
场景1：智能体全自动
  买家: "这个有M码吗" → AI(0.95) → 自动发送"亲，有M码的哦~"
  买家: "发什么快递" → AI(0.88) → 自动发送"默认发中通~"
  买家: "我要投诉你们" → AI(0.35) → 转人工 → 客服3分钟未响应 → 兜底话术
  → 继续10分钟 → 自动创建P1工单

场景2：人机协同
  买家: "快递丢了怎么办" → AI生成3条建议(0.72) → 客服看到inline suggestion
  → 客服编辑后发送 → 记录 was_adopted=2 + confidence=0.72

场景3：售前→售后流转
  买家: "这个颜色怎么选" → 售前客服(AI推荐) → 买家下单
  → 买家: "收到了有划痕" → AI意图识别"售后" → 自动转售后组
  → 售后客服看到完整上下文 + AI建议退换方案
```
