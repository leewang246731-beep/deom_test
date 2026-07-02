"""消费者端 - 商品付款链接生成与支付确认"""
import secrets
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.response import ok
from app.core.security import decode_token
from app.database.session import get_db, SessionLocal
from app.models.vm_buyer import VmBuyer
from app.models.vm_order import VmOrder
from app.models.vm_product import VmProduct
from app.models.vm_wallet import VmWallet, VmWalletTransaction

router = APIRouter(prefix="/consumer/orders", tags=["消费者-付款链接"])

# 链接 token 有效期 30 分钟
LINK_EXPIRY_MINUTES = 30
# token → (order_id, buyer_id, expires_at) 内存缓存，生产应改用 Redis
_link_store: dict[str, dict] = {}


def _get_buyer(auth: str) -> int:
    payload = decode_token(auth.split(" ", 1)[1])
    return int(payload["sub"])


def _cleanup_expired():
    """清理过期 token"""
    now = datetime.now()
    expired = [k for k, v in _link_store.items() if v["expires_at"] < now]
    for k in expired:
        del _link_store[k]


@router.post("/payment-link")
def generate_payment_link(body: dict, authorization: str = Header(None),
                          db: Session = Depends(get_db)):
    """为指定商品生成带优惠券的付款链接。

    请求参数:
        product_id: int  商品ID
        sku_code: str    规格代码（可选，默认取第一个SKU）
        quantity: int    数量（默认1）
        coupon_code: str 优惠券码（可选）

    返回:
        link: str        付款链接（相对路径）
        order_id: int    创建的订单ID
        amount: float    应付金额
        expires_in: int  链接有效期（分钟）
    """
    buyer_id = _get_buyer(authorization)
    _cleanup_expired()

    pid = body.get("product_id")
    if not pid:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "缺少 product_id"})

    product = db.query(VmProduct).filter(VmProduct.id == pid, VmProduct.status == 1).first()
    if not product:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "商品不存在或已下架"})

    # 选择 SKU
    sku_code = body.get("sku_code")
    skus = product.skus_json or []
    if not skus:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "商品无可用规格"})
    if sku_code:
        sku = next((s for s in skus if s.get("sku_code") == sku_code), None)
        if not sku:
            raise HTTPException(status_code=400, detail={"code": 40001, "msg": "规格不存在"})
    else:
        sku = skus[0]
        sku_code = sku["sku_code"]

    quantity = max(1, int(body.get("quantity", 1)))
    unit_price = float(sku.get("price", product.price_min))
    total_amount = round(unit_price * quantity, 2)

    # 优惠券处理（预留接口，当前仅记录 coupon_code）
    coupon_code = body.get("coupon_code", "")
    discount_amount = 0.0
    if coupon_code:
        # TODO: 对接优惠券系统校验 + 计算折扣
        # 当前标记 coupon_code 到订单备注，实际折扣由商户后台配置
        pass

    pay_amount = round(total_amount - discount_amount, 2)

    # 创建待付款订单
    buyer = db.query(VmBuyer).filter(VmBuyer.id == buyer_id).first()
    order = VmOrder(
        buyer_id=buyer_id,
        merchant_id=product.merchant_id,
        product_id=pid,
        sku_code=sku_code,
        quantity=quantity,
        total_amount=total_amount,
        discount_amount=discount_amount,
        pay_amount=pay_amount,
        status="pending",
        receiver_name=body.get("receiver_name", buyer.nickname if buyer else ""),
        receiver_phone=body.get("receiver_phone", ""),
        receiver_address=body.get("receiver_address", ""),
        remark=f"AI客服生成链接" + (f" 券码:{coupon_code}" if coupon_code else ""),
        created_at=datetime.now(),
    )
    db.add(order)
    db.flush()

    # 生成访问 token
    token = secrets.token_urlsafe(24)
    _link_store[token] = {
        "order_id": order.id,
        "buyer_id": buyer_id,
        "expires_at": datetime.now() + timedelta(minutes=LINK_EXPIRY_MINUTES),
    }

    return ok({
        "link": f"/pay/{token}",
        "order_id": order.id,
        "amount": pay_amount,
        "original_amount": total_amount,
        "discount": discount_amount,
        "product_title": product.title,
        "expires_in": LINK_EXPIRY_MINUTES,
    })


@router.get("/payment-link/{token}")
def get_payment_link_info(token: str, db: Session = Depends(get_db)):
    """根据 token 获取付款链接详情（支付确认页面使用）。"""
    _cleanup_expired()
    info = _link_store.get(token)
    if not info:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "链接不存在或已过期"})

    order = db.query(VmOrder).filter(VmOrder.id == info["order_id"]).first()
    if not order:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})
    if order.status != "pending":
        return ok({"order_id": order.id, "status": order.status, "msg": "该订单已处理"})

    product = db.query(VmProduct).filter(VmProduct.id == order.product_id).first()
    return ok({
        "order_id": order.id,
        "status": order.status,
        "product": {
            "id": product.id if product else None,
            "title": product.title if product else "",
            "image": product.main_image if product else "",
            "price": float(order.total_amount),
        } if product else None,
        "quantity": order.quantity,
        "pay_amount": float(order.pay_amount),
        "discount_amount": float(order.discount_amount or 0),
        "coupon_code": order.remark or "",
        "expires_in": max(0, int((info["expires_at"] - datetime.now()).total_seconds() // 60)),
    })


@router.post("/payment-link/{token}/confirm")
def confirm_payment(token: str, authorization: str = Header(None),
                    db: Session = Depends(get_db)):
    """确认支付（从余额扣款）。"""
    buyer_id = _get_buyer(authorization)
    _cleanup_expired()

    info = _link_store.get(token)
    if not info:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "链接不存在或已过期"})
    if info["buyer_id"] != buyer_id:
        raise HTTPException(status_code=403, detail={"code": 40301, "msg": "无权操作此订单"})

    order = db.query(VmOrder).filter(VmOrder.id == info["order_id"]).first()
    if not order:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "订单不存在"})
    if order.status != "pending":
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": f"订单状态为{order.status}，不可支付"})

    # 检查余额
    wallet = db.query(VmWallet).filter(VmWallet.buyer_id == buyer_id).first()
    if not wallet or wallet.balance < order.pay_amount:
        return ok({"success": False, "msg": f"余额不足，需要¥{float(order.pay_amount):.2f}"})

    # 扣款
    wallet.balance -= order.pay_amount
    db.add(VmWalletTransaction(
        buyer_id=buyer_id,
        order_id=order.id,
        amount=-order.pay_amount,
        type="payment",
        remark=f"支付订单#{order.id}",
        created_at=datetime.now(),
    ))

    # 更新订单状态
    order.status = "paid"
    order.pay_time = datetime.now()

    # 清理 token
    del _link_store[token]
    db.commit()

    return ok({"success": True, "order_id": order.id, "paid": float(order.pay_amount),
               "msg": "支付成功"})


# ===== 内部 API（供 SaaS 调用，无需买家认证）=====

INTERNAL_KEY = "vmall-internal-demo-key"


@router.post("/payment-link/internal")
def generate_payment_link_internal(body: dict, db: Session = Depends(get_db)):
    """SaaS 内部调用：为买家生成付款链接。

    请求参数:
        api_key: str      内部调用密钥
        buyer_id: int     买家ID
        product_id: int   商品ID
        coupon_code: str  优惠券码（可选）

    返回同上 generate_payment_link
    """
    if body.get("api_key") != INTERNAL_KEY:
        raise HTTPException(status_code=403, detail={"code": 40300, "msg": "无权访问"})

    _cleanup_expired()
    buyer_id = body.get("buyer_id")
    pid = body.get("product_id")

    if not buyer_id or not pid:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "缺少 buyer_id 或 product_id"})

    product = db.query(VmProduct).filter(VmProduct.id == pid, VmProduct.status == 1).first()
    if not product:
        raise HTTPException(status_code=404, detail={"code": 40401, "msg": "商品不存在或已下架"})

    skus = product.skus_json or []
    if not skus:
        raise HTTPException(status_code=400, detail={"code": 40001, "msg": "商品无可用规格"})
    sku = skus[0]
    sku_code = sku["sku_code"]
    unit_price = float(sku.get("price", product.price_min))
    quantity = max(1, int(body.get("quantity", 1)))
    total_amount = round(unit_price * quantity, 2)

    coupon_code = body.get("coupon_code", "")
    pay_amount = total_amount  # 优惠券折扣由券系统计算

    order = VmOrder(
        buyer_id=buyer_id,
        merchant_id=product.merchant_id,
        product_id=pid,
        sku_code=sku_code,
        quantity=quantity,
        total_amount=total_amount,
        discount_amount=0,
        pay_amount=pay_amount,
        status="pending",
        receiver_name="",
        receiver_phone="",
        receiver_address="",
        remark=f"AI客服生成链接" + (f" 券码:{coupon_code}" if coupon_code else ""),
        created_at=datetime.now(),
    )
    db.add(order)
    db.flush()

    token = secrets.token_urlsafe(24)
    _link_store[token] = {
        "order_id": order.id,
        "buyer_id": buyer_id,
        "expires_at": datetime.now() + timedelta(minutes=LINK_EXPIRY_MINUTES),
    }
    db.commit()

    return ok({
        "link": f"/pay/{token}",
        "order_id": order.id,
        "amount": pay_amount,
        "product_title": product.title,
        "expires_in": LINK_EXPIRY_MINUTES,
    })
