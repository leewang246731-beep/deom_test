# AI 话术引擎设计

> 面向客服场景的 AI 话术检索与生成 Pipeline

---

## 一、Pipeline 总览

```
买家消息 "这个有黑色的吗？L码还有吗？"
    │
    ▼
┌─────────────────────────────────────────────┐
│  Step 1: 向量检索 (ChromaDB)                 │
│  ┌───────────────┐  ┌──────────────────────┐ │
│  │ 商品知识匹配    │  │ 历史话术匹配          │ │
│  │ 搜索: title +  │  │ 搜索: buyer question │ │
│  │  description  │  │ → top-k similar      │ │
│  │ → 该商品信息   │  │ → 对应客服回复        │ │
│  └───────┬───────┘  └──────────┬───────────┘ │
│          └──────────┬──────────┘             │
│                     ▼                        │
│            RRF 融合 → Top-5                   │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│  Step 2: LLM 生成 (千问/GPT)                 │
│  Prompt = 商品信息 + 历史话术参考 + 买家问题   │
│  → 3 条回复建议                               │
└─────────────────────┬───────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│  Step 3: 后处理                              │
│  → 过滤空回复 → 去重 → 截断至200字             │
│  → 返回前端：建议列表 + 每条来源/置信度        │
└─────────────────────────────────────────────┘
```

---

## 二、向量化策略

### 商品向量

```python
# 商品同步后自动向量化
embedding_text = f"{product.title} {product.description[:500]} {product.category_path}"

# BGE-M3 输出 1024 维向量
vector = bge_model.encode(embedding_text)

# 存入 ChromaDB，带元数据
collection.add(
    documents=[embedding_text],
    embeddings=[vector.tolist()],
    metadatas=[{
        "type": "product",
        "product_id": product.id,
        "shop_id": product.shop_id,
        "title": product.title,
        "price": float(product.price),
    }],
    ids=[f"product_{product.id}"],
)
```

### 话术向量

```python
# 从 conversations.messages_json 中提取客服回复
for conv in conversations:
    messages = json.loads(conv.messages_json)
    for i, msg in enumerate(messages):
        if msg["role"] == "service":  # 客服消息
            # 用前一条买家消息作为 question
            buyer_msg = messages[i-1]["content"] if i > 0 else ""
            embedding_text = f"Q: {buyer_msg} A: {msg['content']}"
            
            vector = bge_model.encode(embedding_text)
            collection.add(
                documents=[embedding_text],
                embeddings=[vector.tolist()],
                metadatas=[{
                    "type": "reply",
                    "product_id": conv.product_id,
                    "buyer_question": buyer_msg,
                    "reply": msg["content"],
                }],
                ids=[f"reply_{conv.id}_{i}"],
            )
```

---

## 三、话术检索

```python
async def get_ai_suggestions(shop_id, buyer_question, conversation_history, product_id=None):
    collection = get_chroma_collection(merchant_id)
    
    # 1. 商品知识检索
    product_filter = {"product_id": product_id} if product_id else None
    product_results = collection.query(
        query_texts=[buyer_question],
        n_results=3,
        where={"type": "product", **product_filter} if product_filter else {"type": "product"},
    )
    
    # 2. 历史话术检索
    reply_results = collection.query(
        query_texts=[buyer_question],
        n_results=5,
        where={"type": "reply"},
    )
    
    # 3. RRF 融合排序
    fused = rrf_fusion(product_results, reply_results, k=60)
    top_5 = sorted(fused, key=lambda x: x["score"], reverse=True)[:5]
    
    # 4. LLM 生成最终建议
    context = build_context(top_5, conversation_history)
    prompt = f"""基于以下商品知识和历史话术，为买家问题生成3条回复建议。
    
    买家问题：{buyer_question}
    商品信息：{context['product_info']}
    历史话术参考：{context['reply_examples']}
    
    要求：语气自然、直接回答买家问题、每条不超过200字。
    生成3条建议，用 --- 分隔。"""
    
    response = await llm.ainvoke(prompt)
    suggestions = parse_suggestions(response)
    
    # 5. 记录采纳日志（后续优化用）
    return {"suggestions": suggestions}
```

---

## 四、催单话术生成

```python
async def generate_payment_reminders(shop_id):
    """拉取未支付订单，为每个买家生成千人千面催付话术"""
    
    # 1. Mock: 获取"下单未付"的买家列表
    connector = get_platform_connector(shop_id)
    pending_orders = await connector.fetch_orders(shop_id, status="pending")
    
    reminders = []
    for order in pending_orders:
        # 2. 检索该商品卖点
        collection = get_chroma_collection(merchant_id)
        product_info = collection.query(
            query_texts=[order["product_title"]],
            n_results=1,
            where={"type": "product"},
        )
        
        # 3. LLM 生成催付话术
        prompt = f"""生成一条催付话术：
        买家：{order['buyer_nick']}
        商品：{order['product_title']}
        卖点：{product_info['documents'][0] if product_info['documents'] else ''}
        要求：语气亲切、突出商品卖点、制造紧迫感、不超过150字。"""
        
        script = await llm.ainvoke(prompt)
        reminders.append({
            "buyer_nick": order["buyer_nick"],
            "product_title": order["product_title"],
            "script": script,
        })
        
        # 4. 模拟发送
        await connector.send_message(order["buyer_openid"], script)
    
    return {"reminders": reminders, "count": len(reminders)}
```

---

## 五、采纳反馈闭环

```
客服采纳话术 → 记录采纳日志 → 定期(每日)分析采纳率
    │
    ├── 采纳 → 该话术向量权重提升
    ├── 修改后发送 → 修改后文本替代原话术，重新向量化
    └── 忽略 → 降低该话术推荐权重
```

---

## 六、LLM Prompt 模板

```
你是{shop_name}的客服助手。当前话术风格：{style}

商品信息：
{product_context}

历史参考话术：
{reply_examples}

买家问题：{buyer_question}

请生成 3 条回复建议，每条不超过 200 字：
1. 第一建议：直接回答买家问题，附带商品信息
2. 第二建议：口语化回复，适合闲聊场景
3. 第三建议：促单导向，适合购买意向明确的场景

用 --- 分隔三条建议。
```
