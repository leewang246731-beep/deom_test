"""
淘宝开放平台连接器
Demo 模式使用 Mock 数据模拟淘宝 API 返回，字段对齐 ORM 模型。
"""
import random
from datetime import datetime, timedelta
from typing import List

from faker import Faker

from .base import PlatformConnector

_TB_PRODUCTS = [
    ("韩版宽松卫衣女潮牌ins", "女装/卫衣/韩版", (69, 199)),
    ("男士商务休闲皮带真皮", "男装/配饰/皮带", (89, 299)),
    ("2025新款潮流运动鞋男", "鞋靴/运动鞋/男款", (159, 459)),
    ("女士小香风外套短款", "女装/外套/小香风", (259, 599)),
    ("大容量双肩包旅行背包", "箱包/双肩包/旅行", (99, 259)),
    ("儿童益智积木拼装玩具", "母婴/玩具/积木", (49, 149)),
    ("车载手机支架无线充电", "汽车用品/支架/充电", (69, 199)),
    ("不锈钢保温杯大容量", "家居/杯具/保温杯", (39, 129)),
    ("防蓝光眼镜电脑护目镜", "配饰/眼镜/防蓝光", (59, 189)),
    ("瑜伽垫加厚防滑运动垫", "运动户外/瑜伽/垫子", (49, 159)),
    ("真无线蓝牙耳机降噪", "数码/耳机/蓝牙", (129, 399)),
    ("复古石英表女士小方表", "手表/女表/石英", (199, 599)),
    ("纯棉四件套全棉床品", "家居/床品/四件套", (199, 499)),
    ("电动牙刷成人声波清洁", "个护/口腔/牙刷", (89, 299)),
    ("螺蛳粉广西柳州正宗", "食品/速食/螺蛳粉", (29, 79)),
]


class TaobaoConnector(PlatformConnector):
    """淘宝开放平台连接器。Demo 模式生成淘宝风格模拟数据。"""

    def __init__(self, app_key: str = "", app_secret: str = "", access_token: str = ""):
        self.app_key = app_key
        self.app_secret = app_secret
        self.access_token = access_token
        self.fake = Faker("zh_CN")

    async def fetch_products(self, shop_id: int) -> List[dict]:
        products = []
        for i in range(50):
            tpl = _TB_PRODUCTS[i % len(_TB_PRODUCTS)]
            title, cat, price_range = tpl
            price = round(random.uniform(*price_range), 2)
            products.append({
                "platform_product_id": f"TB{shop_id}{i:05d}",
                "title": title,
                "price": price,
                "stock": random.randint(0, 999),
                "description": f"淘宝热销商品：{title}，品质保证，七天无理由退换。",
                "images_json": [f"https://img.alicdn.com/imgextra/{shop_id}/{i}_{n}.jpg" for n in range(3)],
                "category_path": cat,
                "status": 1 if random.random() > 0.08 else 0,
                "last_sync_at": datetime.now(),
            })
        return products

    async def fetch_orders(self, shop_id: int, start_time: datetime) -> List[dict]:
        orders = []
        statuses = ["pending"] * 15 + ["paid"] * 30 + ["shipped"] * 30 + ["completed"] * 20 + ["refunding"] * 3 + ["refunded"] * 2
        for i in range(100):
            tpl = _TB_PRODUCTS[i % len(_TB_PRODUCTS)]
            title, _cat, price_range = tpl
            qty = random.randint(1, 4)
            unit_price = round(random.uniform(*price_range), 2)
            total = round(unit_price * qty, 2)
            discount = round(total * random.choice([0, 0, 0, 0.08]), 2)
            pay_amount = round(total - discount, 2)
            status = statuses[i % len(statuses)]
            created = start_time + timedelta(seconds=random.randint(0, max(1, int((datetime.now() - start_time).total_seconds()))))
            pay_time = created + timedelta(minutes=random.randint(1, 60)) if status != "pending" else None
            ship_time = pay_time + timedelta(hours=random.randint(2, 48)) if status in ("shipped", "completed") and pay_time else None
            orders.append({
                "platform_order_id": f"TB{shop_id}{i:06d}",
                "buyer_openid": f"tb_openid_{shop_id}_{i}",
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
            ("尺码", "亲，这件卫衣我160穿S会不会太大？"),
            ("快递", "今天拍的话什么时候能发货？"),
            ("质量", "这件起球吗？会掉色吗？"),
            ("尺码", "鞋子偏码吗？我平时38码。"),
            ("快递", "能发顺丰到付吗？"),
            ("售后", "收到的有点色差想退一下。"),
        ]
        conversations = []
        for i in range(30):
            qtype, buyer_q = questions[i % len(questions)]
            buyer_nick = self.fake.name()
            base = datetime.now() - timedelta(hours=random.randint(0, 72))
            msgs = [
                {"role": "buyer", "content": buyer_q, "time": base.strftime("%Y-%m-%d %H:%M:%S")},
                {"role": "service", "content": "亲，感谢您的咨询，马上为您查看～", "time": (base + timedelta(minutes=1)).strftime("%Y-%m-%d %H:%M:%S")},
            ]
            handled = random.choice(["pending", "replied", "closed"])
            conversations.append({
                "platform_conversation_id": f"TB_MSG{shop_id}{i:05d}",
                "buyer_nick": buyer_nick,
                "messages_json": msgs,
                "last_message_at": base + timedelta(minutes=2),
                "handled_status": handled,
            })
        return conversations
