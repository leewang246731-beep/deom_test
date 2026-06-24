"""
vMall 种子脚本 — 幂等可重复运行
50 商品 + 55 订单 + 45 物流(覆盖6状态+异常) + 10 会话 + 话术模板
"""
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, ".")
from app.database.session import SessionLocal, engine, Base
import app.models
from app.core.security import hash_password

PRODUCTS = [
    # 数码 — 手机
    ("华为 Mate70 Pro", "数码/手机", 6999, 8999, "麒麟芯片，超光变影像", [{"spec": "曜石黑", "price": 6999, "stock": 15}, {"spec": "冰霜银", "price": 7499, "stock": 10}]),
    ("iPhone 16 Pro Max", "数码/手机", 8999, 10999, "A18 Pro芯片，钛金属设计", [{"spec": "深空黑256G", "price": 8999, "stock": 20}, {"spec": "银色512G", "price": 10499, "stock": 8}]),
    ("小米 15 Ultra", "数码/手机", 4999, 6999, "徕卡光学镜头，骁龙旗舰平台", [{"spec": "黑色12+256", "price": 4999, "stock": 25}, {"spec": "白色16+512", "price": 6499, "stock": 12}]),
    ("OPPO Find X8 Pro", "数码/手机", 5299, 6799, "哈苏人像，天玑旗舰芯", [{"spec": "蓝色", "price": 5299, "stock": 18}, {"spec": "白色", "price": 5999, "stock": 10}]),
    ("vivo X200 Pro", "数码/手机", 4999, 6499, "蔡司超级长焦", [{"spec": "深灰", "price": 4999, "stock": 14}, {"spec": "浅蓝", "price": 5799, "stock": 9}]),
    ("Apple AirPods Pro 2", "数码/耳机", 1699, 1899, "主动降噪，空间音频", [{"spec": "白色", "price": 1699, "stock": 30}]),
    ("索尼 WH-1000XM5", "数码/耳机", 2499, 2899, "旗舰降噪，30小时续航", [{"spec": "黑色", "price": 2499, "stock": 12}, {"spec": "银色", "price": 2599, "stock": 8}]),
    ("华为 FreeBuds Pro 3", "数码/耳机", 1299, 1499, "智慧动态降噪", [{"spec": "白色", "price": 1299, "stock": 22}]),
    ("三星 Galaxy Buds3 Pro", "数码/耳机", 1499, 1699, "智能ANC，360空间音频", [{"spec": "银色", "price": 1499, "stock": 10}]),
    ("漫步者 NeoBuds Pro 3", "数码/耳机", 599, 799, "Hi-Res认证，圈铁混合", [{"spec": "黑色", "price": 599, "stock": 35}]),
    ("小米手环 9", "数码/穿戴", 249, 399, "血氧心率监测，14天续航", [{"spec": "黑色", "price": 249, "stock": 50}, {"spec": "蓝色", "price": 299, "stock": 40}]),
    ("Apple Watch Ultra 2", "数码/穿戴", 6499, 7999, "钛金属表壳，双频GPS", [{"spec": "49mm高山回环", "price": 6499, "stock": 5}]),
    ("华为 Watch GT 5", "数码/穿戴", 1488, 1988, "玄玑感知系统", [{"spec": "46mm黑色", "price": 1488, "stock": 15}]),
    ("MacBook Pro 16 M4 Max", "数码/笔记本", 19999, 28999, "M4 Max芯片", [{"spec": "深空黑36G/1T", "price": 19999, "stock": 4}, {"spec": "银色48G/2T", "price": 27499, "stock": 2}]),
    ("ThinkPad X1 Carbon Gen12", "数码/笔记本", 9999, 14999, "酷睿Ultra，1.09kg", [{"spec": "i7-16G/512G", "price": 9999, "stock": 10}]),
    ("华为 MateBook X Pro 2025", "数码/笔记本", 11999, 14999, "3.1K OLED原色屏", [{"spec": "砚黑32G/1T", "price": 11999, "stock": 8}]),
    ("ROG 枪神8 Plus", "数码/笔记本", 12999, 18999, "i9+RTX4070,240Hz", [{"spec": "黑色32G/1T", "price": 12999, "stock": 5}]),
    ("联想 YOGA Pro 14s", "数码/笔记本", 6999, 8999, "3K 120Hz触控屏", [{"spec": "深灰16G/512G", "price": 6999, "stock": 12}]),
    # 女装
    ("法式复古碎花连衣裙", "女装/连衣裙", 199, 399, "收腰显瘦，雪纺面料", [{"spec": "S码", "price": 199, "stock": 20}, {"spec": "M码", "price": 199, "stock": 25}, {"spec": "L码", "price": 199, "stock": 18}, {"spec": "XL码", "price": 219, "stock": 12}]),
    ("韩版宽松针织开衫", "女装/针织衫", 129, 259, "慵懒风外搭，加厚不起球", [{"spec": "均码米色", "price": 129, "stock": 30}, {"spec": "均码深灰", "price": 129, "stock": 25}]),
    ("高腰直筒牛仔裤", "女装/裤装", 159, 299, "显腿长弹力舒适", [{"spec": "黑色27", "price": 159, "stock": 15}, {"spec": "蓝色29", "price": 159, "stock": 22}]),
    ("羊毛混纺双面呢大衣", "女装/外套", 599, 999, "气质通勤，含羊毛", [{"spec": "S驼色", "price": 599, "stock": 8}, {"spec": "M黑色", "price": 599, "stock": 10}]),
    ("真丝吊带睡裙", "女装/家居服", 299, 499, "桑蚕丝亲肤", [{"spec": "均码香槟金", "price": 299, "stock": 18}]),
    ("冰丝防晒衬衫", "女装/衬衫", 169, 299, "UPF50+防晒", [{"spec": "白色S", "price": 169, "stock": 28}, {"spec": "蓝色M", "price": 169, "stock": 22}]),
    ("显瘦百褶半身裙", "女装/半裙", 139, 259, "A字版型，中长款", [{"spec": "黑色S", "price": 139, "stock": 20}, {"spec": "卡其M", "price": 139, "stock": 15}]),
    ("运动瑜伽裤", "女装/运动", 89, 189, "高腰提臀，裸感面料", [{"spec": "石墨灰S", "price": 89, "stock": 40}, {"spec": "黑色M", "price": 89, "stock": 45}]),
    ("纯棉圆领T恤", "女装/T恤", 59, 129, "新疆长绒棉", [{"spec": "白色M", "price": 59, "stock": 60}, {"spec": "黑色L", "price": 59, "stock": 50}]),
    ("复古格子短外套", "女装/外套", 259, 459, "英伦风通勤百搭", [{"spec": "棕色M", "price": 259, "stock": 12}, {"spec": "灰色L", "price": 279, "stock": 8}]),
    # 美妆
    ("兰蔻小黑瓶精华套装", "美妆/护肤", 1080, 1680, "修护肌底，提亮肤色", [{"spec": "50ml礼盒", "price": 1080, "stock": 15}, {"spec": "100ml限量", "price": 1580, "stock": 8}]),
    ("YSL圣罗兰口红礼盒", "美妆/彩妆", 680, 980, "经典正红显白", [{"spec": "小金条N21", "price": 380, "stock": 25}, {"spec": "圆管12#", "price": 350, "stock": 20}]),
    ("雅诗兰黛小棕瓶眼霜", "美妆/护肤", 480, 680, "淡化细纹，紧致眼周", [{"spec": "15ml", "price": 480, "stock": 20}]),
    ("海蓝之谜面霜", "美妆/护肤", 1680, 2880, "经典修护，深海奇迹", [{"spec": "30ml", "price": 1680, "stock": 5}, {"spec": "60ml", "price": 2680, "stock": 3}]),
    ("资生堂红腰子精华", "美妆/护肤", 680, 890, "焕活肌肤，提亮淡斑", [{"spec": "50ml", "price": 680, "stock": 12}]),
    # 食品
    ("坚果大礼包零食组合", "食品/零食", 89, 159, "每日坚果独立包装", [{"spec": "经典1.2kg", "price": 89, "stock": 100}, {"spec": "豪华2.0kg", "price": 149, "stock": 60}]),
    ("特级新疆和田大枣", "食品/干货", 69, 129, "肉厚核小，自然甜", [{"spec": "500g", "price": 69, "stock": 80}]),
    ("云南普洱茶饼礼盒", "食品/茶叶", 199, 599, "古树春料，越陈越香", [{"spec": "357g生普", "price": 199, "stock": 30}, {"spec": "357g熟普", "price": 299, "stock": 25}]),
    ("五常大米5kg", "食品/粮油", 69, 99, "正宗五常产地", [{"spec": "5kg真空装", "price": 69, "stock": 120}]),
    ("每日鲜语纯牛奶×12", "食品/乳品", 59, 89, "蛋白质3.6g，牧场直供", [{"spec": "250ml×12盒", "price": 59, "stock": 200}]),
    # 家居
    ("北欧简约乳胶枕", "家居/床品", 129, 259, "泰国进口乳胶", [{"spec": "标准款", "price": 129, "stock": 40}, {"spec": "按摩款", "price": 199, "stock": 30}]),
    ("加湿器香薰一体机", "家居/电器", 159, 329, "静音大雾量", [{"spec": "白色3L", "price": 159, "stock": 25}]),
    ("北欧风陶瓷餐具套装", "家居/厨房", 199, 399, "釉下彩工艺，微波可用", [{"spec": "28头", "price": 199, "stock": 15}, {"spec": "42头", "price": 359, "stock": 8}]),
    ("智能扫地机器人S10", "家居/电器", 1999, 2999, "激光导航扫拖一体", [{"spec": "标准版", "price": 1999, "stock": 10}, {"spec": "Pro版", "price": 2899, "stock": 5}]),
    ("全棉四件套", "家居/床品", 199, 499, "100支长绒棉", [{"spec": "1.5m灰色", "price": 199, "stock": 25}, {"spec": "1.8m蓝色", "price": 299, "stock": 20}]),
    ("日式收纳箱6件套", "家居/收纳", 99, 199, "可折叠大容量", [{"spec": "浅灰6件", "price": 99, "stock": 50}]),
    ("智能马桶盖", "家居/卫浴", 899, 1999, "即热冲洗暖风烘干", [{"spec": "标准版", "price": 899, "stock": 8}, {"spec": "旗舰版", "price": 1899, "stock": 4}]),
    ("升降办公桌", "家居/办公", 1299, 2599, "电动升降记忆高度", [{"spec": "白色120cm", "price": 1299, "stock": 6}, {"spec": "黑色140cm", "price": 1599, "stock": 4}]),
    ("全身落地穿衣镜", "家居/装饰", 199, 399, "铝合金边框高清银镜", [{"spec": "金色150cm", "price": 199, "stock": 15}]),
    ("空气循环扇", "家居/电器", 249, 499, "3D摇头四季通用", [{"spec": "白色", "price": 249, "stock": 30}]),
    ("乳胶床垫1.8m", "家居/床品", 1599, 2999, "泰国进口，七区独立弹簧", [{"spec": "1.8m标准", "price": 1599, "stock": 8}]),
]


def seed():
    Base.metadata.create_all(bind=engine, checkfirst=True)
    db = SessionLocal()
    try:
        from app.models.vm_logistics import VmLogistics, VmLogisticsTrack, VmLogisticsScriptTemplate
        from app.models.vm_message import VmMessage
        from app.models.vm_conversation import VmConversation
        from app.models.vm_after_sale import VmAfterSale
        from app.models.vm_order_item import VmOrderItem
        from app.models.vm_order import VmOrder
        from app.models.vm_product import VmProduct
        from app.models.vm_buyer import VmBuyer
        from app.models.vm_platform_setting import VmPlatformSetting, VmPlatformAdmin
        from app.models.vm_wallet import VmWallet, VmWalletTransaction
        from app.services.fake_logistics import generate_node_data, generate_courier

        # FK-safe cleanup order
        db.query(VmWalletTransaction).delete()
        db.query(VmWallet).delete()
        db.query(VmLogisticsTrack).delete()
        db.query(VmLogisticsScriptTemplate).delete()
        db.query(VmLogistics).delete()
        db.query(VmMessage).delete()
        db.query(VmConversation).delete()
        db.query(VmAfterSale).delete()
        db.query(VmOrderItem).delete()
        db.query(VmOrder).delete()
        db.query(VmProduct).delete()
        db.query(VmBuyer).delete()
        db.query(VmPlatformAdmin).delete()
        db.query(VmPlatformSetting).delete()
        db.commit()

        # ---- 平台配置 + 管理员 ----
        db.add(VmPlatformAdmin(username="admin_vmall", password_hash=hash_password("123456"),
                                display_name="平台管理员", role="admin"))
        db.add(VmPlatformSetting(shop_name="vMall官方旗舰店",
                                  access_token_secret="vmall-secret-key-change-in-production",
                                  saas_webhook_url="http://127.0.0.1:8010/api/v1/webhooks/vmall"))

        # ---- 买家 ----
        buyer = VmBuyer(username="buyer_test", password_hash=hash_password("123456"),
                        nickname="测试买家小明", phone="13800138000", source="h5")
        db.add(buyer); db.flush()
        # 钱包: 初始余额 500 元 + 一条充值记录
        wallet = VmWallet(buyer_id=buyer.id, balance=500.00, total_recharged=500.00, total_spent=0, status=1)
        db.add(wallet); db.flush()
        db.add(VmWalletTransaction(wallet_id=wallet.id, buyer_id=buyer.id, type="recharge",
                                    amount=500.00, balance_before=0, balance_after=500.00,
                                    remark="新用户注册赠送 500 元", order_no=None, operator_id=None))

        # ---- 50 商品 ----
        product_ids = []
        for title, cat, pmin, pmax, desc, skus in PRODUCTS:
            for sku in skus:
                sku["sku_code"] = f"SKU-{title[:6]}-{sku['spec'][:4]}-{random.randint(100,999)}"
            p = VmProduct(title=title, main_image=f"https://picsum.photos/seed/{len(product_ids)}/400/400",
                          price_min=pmin, price_max=pmax, category_path=cat, description=desc,
                          skus_json=skus, total_stock=sum(s["stock"] for s in skus),
                          total_sales=random.randint(0, 500))
            db.add(p); db.flush()
            product_ids.append(p.id)

        # ---- 55 订单: 5待付 + 5待发 + 45已发(覆盖物流各状态) ----
        order_ids = []
        # 前10个: 待付+待发
        for i in range(10):
            st = "pending_payment" if i < 5 else "paid"
            pid = random.choice(product_ids)
            p = db.query(VmProduct).get(pid)
            sku = random.choice(p.skus_json or [{"price": p.price_min, "stock": 1, "sku_code": "SKU-DEF", "spec": "默认"}])
            qty = random.randint(1, 2); amt = float(sku["price"]) * qty
            o = VmOrder(order_no=f"VM-{datetime.now().strftime('%y%m%d%H%M%S')}-{i:05d}",
                        buyer_id=buyer.id, total_amount=amt, pay_amount=amt, status=st,
                        receiver_name="小明", receiver_phone="13800138000",
                        receiver_address="江苏省南京市玄武区虚拟路1号",
                        pay_time=datetime.now() - timedelta(hours=random.randint(1, 48)) if st != "pending_payment" else None,
                        created_at=datetime.now() - timedelta(hours=random.randint(1, 72)))
            db.add(o); db.flush()
            db.add(VmOrderItem(order_id=o.id, product_id=pid, sku_code=sku["sku_code"], sku_spec=sku.get("spec", ""),
                                unit_price=float(sku["price"]), quantity=qty))
            order_ids.append(o.id)

        # 后45个: shipped/received/completed, 预分配物流状态
        log_plan = (["PICKED"] * 8 + ["IN_TRANSIT"] * 12 + ["OUT_FOR_DELIVERY"] * 10
                    + ["DELIVERED"] * 10 + ["FAILED"] * 3 + ["STUCK"] * 2)
        for i, log_status in enumerate(log_plan):
            pid = random.choice(product_ids)
            p = db.query(VmProduct).get(pid)
            sku = random.choice(p.skus_json or [{"price": p.price_min, "stock": 1, "sku_code": "SKU-DEF", "spec": "默认"}])
            qty = random.randint(1, 2); amt = float(sku["price"]) * qty
            order_stat = "received" if log_status == "DELIVERED" else "shipped"
            pay_t = datetime.now() - timedelta(hours=random.randint(24, 96))
            ship_t = pay_t + timedelta(hours=random.randint(2, 12))
            o = VmOrder(order_no=f"VM-{datetime.now().strftime('%y%m%d%H%M%S')}-{i+10:05d}",
                        buyer_id=buyer.id, total_amount=amt, pay_amount=amt, status=order_stat,
                        receiver_name="小明", receiver_phone="13800138000",
                        receiver_address="江苏省南京市玄武区虚拟路1号",
                        pay_time=pay_t, ship_time=ship_t,
                        created_at=datetime.now() - timedelta(hours=random.randint(48, 200)))
            db.add(o); db.flush()
            db.add(VmOrderItem(order_id=o.id, product_id=pid, sku_code=sku["sku_code"], sku_spec=sku.get("spec", ""),
                                unit_price=float(sku["price"]), quantity=qty))
            order_ids.append(o.id)

            # 物流
            co = random.choice(["顺丰速运", "中通快递", "圆通速递"])
            courier = generate_courier()
            tno = f"{'SF' if '顺丰' in co else 'ZTO' if '中通' in co else 'YTO'}{random.randint(1000000000,9999999999)}"
            log = VmLogistics(
                order_id=o.id, company=co, tracking_no=tno, status=log_status,
                status_label={"PICKED":"已揽收","IN_TRANSIT":"运输中","OUT_FOR_DELIVERY":"派送中",
                              "DELIVERED":"已签收","FAILED":"派送失败","STUCK":"异常滞留"}.get(log_status, log_status),
                estimated_days=random.randint(1, 5),
                exception_code=log_status if log_status in ("FAILED","STUCK") else None,
                exception_detail={"FAILED":"快递员联系不上买家","STUCK":"因天气原因滞留"}.get(log_status),
                courier_name=courier["name"], courier_phone=courier["phone"], current_city=courier["city"],
            )
            db.add(log); db.flush()

            # 历史轨迹
            tracks = []
            if log_status in ("PICKED", "IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"):
                nd = generate_node_data(log.id, "PICKED")
                tracks.append(VmLogisticsTrack(logistics_id=log.id, status_code="PICKED", node_name=nd["node_name"],
                                                node_desc=nd["node_desc"], node_time=ship_t, city=nd.get("city", ""),
                                                operator=nd.get("operator", ""), is_current=(log_status == "PICKED")))
            if log_status in ("IN_TRANSIT", "OUT_FOR_DELIVERY", "DELIVERED"):
                nd = generate_node_data(log.id, "IN_TRANSIT")
                tracks.append(VmLogisticsTrack(logistics_id=log.id, status_code="IN_TRANSIT", node_name=nd["node_name"],
                                                node_desc=nd["node_desc"], node_time=ship_t + timedelta(hours=6),
                                                city=nd.get("city", ""), is_current=(log_status == "IN_TRANSIT")))
            if log_status in ("OUT_FOR_DELIVERY", "DELIVERED"):
                nd = generate_node_data(log.id, "OUT_FOR_DELIVERY")
                tracks.append(VmLogisticsTrack(logistics_id=log.id, status_code="OUT_FOR_DELIVERY", node_name=nd["node_name"],
                                                node_desc=nd["node_desc"], node_time=ship_t + timedelta(hours=12),
                                                city=nd.get("city", ""), operator=nd.get("operator", ""),
                                                is_current=(log_status == "OUT_FOR_DELIVERY")))
            if log_status == "DELIVERED":
                nd = generate_node_data(log.id, "DELIVERED")
                tracks.append(VmLogisticsTrack(logistics_id=log.id, status_code="DELIVERED", node_name=nd["node_name"],
                                                node_desc=nd["node_desc"], node_time=ship_t + timedelta(hours=18),
                                                city=nd.get("city", ""), is_current=True))
            # 异常节点
            if log_status in ("FAILED", "STUCK"):
                nd = generate_node_data(log.id, log_status)
                tracks.append(VmLogisticsTrack(logistics_id=log.id, status_code=log_status, node_name=nd["node_name"],
                                                node_desc=nd["node_desc"], node_time=ship_t + timedelta(hours=18),
                                                city=nd.get("city", ""), is_current=True, is_exception=1))
            for t in tracks:
                db.add(t)

        # ---- 话术模板 ----
        for sc, tmpl in [
            ("PICKED", "亲，您的订单{order_no}已由{company}揽收，运单号{track_no}，预计{estimated}天送达~"),
            ("IN_TRANSIT", "您的包裹已到达{city}中转站，加速分拣中，预计{estimated}天送达❤️"),
            ("OUT_FOR_DELIVERY", "快递员{courier}({phone})正在派送，请保持电话畅通~"),
            ("DELIVERED", "您的包裹已签收，满意请给五星好评哦⭐"),
            ("FAILED", "亲，快递员反馈联系不上您({detail})，请确认联系方式或联系我们安排改址/自提"),
            ("STUCK", "您的包裹因{detail}滞留，已联系快递加急处理，抱歉🙏"),
        ]:
            db.add(VmLogisticsScriptTemplate(merchant_id=1, status_code=sc, script_template=tmpl, tone="warm", is_default=1))

        # ---- 10 条会话 ----
        for i in range(10):
            c = VmConversation(buyer_id=buyer.id, order_id=random.choice(order_ids) if i % 3 == 0 else None,
                               product_id=random.choice(product_ids), status="open" if i < 8 else "closed",
                               buyer_ip_region=random.choice(["江苏·南京", "浙江·杭州", "北京", "广东·深圳"]),
                               buyer_last_online=datetime.now() - timedelta(minutes=random.randint(1, 120)),
                               last_message_at=datetime.now() - timedelta(minutes=random.randint(1, 60)))
            db.add(c); db.flush()
            db.add(VmMessage(conversation_id=c.id, sender_role="buyer", msg_type="text",
                              content_json={"text": random.choice(["亲，有货吗？", "什么时候发货", "质量怎么样", "能便宜吗", "尺码偏大还是偏小"])}))
            if i < 6:
                db.add(VmMessage(conversation_id=c.id, sender_role="admin", msg_type="text",
                                  content_json={"text": random.choice(["亲，有货的~", "质量放心，正品授权", "建议拍大一码", "发中通，可补差价发顺丰"])}))

        db.commit()
        lc = db.query(VmLogistics).count()
        sc = db.query(VmLogisticsTrack).count()
        print(f"vMall 种子数据生成成功!")
        print(f"  管理员: admin_vmall / 123456  |  买家: buyer_test / 123456")
        print(f"  商品: {len(PRODUCTS)} | 订单: {len(order_ids)} | 物流: {lc}单/{sc}轨迹 | 会话: 10")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
