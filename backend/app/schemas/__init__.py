"""Pydantic 请求/响应模型"""
from pydantic import BaseModel, Field
from typing import Optional, List


# ===== 认证 =====
class LoginRequest(BaseModel):
    username: str
    password: str
    merchant_id: Optional[int] = None  # 多商户环境指定租户


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
    quality_score: Optional[int] = None  # 1-5
    feedback_note: Optional[str] = None
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


class RecommendationRuleUpdate(BaseModel):
    rule_type: Optional[str] = None
    priority: Optional[int] = None
    is_active: Optional[int] = None


class SimilarProductsRequest(BaseModel):
    product_id: Optional[int] = None
    shop_id: Optional[int] = None
    top_k: Optional[int] = 10
    exclude_bought: Optional[bool] = False
    buyer_openid: Optional[str] = None


class BuyerRecommendationRequest(BaseModel):
    buyer_openid: Optional[str] = None
    shop_id: Optional[int] = None
    top_k: Optional[int] = 10


# ===== 工单 =====
class TicketCreate(BaseModel):
    title: str = Field(..., min_length=1, description="工单标题")
    description: Optional[str] = ""
    priority: Optional[str] = "P3"
    source: Optional[str] = "manual"
    source_id: Optional[int] = None
    category_id: Optional[int] = None
    buyer_openid: Optional[str] = None
    ticket_tags: Optional[List[str]] = None


class TicketUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    category_id: Optional[int] = None
    ticket_tags: Optional[List[str]] = None


class TicketStatusUpdate(BaseModel):
    status: str
    resolved_notes: Optional[str] = None


class TicketAssign(BaseModel):
    to_user_id: int
    remark: Optional[str] = ""


class TicketCommentCreate(BaseModel):
    content: str
    is_internal: Optional[int] = 0
    attachments: Optional[str] = None


class TicketCategoryCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None


class TicketCategoryUpdate(BaseModel):
    name: Optional[str] = None


class TicketBatchOperation(BaseModel):
    action: str
    ticket_ids: List[int]
    to_user_id: Optional[int] = None


class TicketAutoClassifyRequest(BaseModel):
    title: str = ""
    description: Optional[str] = ""


# ===== 服务模式 =====
class ServiceModeConfigUpdate(BaseModel):
    default_mode: Optional[str] = None
    auto_mode_hours: Optional[str] = None
    auto_confidence_threshold: Optional[float] = None
    fallback_confidence_threshold: Optional[float] = None
    human_response_timeout_seconds: Optional[int] = None
    fallback_escalate_timeout_seconds: Optional[int] = None
    fallback_template: Optional[str] = None
    busy_template: Optional[str] = None
    offline_template: Optional[str] = None


class ConversationModeSwitch(BaseModel):
    mode: str  # manual / copilot / auto
    reason: Optional[str] = "手动切换"


# ===== 商品 =====
class ProductCreate(BaseModel):
    shop_id: int
    title: str
    price: Optional[float] = 0
    stock: Optional[int] = 0
    description: Optional[str] = ""
    images_json: Optional[List[str]] = None
    category_path: Optional[str] = ""
    platform_product_id: Optional[str] = None
    status: Optional[int] = 1


class ProductUpdate(BaseModel):
    title: Optional[str] = None
    price: Optional[float] = None
    stock: Optional[int] = None
    description: Optional[str] = None
    images_json: Optional[List[str]] = None
    category_path: Optional[str] = None
    status: Optional[int] = None


# ===== 用户管理 =====
class UserCreate(BaseModel):
    username: str
    password: str
    display_name: Optional[str] = None
    role: str = "service"


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    status: Optional[int] = None
    password: Optional[str] = None


# ===== 技能组 =====
class SkillGroupCreate(BaseModel):
    name: str
    description: Optional[str] = ""


class SkillGroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[int] = None


class SkillMemberAdd(BaseModel):
    user_id: int
    skill_tags: Optional[List[str]] = None


# ===== SLA =====
class SLAPolicyCreate(BaseModel):
    name: str
    priority: str
    response_minutes: int = 30
    resolve_minutes: int = 480


class SLAPolicyUpdate(BaseModel):
    name: Optional[str] = None
    priority: Optional[str] = None
    response_minutes: Optional[int] = None
    resolve_minutes: Optional[int] = None


# ===== AI 风格 =====
class AIStyleCreate(BaseModel):
    name: str
    prompt_template: str
    is_default: Optional[bool] = False


class AIStyleUpdate(BaseModel):
    name: Optional[str] = None
    prompt_template: Optional[str] = None
    is_default: Optional[bool] = None


# ===== 分类 =====
class CategoryCreate(BaseModel):
    name: str
    parent_id: Optional[int] = None


class CategoryUpdate(BaseModel):
    name: Optional[str] = None
    parent_id: Optional[int] = None


# ===== 知识库 =====
class KbDocumentCreate(BaseModel):
    title: str
    content: Optional[str] = ""
    source_type: Optional[str] = "manual"
    source_id: Optional[int] = None


class KbAskRequest(BaseModel):
    question: str
    conversation_id: Optional[int] = None
    mode: Optional[str] = "auto"
    merchant_id: Optional[int] = None


class KbConversationCreate(BaseModel):
    title: Optional[str] = "新对话"
    mode: Optional[str] = "auto"


class KbSyncRequest(BaseModel):
    shop_id: Optional[int] = None
    merchant_id: Optional[int] = None


# ===== 退款 =====
class RefundRequest(BaseModel):
    reason: Optional[str] = ""


# ===== 会话消息 =====
class ConversationMessageSend(BaseModel):
    content: str
    msg_type: Optional[str] = "text"


# ===== OpenAPI (vMall 集成) =====
class GenerateBindTokenRequest(BaseModel):
    shop_id: int


class ConfirmBindRequest(BaseModel):
    bind_token: str
    vmall_url: Optional[str] = ""


class UnbindShopRequest(BaseModel):
    shop_id: int


class RegisterShopRequest(BaseModel):
    shop_name: str
    contact_phone: Optional[str] = ""
    saas_url: Optional[str] = ""
