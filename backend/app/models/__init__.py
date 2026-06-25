"""
集中导入全部 ORM 模型，便于 Base.metadata 发现所有表（供 create_all 使用）。
一期 7 张核心表。
"""
from app.models.merchant import Merchant
from app.models.merchant_user import MerchantUser
from app.models.platform_shop import PlatformShop
from app.models.external_product import ExternalProduct
from app.models.external_order import ExternalOrder
from app.models.conversation import Conversation
from app.models.category import Category

from app.models.ai_suggestion_log import AISuggestionLog
from app.models.ai_style_config import AIStyleConfig
from app.models.buyer_profile import BuyerProfile
from app.models.product_co_purchase import ProductCoPurchase
from app.models.product_recommendation_rule import ProductRecommendationRule
from app.models.skill_group import SkillGroup, SkillMember
from app.models.sla_policy import SLAPolicy
from app.models.ticket import Ticket
from app.models.ticket_assignment import TicketAssignment
from app.models.ticket_category import TicketCategory
from app.models.ticket_comment import TicketComment
from app.models.service_mode import ServiceModeConfig, AutoReplyLog
from app.models.audit_log import AuditLog
from app.models.webhook_delivery_log import WebhookDeliveryLog
from app.kb.models import KbDocument, KbChunk, KbConversation, KbMessage

__all__ = [
    "Merchant", "MerchantUser", "PlatformShop", "ExternalProduct", "ExternalOrder",
    "Conversation", "Category", "AISuggestionLog", "AIStyleConfig",
    "BuyerProfile", "ProductCoPurchase", "ProductRecommendationRule",
    "SkillGroup", "SkillMember", "SLAPolicy",
    "Ticket", "TicketAssignment", "TicketCategory", "TicketComment",
    "ServiceModeConfig", "AutoReplyLog",
    "AuditLog", "WebhookDeliveryLog",
    "KbDocument", "KbChunk", "KbConversation", "KbMessage",
]
