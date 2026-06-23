# Agent 编排设计

---

## 一、架构总览

采用 **Master Agent + 6 子Agent** 架构，基于 LangGraph 实现有状态编排：

```
                    ┌──────────────────┐
                    │   User / 客服输入  │
                    └────────┬─────────┘
                             │
                    ┌────────▼─────────┐
                    │  Master Agent    │
                    │  · 意图识别(12类) │
                    │  · 场景策略匹配   │
                    │  · 自动模式判断   │  auto / assist / learn
                    │  · 风格路由       │
                    └──┬───┬───┬───┬───┘
          ┌────────────┘   │   │   └──────────────┐
          ▼                ▼   ▼                  ▼
   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
   │ 客服 Agent    │ │ 推荐 Agent    │ │ 订单 Agent    │
   │ · RAG知识问答 │ │ · 协同过滤   │ │ · 下单引导   │
   │ · 风格定制   │ │ · 卖点提炼   │ │ · 物流追踪   │
   │ · 素材图自动 │ │ · 尺码推荐   │ │ · 催单催付   │
   │ · 商品对比   │ │ · 搭配推荐   │ │ · 退款引导   │
   │ · 话术采纳   │ │ · 比价分析   │ │              │
   └──────┬───────┘ └──────┬───────┘ └──────┬───────┘
          │                │                │
   ┌──────▼───────┐ ┌──────▼───────┐ ┌──────▼───────┐
   │ 营销 Agent    │ │ 工单 Agent    │ │ 学习 Agent    │
   │ · 活动匹配   │ │ · 工单分配   │ │ · 销冠话术提炼│
   │ · 优惠推荐   │ │ · 流转处理   │ │ · 知识库更新  │
   │ · 催付话术   │ │ · 满意度采集 │ │ · 错误修正    │
   │ · 消息推送   │ │ · SLA监控    │ │ · 风格微调    │
   └──────────────┘ └──────────────┘ └──────────────┘

共享基础设施：
┌────────────────────────────────────────────────────────────┐
│  场景策略引擎 │ 话术模板库 │ 素材图库 │ 风格配置 │ 聊天提炼管道 │
└────────────────────────────────────────────────────────────┘
```

---

## 二、三种运行模式

| 模式 | 触发条件 | 行为 |
|------|---------|------|
| **全自动 (auto)** | 开启全自动 + 不在排除场景 | Agent 3秒自动生成并发送，无需人工确认 |
| **人工辅助 (assist)** | 默认 / 客服在线 | Agent 生成参考话术，客服点"采纳"才发送 |
| **学习修正 (learn)** | 客服修改话术后 | 系统记录差异，学习Agent优化后续话术 |

**自动模式排除场景：** 退款退货、强烈负面情绪、优惠价格咨询、法律合规问询

---

## 三、意图分类（12类）

| 意图 | 路由 | 示例 |
|------|:--:|------|
| `product_inquiry` | 客服 | "这面料是什么材质？" |
| `product_recommend` | 推荐 | "帮我推荐一款适合我的" |
| `product_compare` | 客服 | "这两款有什么区别？" |
| `size_recommend` | 推荐 | "我180cm穿什么尺码？" |
| `order_query` | 订单 | "我的订单到哪了？" |
| `purchase_intent` | 订单 | "帮我下单" |
| `payment_reminder` | 订单 | "还没付款，催一下" |
| `after_sales` | 客服→工单 | "我要退货" |
| `complaint` | 工单 | "你们太差了！" |
| `price_compare` | 营销 | "和那家比哪个划算？" |
| `promotion_inquiry` | 营销 | "有什么优惠？" |
| `chitchat` | 客服 | "你好" |

---

## 四、Master Agent

```python
class MasterAgent:
    
    def __init__(self):
        self.intent_classifier = IntentClassifier()     # 12类 BERT 分类器
        self.strategy_engine = StrategyEngine()          # 场景策略匹配
        self.auto_mode_judge = AutoModeJudge()          # 自动模式判断
        self.style_router = StyleRouter()               # 风格路由
        self.context_store = RedisContextStore()
        
    async def route(self, user_input: str, user_id: int, 
                    session_id: str, mode: str = "assist") -> AgentResponse:
        context = await self._aggregate_context(user_id, session_id)
        
        # 1. 意图 + 场景联合识别
        intent = await self.intent_classifier.classify(user_input, context)
        scene = await self.strategy_engine.match(user_input, intent, context)
        
        # 2. 自动模式判断
        can_auto = False
        if mode == "auto":
            can_auto = await self.auto_mode_judge.should_auto(
                intent, scene, user_input, context
            )
        
        # 3. 风格路由
        style = await self.style_router.resolve(intent, scene, user_id)
        
        # 4. Agent 路由
        agent = self._select_agent(intent)
        
        # 5. 子Agent执行
        result = await agent.execute(user_input, context, style=style, auto_send=can_auto)
        
        # 6. 场景策略后处理 + 外部工具调度
        enriched = await self.strategy_engine.post_process(scene, intent, result, context)
        if scene.tools:
            await self._dispatch_external_tools(scene.tools, enriched)
        
        await self.context_store.update(session_id, {
            "last_intent": intent, "last_scene": scene.name,
            "last_agent": agent.name, "auto_sent": can_auto,
        })
        return enriched
```

---

## 五、子 Agent 定义

### 5.1 客服 Agent

```python
class CustomerServiceAgent(BaseAgent):
    tools = [
        "rag_search",           # ChromaDB 知识库检索
        "product_lookup",       # 查商品详情
        "compare_products",     # 多商品对比
        "send_material_image",  # 自动发送素材图
        "order_lookup",         # 查用户订单
        "create_ticket",        # 创建工单
        "transfer_human",       # 转人工
        "recommend_product",    # 调用推荐Agent
    ]
    
    system_prompt = """
    你是一个{style_name}的电商客服助手。当前场景：{scene}。
    
    核心能力：
    1. 基于商品知识库精准回答产品问题
    2. 主动对比多商品差异（材质/尺寸/价格/适用场景）
    3. 自动匹配并发送相关素材图
    4. 识别用户情绪，不满时主动道歉+创建工单
    5. 回答后附带相关商品推荐
    6. 无法回答时诚实转人工
    
    话术要求：{style_rules}
    """
```

### 5.2 推荐 Agent

```python
class RecommendationAgent(BaseAgent):
    tools = [
        "collaborative_filter",   # 协同过滤
        "vector_search",          # ChromaDB 语义检索
        "extract_selling_points", # 商品卖点提炼
        "size_recommend",         # 尺码推荐（含尺寸表学习）
        "match_outfit",           # 搭配推荐
        "user_profile_boost",     # 画像加权
        "hot_ranking",            # 热门排行
        "price_compare",          # 比价
    ]
```

### 5.3 订单 Agent

```python
class OrderAgent(BaseAgent):
    tools = [
        "query_order", "query_logistics", "create_order",
        "apply_coupon", "cancel_order",
        "send_payment_reminder",  # 催单催付
        "confirm_receipt",
    ]
```

### 5.4 营销 Agent

```python
class MarketingAgent(BaseAgent):
    tools = [
        "query_promotions", "query_coupons", "match_coupon",
        "price_compare",
        "send_notification",      # 钉钉/微信/飞书推送
    ]
```

### 5.5 工单 Agent

```python
class TicketAgent(BaseAgent):
    tools = [
        "create_ticket", "assign_ticket",
        "query_ticket", "update_ticket_status",
        "escalate",               # 紧急升级
    ]
```

### 5.6 学习 Agent（离线）

```python
class LearningAgent(BaseAgent):
    """Celery定时任务驱动，不参与实时对话"""
    
    def extract_top_seller_style(self, chat_logs):
        """从金牌客服聊天记录提炼话术模式"""
        prompt = f"""
        分析金牌客服聊天记录，提炼：话术特点、高频场景模板、
        投诉处理策略、促单关键话术。记录：{self._format_logs(chat_logs)}
        """
        return await self.llm.ainvoke(prompt)
    
    def learn_from_correction(self, original, corrected, context):
        """客服修改AI话术后学习修正模式"""
        self.kb.add_correction(original, corrected, context)
        if self.kb.correction_count > 100:
            self.trigger_style_finetune()
```

---

## 六、场景策略引擎

```python
class StrategyEngine:
    strategies = {
        "pre_sale": {
            "triggers": ["产品咨询", "尺码咨询", "推荐请求"],
            "actions": ["send_material_image", "recommend_similar"],
        },
        "post_sale": {
            "triggers": ["退货", "换货", "质量问题"],
            "actions": ["create_ticket", "apologize"],
            "auto_send": False,
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
            "auto_send": True,
        },
    }
```

---

## 七、话术风格系统

```python
class StyleRouter:
    style_configs = {
        "professional": {
            "tone": "专业稳重", "greeting": "尊敬的客户，您好。",
            "features": ["使用敬语", "结构化回复", "附带政策依据"],
        },
        "warm": {
            "tone": "亲切温暖", "greeting": "亲，在的呢~",
            "features": ["使用表情", "口语化", "主动关怀"],
        },
        "expert": {
            "tone": "专业导购", "greeting": "您好！我是您的专属导购。",
            "features": ["数据支撑", "对比分析", "专业术语解释"],
        },
    }
    
    scene_style_map = {
        "complaint": "professional", "pre_sale": "expert", "chitchat": "warm",
    }
```

---

## 八、Agent 间协同

| 场景 | Agent 协作链 |
|------|-------------|
| 用户问"有什么好手机？" | 推荐Agent → 展示商品 → 附带"需要比价吗？" |
| 用户问"这个续航怎么样？" | 客服Agent → RAG查知识库 → 附加"加入购物车？" |
| 用户说"我要退货" | 订单Agent查订单 → 客服Agent创建工单 |
| 营销推送"618大促" | 营销Agent匹配活动 → 推荐Agent筛选活动商品 → 推送 |
| 客服发现某商品投诉激增 | 客服标记 → 推荐系统降权 → 通知运营 |

---

## 九、工具定义

```python
TOOLS = [
    {"name": "rag_search",         "desc": "知识库搜索"},
    {"name": "vector_search_products", "desc": "语义搜索商品"},
    {"name": "collaborative_filter",   "desc": "协同过滤推荐"},
    {"name": "create_ticket",      "desc": "创建售后工单"},
    {"name": "query_promotions",   "desc": "查询营销活动"},
    {"name": "match_coupon",       "desc": "匹配最优优惠券"},
    {"name": "send_material_image", "desc": "发送商品素材图"},
    {"name": "compare_products",   "desc": "多商品对比"},
    {"name": "send_payment_reminder", "desc": "催单催付"},
    {"name": "size_recommend",     "desc": "尺码推荐"},
    {"name": "send_notification",  "desc": "钉钉/微信/飞书推送"},
]
```

---

## 十、LangGraph 编排

```python
from langgraph.graph import StateGraph, END

class AgentState(TypedDict):
    messages: List[Message]
    intent: str
    current_agent: str
    context: dict

workflow = StateGraph(AgentState)
# Nodes: intent_classifier → agent_router → {cs, reco, order, marketing, ticket} → response_builder
workflow.add_node("intent_classifier", intent_classifier)
workflow.add_node("agent_router", agent_router)
for name in ["customer_service", "recommendation", "order_agent", "marketing", "ticket"]:
    workflow.add_node(name, globals()[name])
workflow.add_node("response_builder", response_builder)
workflow.set_entry_point("intent_classifier")
workflow.add_edge("intent_classifier", "agent_router")
workflow.add_conditional_edges("agent_router", route_agent, {
    "cs": "customer_service", "reco": "recommendation",
    "order": "order_agent", "marketing": "marketing", "ticket": "ticket",
})
for node in ["customer_service", "recommendation", "order_agent", "marketing", "ticket"]:
    workflow.add_edge(node, "response_builder")
workflow.add_edge("response_builder", END)

agent_graph = workflow.compile()
```

---

## 十一、评估指标

| 指标 | 目标 | 测量方式 |
|------|:---:|------|
| 意图识别准确率 | > 90% | 标注数据集 |
| Agent 路由准确率 | > 95% | 人工抽检 |
| 客服回答正确率 | > 85% | RAGAS faithfulness |
| 推荐点击率 | > 15% | 埋点统计 |
| 推荐转化率 | > 5% | 订单关联 |
| 对话完成率 | > 80% | 无需转人工比例 |
| 平均响应时间 | < 2s | 系统监控 |
