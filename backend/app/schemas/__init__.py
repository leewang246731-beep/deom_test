"""Pydantic 请求/响应模型"""
from pydantic import BaseModel
from typing import Optional, List


# ===== 认证 =====
class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


# ===== 店铺 =====
class ShopCreate(BaseModel):
    platform_type: str = "mock"
    shop_name: str
    shop_url: Optional[str] = None


# ===== AI =====
class AISuggestRequest(BaseModel):
    shop_id: int
    buyer_question: str
    conversation_history: Optional[List[dict]] = None
    product_id: Optional[int] = None


class AISearchRequest(BaseModel):
    query: str
    shop_id: Optional[int] = None
    top_k: int = 5


class AISuggestLogRequest(BaseModel):
    conversation_id: int
    buyer_question: str
    ai_suggestion: str
    was_adopted: int = 1  # 0:忽略 1:采纳 2:修改后发送
    final_message: Optional[str] = None


class AICampaignRequest(BaseModel):
    shop_id: int
    limit: int = 20
    offset: int = 0


class RecommendationRuleCreate(BaseModel):
    product_id: int
    recommended_product_id: int
    rule_type: Optional[str] = "manual"
    priority: Optional[int] = 0
