"""付款链接 Agent 工具 — 闭包绑定 merchant_id"""
import json
import logging
import urllib.request

from langchain_core.tools import tool as langchain_tool

from app.database.session import SessionLocal
from app.models.platform_shop import PlatformShop

logger = logging.getLogger(__name__)

INTERNAL_KEY = "vmall-internal-demo-key"


def _get_vmall_url(merchant_id: int) -> str | None:
    """获取商户的 vmall 后端 URL。"""
    db = SessionLocal()
    try:
        shop = db.query(PlatformShop).filter(
            PlatformShop.merchant_id == merchant_id,
            PlatformShop.platform_type == "vmall",
            PlatformShop.is_active == 1,
        ).first()
        if shop and shop.shop_url:
            return shop.shop_url.rstrip("/")
        return "http://vmall-backend:8020"  # Docker 兜底
    finally:
        db.close()


def build_generate_payment_link_tool(merchant_id: int):
    """生成商品付款链接工具"""

    @langchain_tool
    def generate_payment_link(product_id: int, buyer_id: int,
                              coupon_code: str = "", quantity: int = 1) -> str:
        """为买家生成商品付款链接。链接可在聊天窗口中点击跳转到支付确认页。

        使用时机：买家明确表示要购买某商品时，生成一个带商品信息和优惠券的付款链接。

        参数：
        - product_id: vmall 商品ID（数字，从对话上下文或 webhook 中获取）
        - buyer_id: 买家ID（数字，从对话上下文获取）
        - coupon_code: 可选优惠券码，如已通过 compensate/issue_promo 发券则传入券码
        - quantity: 购买数量，默认1

        返回：付款链接及订单摘要。
        """
        vmall_url = _get_vmall_url(merchant_id)
        if not vmall_url:
            return "未找到该商户的 vmall 店铺，无法生成付款链接。请联系人工客服处理。"

        payload = {
            "api_key": INTERNAL_KEY,
            "buyer_id": buyer_id,
            "product_id": product_id,
            "quantity": quantity,
        }
        if coupon_code:
            payload["coupon_code"] = coupon_code

        try:
            req = urllib.request.Request(
                f"{vmall_url}/api/v1/consumer/orders/payment-link/internal",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            data = result.get("data", {})
            if not data or not data.get("link"):
                return f"生成付款链接失败: {result.get('msg', '未知错误')}"

            link = data["link"]
            amount = data.get("amount", 0)
            title = data.get("product_title", "商品")
            full_url = f"{vmall_url}/#/pay/{link.split('/')[-1]}" if link.startswith("/pay/") else link

            lines = [
                f"已为您生成「{title}」的专属下单链接：",
                f"👉 {full_url}",
                f"应付金额：¥{amount:.2f}",
            ]
            if coupon_code:
                lines.append(f"优惠券：{coupon_code}（已自动绑定）")
            lines.append("链接30分钟内有效，点击即可确认支付。")
            return "\n".join(lines)

        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            logger.error("Payment link HTTP %s: %s", e.code, body)
            return f"生成付款链接失败（{e.code}），请稍后重试或联系人工客服。"
        except Exception as e:
            logger.error("Payment link error: %s", e)
            return f"付款链接服务暂时不可用，请稍后重试或联系人工客服。"

    return generate_payment_link
