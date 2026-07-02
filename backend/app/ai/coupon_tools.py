"""优惠券 Agent 工具 — 闭包绑定 merchant_id，供 LLM 调用"""
from langchain_core.tools import tool as langchain_tool

from app.core.config import settings
from app.database.session import SessionLocal
from app.models.coupon import CouponGrantLog
from app.services.coupon_engine import MarketingEngine, PolicyEngine
from app.services.external_apis import CouponAPI, OrderService, TicketService

# 补偿场景 → 允许的订单状态集合（其他状态视为"无异常"，不应自动发券）
SCENARIO_ALLOWED_STATUS = {
    "logistics_delay": {"paid", "shipped"},               # 已付款/运输中才可能延迟
    "quality_issue": {"completed"},                        # 已收货才能发现质量问题
    "service_complaint": {"paid", "shipped", "completed"}, # 服务投诉贯穿全流程
}


def _check_auto_coupon_enabled() -> str | None:
    """检查自动发券开关，关闭时返回转人工消息；开启时返回 None。"""
    if not settings.ENABLE_AUTO_COUPON:
        return "自动发券功能当前已关闭，已为您转接人工专员处理，请稍候。"
    return None


def _validate_order_for_scenario(order_status: str, scenario: str) -> str | None:
    """校验订单状态是否匹配补偿场景，不匹配时返回拒绝理由。"""
    allowed = SCENARIO_ALLOWED_STATUS.get(scenario)
    if allowed is None:
        return f"未知的补偿场景: {scenario}"

    if order_status not in allowed:
        status_cn = {
            "pending": "待付款", "paid": "已付款", "shipped": "已发货",
            "completed": "已完成", "refunding": "退款中", "refunded": "已退款",
        }
        current = status_cn.get(order_status, order_status)
        allowed_cn = "、".join(status_cn.get(s, s) for s in sorted(allowed))
        return (
            f"订单当前状态为「{current}」，而「{scenario}」场景要求订单状态为「{allowed_cn}」。"
            f"当前订单状态正常，不符合该补偿场景的自动发券条件。"
        )
    return None


# ===== 售后补偿工具 =====

def build_compensate_tool(merchant_id: int):
    """创建售后补偿工具 — 闭包绑定 merchant_id"""

    @langchain_tool
    def compensate(order_id: str, scenario: str, reason: str) -> str:
        """给买家发放售后补偿优惠券。

        适用场景：用户投诉物流延迟、商品质量问题、服务投诉等，经核实为商户责任后调用。

        参数：
        - order_id: 订单号（从 query_order 工具返回结果中获取）
        - scenario: 补偿场景，可选值 logistics_delay / quality_issue / service_complaint
        - reason: 发放理由简述（如"物流超时3天"）

        返回：发放结果，包含券码和金额或失败原因。
        """
        # 0. 全局降级开关
        disabled_msg = _check_auto_coupon_enabled()
        if disabled_msg:
            return disabled_msg

        policy_engine = PolicyEngine(merchant_id)
        coupon_api = CouponAPI(merchant_id)

        # 1. 订单查询 → 反查 buyer 身份
        order = OrderService.get_order(merchant_id, order_id)
        if not order:
            return "订单不存在，无法核实补偿资格。请确认订单号是否正确。"

        user_id = order.user_id

        # 2. 订单状态校验 — 状态不符合场景的订单不应补偿
        status_err = _validate_order_for_scenario(order.status, scenario)
        if status_err:
            return status_err

        # 3. 策略校验（冷却期/次数/人工审核）
        allowed, msg, policy = policy_engine.check_eligibility(user_id, order_id, scenario)
        if not allowed:
            return msg

        # 4. 发券
        res = coupon_api.issue(policy.coupon_template_id, user_id)
        if not res.success:
            return f"优惠券发放失败: {res.message}"

        # 5. 记录日志
        db = SessionLocal()
        try:
            log = CouponGrantLog(
                merchant_id=merchant_id,
                user_id=user_id,
                order_id=order_id,
                type="compensation",
                scenario=scenario,
                coupon_code=res.coupon_code,
                amount=res.amount,
                reason=reason,
            )
            db.add(log)
            db.commit()
        finally:
            db.close()

        return f"已为您申请 {res.amount:.2f} 元优惠券（券码: {res.coupon_code}），下次购物可用。"

    return compensate


# ===== 售前营销工具 =====

def build_issue_promo_tool(merchant_id: int):
    """创建售前发券工具 — 闭包绑定 merchant_id"""

    @langchain_tool
    def issue_promo(campaign_id: int, user_id: str, reason: str) -> str:
        """给买家发放售前营销优惠券。

        适用场景：用户在咨询中表现出购买意向或主动询问优惠活动时，推荐并发放优惠券。

        参数：
        - campaign_id: 营销活动ID（数字）
        - user_id: 买家OpenID（从对话上下文中获取，通常是 buyer_openid 或 buyer_nick）
        - reason: 发放理由简述（如"新用户首单优惠"）

        返回：发放结果，包含券码和金额或失败原因。
        """
        # 0. 全局降级开关
        disabled_msg = _check_auto_coupon_enabled()
        if disabled_msg:
            return disabled_msg

        marketing_engine = MarketingEngine(merchant_id)
        coupon_api = CouponAPI(merchant_id)

        # 1. 活动有效性
        campaign = marketing_engine.get_active_campaign(campaign_id)
        if not campaign:
            return "活动不存在或已结束"

        # 2. 人工审核标记
        if campaign.require_manual:
            TicketService.create_ticket(
                merchant_id, user_id,
                title=f"营销活动人工审核 - 活动{campaign_id}",
                description=f"用户 {user_id} 申请领取活动「{campaign.campaign_name}」优惠券，需人工审核发放。\n理由: {reason}",
                campaign_id=campaign.id,
            )
            return "该活动需人工审核，已为您转接专员处理，请稍候。"

        # 3. 用户资格及库存
        allowed, msg = marketing_engine.check_and_deduct(user_id, campaign)
        if not allowed:
            return msg

        # 4. 发券
        res = coupon_api.issue(campaign.coupon_template_id, user_id)
        if not res.success:
            return f"领取失败: {res.message}"

        # 5. 记录
        db = SessionLocal()
        try:
            log = CouponGrantLog(
                merchant_id=merchant_id,
                user_id=user_id,
                campaign_id=campaign.id,
                type="marketing",
                coupon_code=res.coupon_code,
                amount=res.amount,
                reason=reason,
            )
            db.add(log)
            db.commit()
        finally:
            db.close()

        return f"已为您发放 {res.amount:.2f} 元优惠券（券码: {res.coupon_code}），有效期至 {campaign.end_time.strftime('%Y-%m-%d') if campaign.end_time else '领取后30天'}。"

    return issue_promo


# ===== 查询营销活动工具（推荐用）=====

def build_list_promos_tool(merchant_id: int):
    """创建查询可领营销活动工具"""

    @langchain_tool
    def list_promos() -> str:
        """查询当前有效的营销活动列表，用于向买家推荐可用优惠。

        返回：当前可领取的营销活动列表，包含活动ID、名称、目标用户类型和库存情况。
        """
        engine = MarketingEngine(merchant_id)
        campaigns = engine.list_active_campaigns()
        if not campaigns:
            return "当前暂无有效的营销活动"

        lines = ["当前有效营销活动:"]
        for c in campaigns:
            stock_info = f"剩余{c['max_issue_total']}张" if c["max_issue_total"] else "不限量"
            lines.append(
                f"  ID:{c['id']} - {c['name']} "
                f"目标:{c['target_user_type']} "
                f"每人限{c['max_issue_per_user']}次 "
                f"{stock_info} "
                f"截止:{c['end_time']}"
            )
        return "\n".join(lines)

    return list_promos
