"""
种子脚本（PHASE1-PLAN 步骤3 + REQUIREMENTS-V2 缺口6/7）
幂等：可重复运行。每次清空业务数据后用 MockPlatformConnector 重建。

生成规模（2 店铺 × 连接器单店产出）：
  1 商户 + admin/manager/service 账号
  2 个 Mock 店铺
  100 商品（仅入库，embedding_status='pending'）
  60  会话（覆盖问尺码/快递/质量，product_id 关联真实商品）
  200 订单（含多种状态）
  ~35 分类节点（从 category_path 解析自动建）

运行：
  python seed.py                    # 仅入库，不回填（快速重置）
  python seed.py --backfill         # 入库 + 自动向量回填 + 协同过滤重建
  python seed.py --backfill --full  # 同上，但全量重建 ChromaDB Collection
"""
import asyncio
import random
import sys
from datetime import datetime, timedelta

from app.core.platform_connector.mock import MockPlatformConnector
from app.core.security import hash_password
from app.database.session import SessionLocal, engine, Base
import app.models  # noqa: F401  注册全部模型
from app.models.ai_suggestion_log import AISuggestionLog
from app.models.category import Category
from app.models.conversation import Conversation
from app.models.external_order import ExternalOrder
from app.models.external_product import ExternalProduct
from app.models.merchant import Merchant
from app.models.merchant_user import MerchantUser
from app.models.platform_shop import PlatformShop

# 多商户配置: (商户名称, vmall店铺名, bind_status, [mock店铺])
MULTI_MERCHANTS = [
    {
        "name": "数码旗舰商户",
        "contact": "400-111-0001",
        "vmall": {"shop_name": "数码旗舰店", "bind_status": "active"},
        "mocks": [{"platform_type": "mock", "shop_name": "模拟数码专营店", "shop_url": "https://mock.local/shop/digital"}],
    },
    {
        "name": "时尚女装商户",
        "contact": "400-222-0002",
        "vmall": {"shop_name": "时尚女装馆", "bind_status": "active"},
        "mocks": [{"platform_type": "mock", "shop_name": "模拟潮流女装店", "shop_url": "https://mock.local/shop/fashion"}],
    },
    {
        "name": "潮流美妆商户",
        "contact": "400-333-0003",
        "vmall": {"shop_name": "潮流美妆坊", "bind_status": "idle"},
        "mocks": [],
    },
]
USERS = [
    {"username": "admin", "display_name": "超级管理员", "role": "admin"},
    {"username": "manager", "display_name": "运营经理", "role": "manager"},
    {"username": "service", "display_name": "客服小美", "role": "service"},
]


def seed_multi_merchants(db) -> list:
    """为每个预配置商户创建 Merchant 记录。返回 [(merchant_id, config), ...]"""
    results = []
    for cfg in MULTI_MERCHANTS:
        m = db.query(Merchant).filter(Merchant.name == cfg["name"]).first()
        if not m:
            m = Merchant(name=cfg["name"], contact=cfg["contact"], status=1)
            db.add(m)
            db.flush()
        results.append((m.id, cfg))
    return results


def reset_users(db, merchant_id: int):
    db.query(MerchantUser).filter(MerchantUser.merchant_id == merchant_id).delete()
    db.flush()
    for u in USERS:
        db.add(MerchantUser(
            merchant_id=merchant_id,
            username=u["username"],
            password_hash=hash_password("123456"),
            display_name=u["display_name"],
            role=u["role"],
            status=1,
        ))
    db.flush()


def clear_business_data(db, merchant_id: int):
    """按外键顺序清空业务数据（工单→采纳日志→会话→订单→商品→店铺→分类→协同→推荐→画像→SLA→技能组）。"""
    # 清工单及子表
    from app.models.ticket import Ticket
    from app.models.ticket_comment import TicketComment
    from app.models.ticket_assignment import TicketAssignment
    from app.models.ticket_category import TicketCategory as TCat
    from app.models.skill_group import SkillGroup as SG, SkillMember as SM
    from app.models.sla_policy import SLAPolicy
    ticket_ids = [r[0] for r in db.query(Ticket.id).filter(Ticket.merchant_id == merchant_id).all()]
    if ticket_ids:
        db.query(TicketComment).filter(TicketComment.ticket_id.in_(ticket_ids)).delete(synchronize_session=False)
        db.query(TicketAssignment).filter(TicketAssignment.ticket_id.in_(ticket_ids)).delete(synchronize_session=False)
        db.query(Ticket).filter(Ticket.merchant_id == merchant_id).delete(synchronize_session=False)
    db.query(TCat).filter(TCat.merchant_id == merchant_id).update({"parent_id": None}, synchronize_session=False)
    db.query(TCat).filter(TCat.merchant_id == merchant_id).delete(synchronize_session=False)
    db.query(SM).filter(SM.group_id.in_(
        db.query(SG.id).filter(SG.merchant_id == merchant_id).subquery()
    )).delete(synchronize_session=False)
    db.query(SG).filter(SG.merchant_id == merchant_id).delete(synchronize_session=False)
    db.query(SLAPolicy).filter(SLAPolicy.merchant_id == merchant_id).delete(synchronize_session=False)
    shop_ids = [r[0] for r in db.query(PlatformShop.id)
                .filter(PlatformShop.merchant_id == merchant_id).all()]
    if shop_ids:
        conv_ids = [r[0] for r in db.query(Conversation.id).filter(Conversation.shop_id.in_(shop_ids)).all()]
        if conv_ids:
            db.query(AISuggestionLog).filter(AISuggestionLog.conversation_id.in_(conv_ids)).delete(synchronize_session=False)
        db.query(Conversation).filter(Conversation.shop_id.in_(shop_ids)).delete(synchronize_session=False)
        db.query(ExternalOrder).filter(ExternalOrder.shop_id.in_(shop_ids)).delete(synchronize_session=False)
        db.query(ExternalProduct).filter(ExternalProduct.shop_id.in_(shop_ids)).delete(synchronize_session=False)
        # 也清理协同过滤和推荐规则
        from app.models.product_co_purchase import ProductCoPurchase
        from app.models.product_recommendation_rule import ProductRecommendationRule
        db.query(ProductCoPurchase).filter(ProductCoPurchase.product_id.in_(
            db.query(ExternalProduct.id).filter(ExternalProduct.shop_id.in_(shop_ids)).subquery()
        )).delete(synchronize_session=False)
        db.query(ProductRecommendationRule).filter(ProductRecommendationRule.merchant_id == merchant_id).delete(synchronize_session=False)
    db.query(PlatformShop).filter(PlatformShop.merchant_id == merchant_id).delete(synchronize_session=False)
    # 先清空 parent_id 再删分类（避免 self-referential FK）
    db.query(Category).filter(Category.merchant_id == merchant_id).update({"parent_id": None}, synchronize_session=False)
    db.query(Category).filter(Category.merchant_id == merchant_id).delete(synchronize_session=False)
    # 清理买家画像
    from app.models.buyer_profile import BuyerProfile
    db.query(BuyerProfile).filter(BuyerProfile.merchant_id == merchant_id).delete(synchronize_session=False)
    db.flush()


TICKET_CATS = [
    (None, "售后"), (None, "物流"), (None, "咨询"),
    ("售后", "退货退款"), ("售后", "换货"), ("售后", "质量问题"),
    ("物流", "未收到货"), ("物流", "物流延迟"), ("物流", "错发漏发"),
    ("咨询", "商品咨询"), ("咨询", "售后政策"),
]

TICKET_TITLES = [
    ("退货退款", "买家要求退货退款", "P2", "买家收到商品后不满意，要求全额退款"),
    ("换货", "尺寸不对需要换货", "P2", "买家表示买大了，想换小一码"),
    ("质量问题", "收到商品有划痕", "P1", "买家开箱后发现屏幕有轻微划痕"),
    ("未收到货", "物流一直没有更新", "P1", "5天过去了物流状态未更新"),
    ("物流延迟", "物流显示已签收但未收到", "P0", "买家称物流显示签收但本人未收到"),
    ("商品咨询", "商品材质询问", "P3", "买家想确认面料成分"),
    ("退货退款", "少发货了一件", "P1", "订单包含3件商品，只收到2件"),
    ("质量投诉", "用了三天就坏了", "P0", "买家电用了三天就坏，买家情绪激动"),
    ("快递破损", "包裹破损拒收", "P1", "快递送来的外包装破损严重"),
    ("退货退款", "收到空包裹", "P0", "买家声称开箱是空的，要求平台介入"),
]


def seed_tickets(db, merchant_id: int, usernames: list) -> int:
    """种子工单数据：分类树 + 技能组 + SLA + 工单。"""
    from app.models.ticket_category import TicketCategory
    from app.models.ticket import Ticket
    from app.models.ticket_comment import TicketComment
    from app.models.skill_group import SkillGroup, SkillMember
    from app.models.sla_policy import SLAPolicy
    from app.models.merchant_user import MerchantUser

    # 工单分类
    cat_map = {}
    for parent_name, name in TICKET_CATS:
        parent_id = cat_map.get(parent_name) if parent_name else None
        c = TicketCategory(merchant_id=merchant_id, name=name, parent_id=parent_id,
                           level=2 if parent_name else 1, sort_order=len(cat_map))
        db.add(c)
        db.flush()
        cat_map[name] = c.id

    # 技能组
    users = db.query(MerchantUser).filter(MerchantUser.merchant_id == merchant_id).all()
    uid_map = {u.username: u.id for u in users}
    groups = [
        ("售后处理组", "处理退货退款/换货/质量投诉", ["service"], ["精通售后流程", "擅长安抚情绪"]),
        ("物流对接组", "处理物流查询/破损/丢失", ["service", "manager"], ["熟悉各家快递"]),
        ("技术维修组", "处理商品故障/维修咨询", [], []),
    ]
    for gname, gdesc, member_usernames, _tags in groups:
        g = SkillGroup(merchant_id=merchant_id, name=gname, description=gdesc)
        db.add(g)
        db.flush()
        for uname in member_usernames:
            if uname in uid_map:
                db.add(SkillMember(group_id=g.id, user_id=uid_map[uname],
                                    skill_tags="，".join(_tags)))

    # SLA
    slas = [("P0", 15, 240), ("P1", 60, 1440), ("P2", 240, 4320), ("P3", 1440, 10080)]
    for pri, resp, resv in slas:
        db.add(SLAPolicy(merchant_id=merchant_id, priority=pri, response_minutes=resp, resolve_minutes=resv))

    # 工单
    service_id = uid_map.get("service")
    admin_id = uid_map.get("admin")
    ticket_count = 0
    convs = db.query(Conversation).filter(Conversation.shop_id.in_(
        db.query(PlatformShop.id).filter(PlatformShop.merchant_id == merchant_id).subquery()
    )).all()
    conv_ids = [c.id for c in convs] if convs else []
    orders = db.query(ExternalOrder).filter(ExternalOrder.shop_id.in_(
        db.query(PlatformShop.id).filter(PlatformShop.merchant_id == merchant_id).subquery()
    )).all()
    order_ids = [o.id for o in orders] if orders else []

    for i, (cat_name, title, priority, desc) in enumerate(TICKET_TITLES):
        seq = i + 1
        ticket_no = f"TK-{merchant_id}-{seq:05d}"
        source = "conversation" if conv_ids and i % 2 == 0 else "order" if order_ids else "manual"
        source_id = conv_ids[i % len(conv_ids)] if source == "conversation" and conv_ids else (
            order_ids[i % len(order_ids)] if source == "order" and order_ids else None)
        buyer = orders[i % len(order_ids)].buyer_openid if order_ids and source == "order" else None
        statuses = ["pending", "pending", "pending", "in_progress", "in_progress", "waiting_customer",
                    "resolved", "closed", "pending", "in_progress"]
        t = Ticket(
            merchant_id=merchant_id, ticket_no=ticket_no, title=f"[{cat_name}] {title}",
            description=desc, category_id=cat_map.get(cat_name), priority=priority,
            status=statuses[i % len(statuses)], source=source, source_id=source_id,
            buyer_openid=buyer, assigned_to=service_id if statuses[i % len(statuses)] != "pending" else None,
            created_by=admin_id, ticket_tags=["#种子数据"] if i < 5 else None,
            sla_due_at=datetime.now() + timedelta(hours=random.randint(1, 48)) if i % 3 != 0 else None,
        )
        db.add(t)
        db.flush()
        # 评论
        for j in range(random.randint(1, 4)):
            internal = j == 0
            db.add(TicketComment(ticket_id=t.id, user_id=service_id or admin_id,
                                 content=f"内部备注: 问题正在跟进中" if internal else f"{'客服' if j==0 else '买家'}: {random.choice(['您好','请问','谢谢','好的','已经处理了','麻烦看一下'])}",
                                 is_internal=1 if internal else 0))
        ticket_count += 1
    return ticket_count


def build_categories(db, merchant_id: int):
    """从 external_products.category_path 解析生成分类树。"""
    cat_paths = set()
    products = db.query(ExternalProduct.category_path).filter(
        ExternalProduct.shop_id.in_(
            db.query(PlatformShop.id).filter(PlatformShop.merchant_id == merchant_id).subquery()
        )
    ).all()
    for (cp,) in products:
        if cp:
            parts = cp.split("/")
            for depth in range(len(parts)):
                cat_paths.add("/".join(parts[:depth + 1]))

    # 按层级插入，记录 name→id 映射
    name_to_id = {}
    sort_order = 0
    for path in sorted(cat_paths, key=lambda x: (x.count("/"), x)):
        parts = path.split("/")
        name = parts[-1]
        level = len(parts)
        parent_name = "/".join(parts[:-1]) if level > 1 else None
        parent_id = name_to_id.get(parent_name) if parent_name else None
        if path not in name_to_id:
            cat = Category(
                merchant_id=merchant_id, name=name, parent_id=parent_id,
                level=level, sort_order=sort_order,
            )
            db.add(cat)
            db.flush()
            name_to_id[path] = cat.id
            sort_order += 1
    return len(name_to_id)


async def seed():
    Base.metadata.create_all(bind=engine, checkfirst=True)
    connector = MockPlatformConnector()
    db = SessionLocal()
    try:
        # 清理旧数据（先删子表再删商户）
        existing = db.query(Merchant).all()
        for em in existing:
            clear_business_data(db, em.id)
            db.query(MerchantUser).filter(MerchantUser.merchant_id == em.id).delete()
        db.flush()
        # 清理可能残留的跨商户 FK 数据
        from app.models.service_mode import ServiceModeConfig, AutoReplyLog
        from app.models.ai_suggestion_log import AISuggestionLog
        from app.kb.models import KbDocument, KbChunk, KbConversation, KbMessage
        db.query(AutoReplyLog).delete()
        db.query(ServiceModeConfig).delete()
        db.query(AISuggestionLog).delete()
        db.query(KbMessage).delete()
        db.query(KbChunk).delete()
        db.query(KbDocument).delete()
        db.query(KbConversation).delete()
        db.flush()
        for em in existing:
            db.query(Merchant).filter(Merchant.id == em.id).delete()
        db.commit()

        merchant_entries = seed_multi_merchants(db)

        for mid, cfg in merchant_entries:
            reset_users(db, mid)

            total_products = total_convs = total_orders = 0
            vmall_shop_id = None

            # vmall 店铺
            vmall = cfg["vmall"]
            vmall_shop = PlatformShop(
                merchant_id=mid,
                platform_type="vmall",
                shop_name=vmall["shop_name"],
                shop_url="http://127.0.0.1:8020",
                sync_status="idle",
                is_active=1,
                bind_status=vmall["bind_status"],
            )
            if vmall["bind_status"] == "idle":
                import secrets
                vmall_shop.bind_token = secrets.token_urlsafe(24)
            db.add(vmall_shop)
            db.flush()
            vmall_shop_id = vmall_shop.id

            # mock 店铺
            for shop_cfg in cfg["mocks"]:
                shop = PlatformShop(
                    merchant_id=mid,
                    platform_type=shop_cfg["platform_type"],
                    shop_name=shop_cfg["shop_name"],
                    shop_url=shop_cfg["shop_url"],
                    sync_status="idle",
                    last_sync_at=datetime.now(),
                    is_active=1,
                )
                db.add(shop)
                db.flush()

                products = await connector.fetch_products(shop.id)
                product_ids = []
                for p in products:
                    obj = ExternalProduct(
                        shop_id=shop.id,
                        platform_product_id=p["platform_product_id"],
                        title=p["title"],
                        price=p["price"],
                        stock=p["stock"],
                        description=p["description"],
                        images_json=p["images_json"],
                        category_path=p["category_path"],
                        status=p["status"],
                        last_sync_at=p["last_sync_at"],
                    )
                    db.add(obj)
                    db.flush()
                    product_ids.append(obj.id)
                total_products += len(products)

                convs = await connector.get_conversations(shop.id)
                for c in convs:
                    db.add(Conversation(
                        shop_id=shop.id,
                        platform_conversation_id=c["platform_conversation_id"],
                        product_id=random.choice(product_ids) if product_ids else None,
                        buyer_nick=c["buyer_nick"],
                        messages_json=c["messages_json"],
                        last_message_at=c["last_message_at"],
                        handled_status=c["handled_status"],
                        assigned_to=None,
                    ))
                total_convs += len(convs)

                since = datetime.now() - timedelta(days=7)
                orders = await connector.fetch_orders(shop.id, since)
                for o in orders:
                    db.add(ExternalOrder(
                        shop_id=shop.id,
                        platform_order_id=o["platform_order_id"],
                        buyer_openid=o["buyer_openid"],
                        buyer_nick=o["buyer_nick"],
                        total_amount=o["total_amount"],
                        discount_amount=o["discount_amount"],
                        pay_amount=o["pay_amount"],
                        status=o["status"],
                        sku_details_json=o["sku_details_json"],
                        receiver_name=o["receiver_name"],
                        receiver_phone=o["receiver_phone"],
                        receiver_address=o["receiver_address"],
                        pay_time=o["pay_time"],
                        ship_time=o["ship_time"],
                        created_at=o["created_at"],
                    ))
                total_orders += len(orders)

            cat_count = build_categories(db, mid)
            ticket_count = seed_tickets(db, mid, [u["username"] for u in USERS])
            db.commit()

            print(f"商户: {cfg['name']} (id={mid}, vmall_shop={vmall_shop_id})")
            print(f"  店铺: vmall({vmall['bind_status']}) + mock×{len(cfg['mocks'])} | 商品: {total_products} | 会话: {total_convs} | 订单: {total_orders} | 分类: {cat_count} | 工单: {ticket_count}")

        print("=" * 48)
        print("多商户种子数据生成成功！")
        print("  商户1「数码旗舰商户」已绑定 vmall merchant01")
        print("  商户2「时尚女装商户」已绑定 vmall merchant02")
        print("  商户3「潮流美妆商户」待绑定 (idle)")
        print("  登录: admin/123456 (每个商户独立登录)")

        if "--backfill" in sys.argv or "--full" in sys.argv:
            full = "--full" in sys.argv
            print("\n开始向量回填（所有商户）...")
            for mid, cfg in merchant_entries:
                try:
                    from app.services.ai_suggest import backfill_all
                    result = backfill_all(db, mid, full_rebuild=full)
                    print(f"  [{cfg['name']}] 回填完成: {result['total_vectors']} 向量")
                except Exception as e:
                    print(f"  [{cfg['name']}] 回填失败: {e}")
            print("[OK] 向量回填完成")

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(seed())
