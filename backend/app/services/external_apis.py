"""外部系统对接客户端 — 订单查询 / 用户画像 / 优惠券发券 / 工单创建

当前为 Mock 实现，生产环境替换为真实 API 调用。
所有方法都接受 merchant_id 保证租户隔离。
"""
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


# ===== 数据类 =====

@dataclass
class OrderInfo:
    order_id: str
    user_id: str
    status: str
    pay_amount: float
    buyer_nick: str = ""


@dataclass
class UserProfile:
    user_id: str
    is_new: bool = False
    is_vip: bool = False
    vip_level: int = 0


@dataclass
class CouponResult:
    success: bool
    coupon_code: str = ""
    amount: float = 0.0
    message: str = ""


# ===== 订单服务 =====

class OrderService:
    """商户订单查询 — 对接商户订单系统 API"""

    @staticmethod
    def get_order(merchant_id: int, order_id: str) -> Optional[OrderInfo]:
        """查询订单详情。

        生产环境替换为:
            POST {merchant_order_api}/order/detail
            Body: {merchant_id, order_id}
            Header: Authorization: Bearer {merchant_token}
        """
        from app.database.session import SessionLocal
        from app.models.external_order import ExternalOrder
        from app.models.platform_shop import PlatformShop

        db = SessionLocal()
        try:
            sids = [
                r[0] for r in db.query(PlatformShop.id).filter(
                    PlatformShop.merchant_id == merchant_id
                ).all()
            ]
            if not sids:
                return None

            o = db.query(ExternalOrder).filter(
                ExternalOrder.shop_id.in_(sids),
                ExternalOrder.platform_order_id == order_id,
            ).first()
            if not o:
                # 也尝试按内部 ID 查询
                if order_id.isdigit():
                    o = db.query(ExternalOrder).filter(
                        ExternalOrder.shop_id.in_(sids),
                        ExternalOrder.id == int(order_id),
                    ).first()
            if not o:
                return None

            return OrderInfo(
                order_id=o.platform_order_id,
                user_id=o.buyer_openid,
                status=o.status,
                pay_amount=float(o.pay_amount),
                buyer_nick=o.buyer_nick or "",
            )
        finally:
            db.close()


# ===== 用户画像服务 =====

class UserProfileService:
    """用户画像查询 — 对接用户画像系统 API"""

    @staticmethod
    def get_profile(merchant_id: int, user_id: str) -> UserProfile:
        """查询用户标签。

        生产环境替换为:
            POST {user_profile_api}/profile/query
            Body: {merchant_id, user_id}
        """
        from app.database.session import SessionLocal
        from app.models.external_order import ExternalOrder
        from app.models.platform_shop import PlatformShop

        db = SessionLocal()
        try:
            sids = [
                r[0] for r in db.query(PlatformShop.id).filter(
                    PlatformShop.merchant_id == merchant_id
                ).all()
            ]
            order_count = 0
            if sids:
                order_count = db.query(ExternalOrder).filter(
                    ExternalOrder.shop_id.in_(sids),
                    ExternalOrder.buyer_openid == user_id,
                ).count()

            return UserProfile(
                user_id=user_id,
                is_new=(order_count == 0),
                is_vip=(order_count >= 5),  # 简化逻辑：≥5 单视为 VIP
                vip_level=(2 if order_count >= 10 else (1 if order_count >= 5 else 0)),
            )
        finally:
            db.close()


# ===== 优惠券发券 API =====

class CouponAPI:
    """优惠券系统对接 — 发券 / 查询"""

    def __init__(self, merchant_id: int):
        self.merchant_id = merchant_id
        # 生产环境从商户配置读取:
        # self.base_url = get_merchant_config(merchant_id, 'coupon_api_base')
        # self.api_key = get_merchant_config(merchant_id, 'coupon_api_key')

    def issue(self, template_id: str, user_id: str) -> CouponResult:
        """发放优惠券。

        生产环境替换为:
            POST {base_url}/coupon/issue
            Header: Authorization: Bearer {api_key}
            Body: {template_id, user_id, merchant_id}
        """
        import random
        import string

        # Mock: 生成模拟券码和金额
        code = "COUPON" + ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        # 从模板 ID 中提取金额提示（如 TPL_DELAY_10 → 10 元）
        amount_hint = 5.0
        try:
            parts = template_id.rsplit("_", 1)
            amount_hint = float(parts[1]) if len(parts) == 2 else 5.0
        except (ValueError, IndexError):
            amount_hint = 5.0
        amount = round(amount_hint + random.uniform(-1, 1), 2)

        logger.info(
            "[CouponAPI Mock] 发券 merchant=%s template=%s user=%s → code=%s amount=%.2f",
            self.merchant_id, template_id, user_id, code, amount,
        )
        return CouponResult(success=True, coupon_code=code, amount=amount,
                            message=f"优惠券已发放，券码 {code}")


# ===== 工单服务 =====

class TicketService:
    """工单系统对接 — 大额/异常转人工"""

    @staticmethod
    def create_ticket(merchant_id: int, user_id: str, title: str,
                      description: str, order_id: str = "",
                      campaign_id: int = 0) -> bool:
        """创建人工审核工单。

        生产环境替换为:
            POST {ticket_api}/ticket/create
            Body: {merchant_id, user_id, title, description, ...}
        """
        from app.database.session import SessionLocal
        from app.models.ticket import Ticket
        from app.models.ticket_category import TicketCategory
        from datetime import datetime

        db = SessionLocal()
        try:
            category_id = None
            cat = db.query(TicketCategory).filter(
                TicketCategory.merchant_id == merchant_id,
            ).first()
            if cat:
                category_id = cat.id

            ticket = Ticket(
                merchant_id=merchant_id,
                title=title,
                description=description,
                priority="medium",
                status="pending",
                category_id=category_id,
                buyer_openid=user_id,
                created_at=datetime.now(),
            )
            db.add(ticket)
            db.commit()
            logger.info(
                "[TicketService] 工单已创建 merchant=%s user=%s title=%s",
                merchant_id, user_id, title,
            )
            return True
        except Exception as e:
            logger.error("[TicketService] 创建工单失败: %s", e)
            return False
        finally:
            db.close()
