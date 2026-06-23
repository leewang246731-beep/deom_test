# Agent 编排设计 · 智能电商全链路平台（增强版）

> 融合成熟客服智能体的 **话术风格/自动素材/销冠复制/场景策略/全自动发送** 等能力

---

## 一、Agent 架构总览（6 子Agent + 1 Master）

```
                    ┌──────────────────┐
                    │   User / 客服输入  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Master Agent    │
                    │  · 意图识别(8→12类)│
                    │  · 场景策略匹配   │  ← 新增
                    │  · 自动模式判断   │  ← 新增 (auto/manual/assist)
                    │  · 风格路由       │  ← 新增
                    └──┬───┬───┬───┬───┘
          ┌────────────┘   │   │   └──────────────┐
          ▼                ▼   ▼                  ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │ 客服 Agent    │ │ 推荐 Agent    │ │ 订单 Agent    │
   │ · RAG知识问答 │ │ · 协同过滤   │ │ · 下单引导   │
   │ · 风格定制   │+│ · 卖点提炼   │+│ · 物流追踪   │
   │ · 素材图自动 │+│ · 尺码推荐   │+│ · 催单催付   │+
   │ · 商品对比   │+│ · 搭配推荐   │ │ · 退款引导   │
   │ · 话术采纳   │+│ · 比价分析   │ │              │
   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
          │                │                │
   ┌──────▼───────┐ ┌──────▼───────┐ ┌──────▼───────┐
   │ 营销 Agent    │ │ 工单 Agent    │ │ 学习 Agent    │ ← 新增
   │ · 活动匹配   │ │ · 工单分配   │ │ · 销冠话术提炼│
   │ · 优惠推荐   │ │ · 流转处理   │ │ · 知识库更新  │
   │ · 催付话术   │+│ · 满意度采集 │ │ · 错误修正    │
   │ · 消息推送   │+│ · SLA监控    │ │ · 风格微调    │
   └──────────────┘ └──────────────┘ └──────────────┘

共享基础设施：
┌────────────────────────────────────────────────────────────┐
│  场景策略引擎 │ 话术模板库 │ 素材图库 │ 风格配置 │ 聊天提炼管道 │
└────────────────────────────────────────────────────────────┘
```

---

## 二、三种运行模式

| 模式 | 触发 | 行为 |
|------|------|------|
| **全自动 (auto)** | 开启全自动 + 不在排除场景 | Agent 3秒自动生成并发送，无需人工确认 |
| **人工辅助 (assist)** | 默认 / 客服在线 | Agent 生成参考话术，客服点"采纳"才发送 |
| **学习修正 (learn)** | 客服修改话术后 | 系统记录差异，喂入学习Agent优化后续话术 |

**排除场景（全自动模式下不触发）：**
- 退款/退货请求
- 用户表达强烈负面情绪（投诉类）
- 优惠价格咨询（需人工确认）
- 法律/合规相关问询

---

## 三、意图分类体系（8 类 → 12 类）

| 意图 | 路由 | 示例 |
|------|:--:|------|
| `product_inquiry` | 客服 | "这面料是什么材质？" |
| `product_recommend` | 推荐 | "帮我推荐一款适合我的" |
| `product_compare` | 客服 | "这两款有什么区别？" ← 新增 |
| `size_recommend` | 推荐 | "我180cm穿什么尺码？" ← 新增 |
| `order_query` | 订单 | "我的订单到哪了？" |
| `purchase_intent` | 订单 | "帮我下单" |
| `payment_reminder` | 订单 | "还没付款，催一下" ← 新增 |
| `after_sales` | 客服→工单 | "我要退货" |
| `complaint` | 工单 | "你们太差了！" ← 新增 |
| `price_compare` | 营销 | "和那家比哪个划算？" |
| `promotion_inquiry` | 营销 | "有什么优惠？" |
| `chitchat` | 客服 | "你好" |

---

## 四、Master Agent（增强版）

```python
class MasterAgent:
    """主控 Agent：路由 + 场景策略 + 模式切换 + 风格路由"""
    
    def __init__(self):
        self.intent_classifier = IntentClassifier()     # 12类
        self.strategy_engine = StrategyEngine()          # 新增：场景策略
        self.auto_mode_judge = AutoModeJudge()          # 新增：自动模式判断
        self.style_router = StyleRouter()               # 新增：风格路由
        self.context_store = RedisContextStore()
        
    async def route(self, user_input: str, user_id: int, 
                    session_id: str, mode: str = "assist") -> AgentResponse:
        context = await self._aggregate_context(user_id, session_id)
        
        # 1. 意图 + 场景联合识别
        intent = await self.intent_classifier.classify(user_input, context)
        scene = await self.strategy_engine.match(user_input, intent, context)
        
        # 2. 自动模式判断（是否全自动发送）
        can_auto = False
        if mode == "auto":
            can_auto = await self.auto_mode_judge.should_auto(
                intent, scene, user_input, context
            )
        
        # 3. 风格路由
        style = await self.style_router.resolve(intent, scene, user_id)
        
        # 4. Agent 路由
        agent = self._select_agent(intent)
        
        # 5. 注入风格到子Agent
        result = await agent.execute(
            user_input, context, 
            style=style, 
            auto_send=can_auto
        )
        
        # 6. 场景策略后处理
        enriched = await self.strategy_engine.post_process(
            scene, intent, result, context
        )
        
        # 7. 外部工具调度
        if scene.tools:
            await self._dispatch_external_tools(scene.tools, enriched)
        
        await self.context_store.update(session_id, {
            "last_intent": intent,
            "last_scene": scene.name,
            "last_agent": agent.name,
            "auto_sent": can_auto,
        })
        
        return enriched

    def _select_agent(self, intent: str) -> BaseAgent:
        return {
            "product_inquiry":    self.cs_agent,
            "product_recommend":  self.reco_agent,
            "product_compare":    self.cs_agent,
            "size_recommend":     self.reco_agent,
            "order_query":        self.order_agent,
            "purchase_intent":    self.order_agent,
            "payment_reminder":   self.order_agent,
            "after_sales":        self.cs_agent,
            "complaint":          self.ticket_agent,
            "price_compare":      self.marketing_agent,
            "promotion_inquiry":  self.marketing_agent,
            "chitchat":           self.cs_agent,
        }.get(intent, self.cs_agent)
```

---

## 五、子 Agent 定义（增强版）

### 5.1 客服 Agent（能力大幅增强）

```python
class CustomerServiceAgent(BaseAgent):
    tools = [
        "rag_search",           # ChromaDB 知识库检索
        "product_lookup",       # 查商品详情
        "compare_products",     # 多商品对比 ← 新增
        "send_material_image",  # 自动发送素材图 ← 新增
        "order_lookup",         # 查用户订单
        "create_ticket",        # 创建工单
        "transfer_human",       # 转人工
        "recommend_product",    # 调用推荐Agent
    ]
    
    system_prompt = """
    你是一个{style_name}的电商客服助手。当前场景：{scene}。
    
    核心能力：
    1. 基于商品知识库精准回答产品问题
    2. 用户提到多个商品时主动对比差异（材质/尺寸/价格/适用场景）
    3. 自动匹配并发送相关素材图（不等待用户索要）
    4. 识别用户情绪，不满时主动道歉+创建工单
    5. 回答后附带相关商品推荐
    6. 无法回答时诚实说不知道并转人工
    
    话术要求：
    {style_rules}
    """
```

### 5.2 推荐 Agent（卖点+尺码+搭配）

```python
class RecommendationAgent(BaseAgent):
    tools = [
        "collaborative_filter",   # 协同过滤
        "vector_search",          # 语义检索
        "extract_selling_points", # 商品卖点提炼 ← 新增
        "size_recommend",         # 尺码推荐 ← 新增（含尺寸表学习）
        "match_outfit",           # 搭配推荐 ← 新增
        "user_profile_boost",     # 画像加权
        "hot_ranking",            # 热门排行
        "price_compare",          # 比价
    ]
```

### 5.3 订单 Agent（催单催付增强）

```python
class OrderAgent(BaseAgent):
    tools = [
        "query_order",
        "query_logistics",
        "create_order",
        "apply_coupon",
        "cancel_order",
        "send_payment_reminder",  # 催单催付 ← 新增
        "confirm_receipt",
    ]
```

### 5.4 营销 Agent（消息推送增强）

```python
class MarketingAgent(BaseAgent):
    tools = [
        "query_promotions",
        "query_coupons",
        "match_coupon",
        "price_compare",
        "send_notification",      # 钉钉/微信/飞书推送 ← 新增
    ]
```

### 5.5 工单 Agent（投诉处理独立）

```python
class TicketAgent(BaseAgent):
    tools = [
        "create_ticket",
        "assign_ticket",          # 智能分配
        "query_ticket",
        "update_ticket_status",
        "escalate",               # 紧急升级 ← 新增
    ]
```

### 5.6 学习 Agent（销冠复制 + 话术进化）← 全新

```python
class LearningAgent(BaseAgent):
    """
    离线 Agent，由 Celery 定时任务驱动，不参与实时对话。
    负责：话术提炼、知识库更新、错误修正、风格微调
    """
    
    def extract_top_seller_style(self, chat_logs: List[ChatLog]) -> dict:
        """从金牌客服聊天记录中提炼话术模式"""
        prompt = f"""
        分析以下金牌客服的聊天记录，提炼：
        1. 话术特点（语气/句式/常用词）
        2. 高频场景的回复模板
        3. 处理投诉的话术策略
        4. 促单转化的关键话术
        
        聊天记录：
        {self._format_logs(chat_logs)}
        """
        return await self.llm.ainvoke(prompt)
    
    def learn_from_correction(self, original: str, corrected: str, context: dict):
        """客服修改 AI 话术后，学习修正模式"""
        diff = self._analyze_diff(original, corrected)
        # 存入修正知识库
        self.kb.add_correction(original, corrected, context, diff)
        # 定期触发风格微调
        if self.kb.correction_count > 100:
            self.trigger_style_finetune()
```

---

## 六、场景策略引擎（新增）

```python
class StrategyEngine:
    """场景策略引擎：定义+匹配+执行"""
    
    # 预设场景策略（商家可自定义）
    strategies = {
        "pre_sale": {
            "triggers": ["产品咨询", "尺码咨询", "推荐请求"],
            "actions": ["send_material_image", "recommend_similar"],
            "auto_msg": "您好！这款{material}面料的{p_name}...",
        },
        "post_sale": {
            "triggers": ["退货", "换货", "质量问题"],
            "actions": ["create_ticket", "apologize"],
            "auto_send": False,  # 售后不自动
            "notify": ["dingtalk:客服主管"],
        },
        "complaint": {
            "triggers": ["差评", "投诉", "威胁"],
            "actions": ["escalate", "notify_manager"],
            "auto_send": False,
            "notify": ["dingtalk:客服主管", "feishu:店长"],
        },
        "payment_reminder": {
            "triggers": ["未付款", "加购未下单"],
            "actions": ["send_reminder", "attach_coupon"],
            "auto_msg": "{user_name}，您喜欢的{p_name}库存紧张...",
            "auto_send": True,
        },
    }
    
    def match(self, user_input, intent, context):
        """匹配场景策略"""
        # 规则匹配 + LLM 理解行业 Know-how
        ...
    
    def post_process(self, scene, intent, result, context):
        """策略后处理：追加消息/调度工具"""
        ...
```

---

## 七、话术风格系统（新增）

```python
class StyleRouter:
    """根据场景/角色/品牌配置路由到不同话术风格"""
    
    style_configs = {
        "professional": {
            "tone": "专业稳重",
            "greeting": "尊敬的客户，您好。",
            "features": ["使用敬语", "结构化回复", "附带政策依据"],
        },
        "warm": {
            "tone": "亲切温暖",
            "greeting": "亲，在的呢~",
            "features": ["使用表情", "口语化", "主动关怀"],
        },
        "expert": {
            "tone": "专业导购",
            "greeting": "您好！我是您的专属导购。",
            "features": ["数据支撑", "对比分析", "专业术语解释"],
        },
    }
    
    # 场景→风格映射（可自定义）
    scene_style_map = {
        "complaint": "professional",    # 投诉用专业风格
        "pre_sale": "expert",          # 售前用专家风格
        "chitchat": "warm",            # 闲聊用温暖风格
    }
    
    # 角色→风格映射
    role_style_map = {
        "sales_manager": "expert",
        "junior_cs": "warm",
        "senior_cs": "professional",
    }
```

---

## 八、新旧对比

| 维度 | 原设计 | 增强后 |
|------|--------|--------|
| 子 Agent 数 | 4 个 | **6 个**（+学习 +工单独立） |
| 意图分类 | 8 类 | **12 类** |
| 运行模式 | 仅实时对话 | **自动/辅助/学习 三模式** |
| 话术风格 | 固定 system_prompt | **可配置风格路由（场景+角色）** |
| 素材图 | 不支持 | **自动匹配发送** |
| 催单催付 | 不支持 | **千人千面 + 图片** |
| 销冠复制 | 不支持 | **聊天提炼 + 话术注入** |
| 采纳学习 | 不支持 | **修正反馈闭环** |
| 外部工具 | 不支持 | **钉钉/微信/飞书推送** |
| 场景策略 | 无 | **策略引擎（预设+可自定义）** |
| 技术栈 | LangGraph + LLM + Redis | **完全相同（零新增框架）** |
