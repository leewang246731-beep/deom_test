"""
京东开放平台连接器
Demo 模式使用 Mock 数据模拟京东 API 返回，字段对齐 ORM 模型。
"""
import random
from datetime import datetime, timedelta
from typing import List

from faker import Faker

from .base import PlatformConnector

_JD_PRODUCTS = [
    ("【京东自营】联想ThinkPad X1 Carbon 商务本", "电脑办公/笔记本/联想", (6999, 12999)),
    ("京东超市 金龙鱼花生油 5L", "食品饮料/粮油/花生油", (89, 149)),
    ("【京东自营】戴森V15吸尘器无绳", "家用电器/吸尘器/戴森", (2999, 4999)),
    ("海澜之家男士商务衬衫", "男装/衬衫/商务", (199, 399)),
    ("【京东自营】Apple iPhone 17 Pro", "手机通讯/苹果手机/iPhone", (7999, 10999)),
    ("良品铺子零食大礼包", "食品饮料/休闲零食/坚果", (69, 159)),
    ("【京东自营】海尔冰箱双开门", "家用电器/冰箱/海尔", (2999, 5999)),
    ("南极人男士内裤纯棉4条装", "男装/内衣/南极人", (49, 99)),
    ("【京东自营】飞利浦电动剃须刀", "个护健康/剃须刀/飞利浦", (299, 799)),
    ("苏泊尔电饭煲智能IH", "家用电器/厨房电器/苏泊尔", (399, 899)),
    ("【京东自营】惠普打印机家用", "电脑办公/打印机/惠普", (499, 1299)),
    ("三只松鼠坚果礼盒装", "食品饮料/坚果炒货/礼盒", (99, 259)),
    ("【京东自营】格力空调1.5匹", "家用电器/空调/格力", (2599, 4299)),
    ("小米电视65寸4K全面屏", "家用电器/电视/小米", (2999, 4999)),
    ("蓝月亮洗衣液套装", "清洁用品/洗衣液/蓝月亮", (49, 99)),
]


class JdConnector(PlatformConnector):
    """京东开放平台连接器。Demo 模式生成京东风格模拟数据。"""

    def __init__(self, app_key: str = "", app_secret: str = "", access_token: str = ""):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token
        self.fake = Faker("zh_CN")

    async def fetch_products(self, shop_id: int) -> List[dict]:
        products = []
        for i in range(50):
            tpl = _JD_PRODUCTS[i % len(_JD_PRODUCTS)]
            title, cat, price_range = tpl
            price = round(random.uniform(*price_range), 2)
            products.append({
                "platform_product_id": f"JD{shop_id}{i:05d}",
                "title": title,
                "price": price,
                "stock": random.randint(0, 500),
                "description": f"京东品质保障：{title}，正品行货，211限时达。",
                "images_json": [f"https://img.jd.com/sku/{shop_id}_{i}_{n}.jpg" for n in range(3)],
                "category_path": cat,
                "status": 1 if random.random() > 0.06 else 0,
                "last_sync_at": datetime.now(),
            })
        return products

    async def fetch_orders(self, shop_id: int, start_time: datetime) -> List[dict]:
        orders = []
        statuses = ["pending"] * 12 + ["paid"] * 28 + ["shipped"] * 35 + ["completed"] * 20 + ["refunding"] * 3 + ["refunded"] * 2
        for i in range(100):
            tpl = _JD_PRODUCTS[i % len(_JD_PRODUCTS)]
            title, _cat, price_range = tpl
            qty = random.randint(1, 3)
            unit_price = round(random.uniform(*price_range), 2)
            total = round(unit_price * qty, 2)
            discount = round(total * random.choice([0, 0, 0.05]), 2)
            pay_amount = round(total - discount, 2)
            status = statuses[i % len(statuses)]
            created = start_time + timedelta(seconds=random.randint(0, max(1, int((datetime.now() - start_time).total_seconds()))))
            pay_time = created + timedelta(minutes=random.randint(1, 30)) if status != "pending" else None
            ship_time = pay_time + timedelta(hours=random.randint(1, 24)) if status in ("shipped", "completed") and pay_time else None
            orders.append({
                "platform_order_id": f"JD{shop_id}{i:06d}",
                "buyer_openid": f"jd_pin_{shop_id}_{i}",
                "buyer_nick": self.fake.name(),
                "total_amount": total,
                "discount_amount": discount,
                "pay_amount": pay_amount,
                "status": status,
                "sku_details_json": [{"title": title, "price": unit_price, "qty": qty}],
                "product_title": title,
                "receiver_name": self.fake.name(),
                "receiver_phone": self.fake.phone_number(),
                "receiver_address": self.fake.address().replace("\n", " "),
                "pay_time": pay_time,
                "ship_time": ship_time,
                "created_at": created,
            })
        return orders

    async def send_message(self, shop_id: int, buyer_openid: str, content: str) -> bool:
        return True

    async def get_conversations(self, shop_id: int) -> List[dict]:
        questions = [
            ("商品咨询", "这款电脑是什么配置？i5还是i7？"),
            ("物流", "京东自营的是不是明天就能到？"),
            ("售后", "买了两个月出现质量问题怎么保修？"),
            ("价格", "最近有优惠活动吗？能不能便宜点？"),
            ("安装", "空调包安装吗？需要额外收费吗？"),
            ("发票", "能开增值税专用发票吗？"),
        ]
        conversations = []
        for i in range(30):
            qtype, buyer_q = questions[i % len(questions)]
            buyer_nick = self.fake.name()
            base = datetime.now() - timedelta(hours=random.randint(0, 72))
            msgs = [
                {"role": "buyer", "content": buyer_q, "time": base.strftime("%Y-%m-%d %H:%M:%S")},
                {"role": "service", "content": "亲，您好，京东自营正品行货，我帮您核实一下～", "time": (base + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")},
            ]
            handled = random.choice(["pending", "replied", "closed"])
            conversations.append({
                "platform_conversation_id": f"JD_MSG{shop_id}{i:05d}",
                "buyer_nick": buyer_nick,
                "messages_json": msgs,
                "last_message_at": base + timedelta(minutes=2),
                "handled_status": handled,
            })
        return conversations
