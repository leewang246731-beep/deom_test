# Agent 系统五维审计与优化方案

> 审计范围：`backend/app/ai/` 全部文件。当前架构：LangGraph Supervisor-Worker 多智能体 + 传统单 ReAct Agent。

## 评分卡

| 维度 | 当前等级 | 评分 | 核心缺陷 |
|---|---|---|---|
| Function Calling | 中等 | 6/10 | 工具链完整但硬编码+物流mock |
| Multi-step Reasoning | 基础 | 4/10 | 有ReAct但无显式CoT+无迭代循环 |
| Memory | 薄弱 | 2/10 | 短期记忆透传不持久+长期记忆缺失 |
| Autonomous Planning | 基础 | 3/10 | 单层路由非真规划+无重规划 |
| Tools | 中等 | 5/10 | 5工具1mock+缺发货/消息/工单CRUD |

---

## 1. Function Calling（6/10）

### 现状

```
tools.py:        5个 @tool (兼容路径)
OrderAgent:      2个 @tool (query_order, process_refund)
LogisticsAgent:  2个 @tool (check_logistics, get_delivery_estimate)
ProductAgent:    2个 @tool (search_product, check_inventory)
TicketAgent:     1个 @tool (search_ticket_history)
RAGAgent:        0个 tool (纯检索)
ReplyAgent:      0个 tool (纯合成)
```

- Function Calling 通过 LangChain `@tool` + LangGraph `create_react_agent` 实现
- LLM 自主决定调用哪个工具，参数由 LLM 从自然语言中推断
- 工具描述清晰，LLM 能正确路由

### 缺陷

1. **硬编码工具列表**：每个 Agent 的工具在 `_build_tools` 中静态定义，无法运行时动态注册/发现工具
2. **工具间无共享**：`tools.py` 和 `OrderAgent` 各自定义 `query_order`，代码重复
3. **物流工具仍 mock**：`LogisticsAgent.check_logistics` 尝试调 vmall connector 但有 async bug（`connector.get_logistics()` 未 await），降级到 random 假数据
4. **无工具调用校验**：LLM 生成的参数直接传给工具，无 schema 校验层
5. **缺少工具输出后处理**：observation 原样返回给 LLM，无格式化/截断/置信度标注

### 优化方案

| 优先级 | 措施 | 工作量 |
|---|---|---|
| P0 | 统一工具注册中心 `ToolRegistry`：单例管理所有工具，Agent 按需拉取 | 0.5天 |
| P0 | 修复 `LogisticsAgent` 的 async bug：用 `run_connector` | 0.1天 |
| P1 | 工具参数 Pydantic schema 校验（LangChain `Tool` 已支持 `args_schema`） | 0.3天 |
| P1 | observation 后处理：截断 >500字、标注数据来源、添加置信度 | 0.3天 |

---

## 2. Multi-step Reasoning（4/10）

### 现状

- LangGraph `create_react_agent` 自带 ReAct 循环（Thought→Action→Observation→...→Final Answer）
- Supervisor 管线：classify → route → dispatch → aggregate，**线性单向**
- 传统路径 `_run_legacy_agent` 提取 `ToolMessage` 形成 `intermediate_steps` trace

### 缺陷

1. **无显式 CoT**：LLM 推理过程不可见，只看到最终的 tool_call。Agent 没有 "先分析再行动" 的结构化思考
2. **无迭代循环**：Supervisor 分发一次就聚合——如果专家 A 的结果依赖专家 B，无法处理
3. **无自我纠错**：工具返回空/错误 → Agent 直接当作答案，不会重试或换策略
4. **无追问能力**：信息不足时不会反问买家，强行给出可能错误的答案
5. **Supervisor 与子 Agent 脱节**：子 Agent 各自独立运行 ReAct，但 Supervisor 不观察子 Agent 的过程，只看最终结果

### 优化方案

| 优先级 | 措施 | 工作量 |
|---|---|---|
| P0 | ReAct 循环增加 max_iterations 上限 + 早停（连续 3 轮无进展则降级） | 0.3天 |
| P0 | 增加 CoT Prompt："分析问题→确定所需信息→选择工具→解读结果→形成回复" | 0.2天 |
| P1 | 迭代调度：Supervisor 根据首轮结果决定是否需要第二轮专家调用 | 0.5天 |
| P2 | 自我纠错：工具返回空/异常 → 自动尝试替代工具或追问买家 | 0.5天 |
| P2 | 信息不足反问问买家的能力（ask_user tool） | 0.2天 |

---

## 3. Memory（2/10）

### 现状

- **短期记忆**：`chat_history` 参数透传，仅在 `ai_suggest.py::get_ai_suggestions` 中使用
- **长期记忆**：ChromaDB 存储商品向量/话术向量/工单案例，但用于语义检索非记忆
- **Supervisor**：`process()` 接收 `chat_history` 但未传递给子 Agent
- **无会话持久化**：每次调用 stateless，Agent 不记得上一轮说过什么

### 缺陷

1. **短期记忆断裂**：Supervisor 不传 chat_history 给子 Agent → 子 Agent 不知道对话上下文
2. **无长期用户记忆**：不记得买家的偏好、历史问题、购买记录 → 每次都是陌生人
3. **无 Agent 执行记忆**：不记录本次调用了哪些工具、效果如何 → 无学习
4. **无会话级状态**：跨轮次无法追踪正在处理的问题（如工单处理到哪一步）
5. **ChromaDB 使用方式停留**：只做知识检索，未扩展为记忆存储

### 优化方案

| 优先级 | 措施 | 工作量 |
|---|---|---|
| P0 | Supervisor 传递 chat_history 给子 Agent（1 行修改） | 0.05天 |
| P1 | 会话记忆落库：`kb_conversations`/`kb_messages` 已存在 → Agent 每次调用后自动写入 | 0.5天 |
| P1 | 买家画像 Memory：从 `ExternalOrder` + 历史会话中提取偏好 → 存入 ChromaDB 新 collection `buyer_memory` | 1天 |
| P2 | Agent 执行记忆：记录 {question, intents, experts_called, tools_used, success} → ChromaDB collection `agent_memory`，下次类似问题优先复用成功策略 | 1天 |
| P2 | 跨轮次状态追踪：新增 `agent_sessions` 表（session_id, state_json, created_at） | 0.5天 |

---

## 4. Autonomous Planning（3/10）

### 现状

- Supervisor 做一层路由：关键词匹配 + LLM fallback → 决定调用哪些专家
- 专家串行执行，结果聚合后一次性合成回复
- 无任务分解、无优先级排序、无依赖管理

### 缺陷

1. **无任务分解**：复杂问题 "我的订单到哪了，顺便帮我看看同款有没有货" → 路由到 order+product 两个专家，但不会串起来（先查订单→根据订单商品查库存）
2. **无动态优先级**：所有专家平等对待，无"先解决订单问题再推荐替代品"的先后顺序
3. **无重规划**：专家返回空结果 → 没有 "换个关键词再搜" 或 "降级到通用知识库" 的 fallback
4. **无澄清式规划**：意图模糊时不会输出中间问题（"你是指最近那个订单还是所有订单？"）
5. **线性不可逆**：管线只能向前，无法跳回上一步

### 优化方案

| 优先级 | 措施 | 工作量 |
|---|---|---|
| P1 | 增加 RePlan 节点：dispatch_experts 后插入检查 → 如果关键专家返回空/低置信度 → 触发 replan | 0.5天 |
| P1 | 任务依赖链：intent 不只是集合，改为 DAG → order→logistics 串行，product 并行 | 0.5天 |
| P2 | LLM 生成执行计划：用 Structured Output 替代规则路由，输出 `[{task, expert, priority, depends_on}]` | 1天 |
| P2 | 澄清节点：置信度 < 阈值 → 不合成最终回复，改为生成追问 | 0.3天 |

---

## 5. Tools（5/10）

### 现状

```
query_order           → DB 查询 (真实)
check_logistics       → Mock 假数据 (有 vmall 调用尝试但 bug)
search_product_kb     → ChromaDB 向量检索 (真实)
check_inventory       → DB 查询 (真实)
search_ticket_history → ChromaDB 向量检索 (真实)
```

5 个工具中 3 个真实、1 个半真半假（logistics 有代码路径但 bug）、1 个纯 mock。

### 缺失的关键业务工具

| 工具 | 业务价值 | 实现可行 | 所需接口 |
|---|---|---|---|
| deliver_order | 客服发货 | ✅ 已有 | `V3Connector.deliver_order` + API |
| send_message_to_buyer | 主动联系 | ✅ 已有 | `V3Connector.send_notification`(Slice 2 新增) |
| create_ticket | 创建工单 | ✅ 已有 | `POST /tickets` API |
| get_real_logistics | 真物流 | ✅ 已有 | `V3Connector.get_logistics`(修 bug) |
| recommend_products | 推荐商品 | ✅ 已有 | `POST /recommendations/for-buyer` |
| get_buyer_profile | 买家画像 | ⚠️ 需新建 | 聚合 order+conversation 数据 |
| cancel_order | 取消订单 | ❌ vmall 无接口 | 需 vmall 新增 |

### 优化方案

| 优先级 | 措施 | 工作量 |
|---|---|---|
| P0 | 统一工具注册中心 `ToolRegistry`（同维度1） | 0.5天 |
| P0 | 修复物流工具：`run_connector(connector.get_logistics(tracking_no))` | 0.1天 |
| P1 | 新增 3 个业务工具：`deliver_order`、`send_buyer_message`、`create_support_ticket` | 0.5天 |
| P1 | 新增 `recommend_products` 工具（已有 API，只包 @tool） | 0.1天 |
| P2 | 新增 `get_buyer_profile` 工具（聚合订单+会话数据） | 0.5天 |

---

## 实施路线图

| 阶段 | 内容 | 涉及维度 | 工作量 |
|---|---|---|---|
| **Phase A: 紧急修复** | 统一 ToolRegistry + 修 logistics async bug + chat_history 透传 | FC, MR, Tools | 0.5天 |
| **Phase B: 推理闭环** | CoT Prompt + ReAct 迭代上限 + RePlan 节点 | MR, Planning | 1天 |
| **Phase C: 工具补齐** | 3 新业务工具 + recommend_products + observation 后处理 | Tools, FC | 0.5天 |
| **Phase D: 记忆体系** | 会话落库 + 买家画像 Memory + Agent 执行记忆 | Memory | 2天 |
| **Phase E: 高级规划** | LLM Structured Output 规划 + DAG 依赖 + 澄清节点 | Planning | 1.5天 |
| **总计** | | | **5.5天** |

## 不做（超出当前项目范围）

- 多模态 Agent（图片/语音输入）
- Agent-to-Agent 协商（merchant agent ↔ platform agent）
- 强化学习 fine-tune（RLHF）
- Agent 安全审计（prompt injection 防护）
