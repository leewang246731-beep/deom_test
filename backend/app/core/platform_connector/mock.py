"""
Mock 平台连接器
用 Faker(zh_CN) 在本地生成真实感中文演示数据，不发起任何外部网络请求。

数据规则（PHASE1-PLAN 步骤2 / modules.md M7）：
- fetch_products    每店铺 50 商品
- get_conversations 每店铺 30 会话（覆盖问尺码/快递/质量）
- fetch_orders      每店铺 100 订单（含多种状态，pending 供催单）
所有 dict 字段形状对齐 ORM 模型，可直接落库。
"""
import random
from datetime import datetime, timedelta
from typing import List

from faker import Faker

from .base import PlatformConnector

# ===== 商品模板库：真实感中文商品，供语义搜索演示 =====
# 每条：(标题, 分类路径, 价格区间, 描述, 卖点关键词)
_PRODUCT_TEMPLATES = [
    # —— 数码（送礼场景重点）——
    ("华为 Mate70 Pro 旗舰手机", "数码/手机/华为", (5999, 7999),
     "麒麟芯片，超光变影像，鸿蒙系统流畅丝滑，送长辈送男友的体面之选。", "送礼 高端 拍照 旗舰"),
    ("Apple AirPods Pro 2 无线耳机", "数码/耳机/苹果", (1599, 1899),
     "主动降噪，空间音频，通勤地铁瞬间安静，精致小巧适合送人。", "送礼 降噪 通勤 苹果"),
    ("小米手环 9 智能运动手表", "数码/穿戴/小米", (249, 399),
     "血氧心率监测，14天续航，运动健康好搭子，平价送礼首选。", "送礼 运动 健康 续航"),
    ("索尼 WH-1000XM5 头戴耳机", "数码/耳机/索尼", (2299, 2899),
     "旗舰降噪，Hi-Res 音质，发烧友与商务人士的礼物。", "送礼 降噪 音质 商务"),
    ("大疆 Osmo Pocket 3 口袋相机", "数码/影像/大疆", (3499, 3999),
     "一英寸传感器，云台稳定，vlog 神器，送摄影爱好者很有面子。", "送礼 vlog 摄影 稳定"),
    ("Kindle Paperwhite 电子书阅读器", "数码/阅读/亚马逊", (999, 1299),
     "墨水屏护眼，海量藏书，送爱读书的人最贴心。", "送礼 护眼 阅读 轻便"),
    # —— 女装 ——
    ("法式复古碎花连衣裙", "女装/连衣裙/法式", (199, 399),
     "收腰显瘦，雪纺面料垂感好，约会通勤都能穿，有 S/M/L/XL。", "显瘦 约会 雪纺 碎花"),
    ("韩版宽松针织开衫", "女装/针织衫/韩版", (129, 259),
     "慵懒风外搭，加厚不起球，秋冬保暖百搭，均码偏大。", "百搭 保暖 慵懒 加厚"),
    ("高腰直筒牛仔裤", "女装/裤装/牛仔", (159, 299),
     "显腿长，弹力舒适，不挑身材，黑蓝两色 25-32 码齐全。", "显瘦 弹力 高腰 百搭"),
    ("羊毛混纺大衣", "女装/外套/大衣", (599, 999),
     "双面呢工艺，挺括有型，气质通勤，含羊毛保暖。", "气质 保暖 通勤 羊毛"),
    ("真丝吊带睡裙", "女装/家居服/真丝", (299, 499),
     "桑蚕丝亲肤，透气凉爽，夏季睡眠舒适，送女友很合适。", "真丝 亲肤 送礼 舒适"),
    # —— 美妆 ——
    ("兰蔻小黑瓶精华套装", "美妆/护肤/兰蔻", (1080, 1680),
     "修护肌底，提亮肤色，节日礼盒装，送女生绝不出错。", "送礼 修护 礼盒 提亮"),
    ("YSL 圣罗兰口红礼盒", "美妆/彩妆/YSL", (680, 980),
     "经典正红显白，丝缎质地，限定礼盒包装精美。", "送礼 显白 礼盒 大牌"),
    ("雅诗兰黛小棕瓶眼霜", "美妆/护肤/雅诗兰黛", (480, 680),
     "淡化细纹，紧致眼周，熬夜党救星。", "抗老 紧致 眼霜 熬夜"),
    # —— 家居 ——
    ("北欧简约乳胶枕", "家居/床品/枕头", (129, 259),
     "泰国进口乳胶，护颈助眠，回弹支撑好。", "助眠 护颈 乳胶 舒适"),
    ("加湿器香薰一体机", "家居/电器/加湿", (159, 329),
     "静音大雾量，卧室办公室都能用，干燥季必备。", "静音 加湿 香薰 卧室"),
    ("北欧风陶瓷餐具套装", "家居/厨房/餐具", (199, 399),
     "釉下彩工艺，微波炉适用，乔迁送礼有格调。", "送礼 乔迁 陶瓷 套装"),
    # —— 食品 ——
    ("坚果大礼包零食组合", "食品/零食/坚果", (89, 159),
     "每日坚果独立包装，多种口味，办公室追剧解馋，送人也体面。", "送礼 健康 零食 组合"),
    ("特级新疆和田大枣", "食品/生鲜/红枣", (69, 129),
     "肉厚核小，自然甜，补气养颜，送长辈贴心。", "送礼 养生 新疆 红枣"),
    ("云南普洱茶饼礼盒", "食品/茶叶/普洱", (199, 599),
     "古树春料，越陈越香，商务送礼有档次。", "送礼 商务 茶叶 礼盒"),
]

# 会话买家问题模板：覆盖 尺码 / 快递 / 质量 三类
_BUYER_QUESTION_TEMPLATES = {
    "尺码": [
        "亲，我 160 的个子 110 斤穿这个选 M 码可以吗？",
        "这个有大码吗？我平时穿 XL。",
        "鞋子偏大还是偏小呀，需要拍大一码吗？",
        "肩宽 42 选什么码合适？",
    ],
    "快递": [
        "今天下单什么时候能发货呀？我有点急。",
        "发什么快递？能发顺丰吗？",
        "江浙沪一般几天能到？",
        "可以备注不要中通吗，我们这边中通老是丢件。",
    ],
    "质量": [
        "这个会起球吗？洗了会缩水吗？",
        "是正品吗？有授权吗？",
        "面料是纯棉的还是涤纶的呀？",
        "用了会过敏吗，我敏感肌。",
    ],
}

# 客服回复模板（按问题类型，喂给步骤6 话术向量库）
_SERVICE_REPLY_TEMPLATES = {
    "尺码": "亲，按您的身高体重建议选 M 码哦，我们版型偏正常，您可以放心拍～如果担心可以拍 L 码更宽松一点呢。",
    "快递": "亲，我们 48 小时内发货哒，默认发中通，您要顺丰的话可以补差价帮您安排，江浙沪一般 2-3 天到～",
    "质量": "亲请放心，我们是品牌正品授权，面料经过检测不易起球，按洗标冷水洗护就好，敏感肌也可放心使用呢。",
}


class MockPlatformConnector(PlatformConnector):
    """Faker 本地生成真实感中文演示数据，无任何外部 API 调用。"""

    def __init__(self):
        self.fake = Faker("zh_CN")

    # ---------- 商品 ----------
    async def fetch_products(self, shop_id: int) -> List[dict]:
        """生成 50 个商品，字段对齐 external_products。"""
        products = []
        for i in range(50):
            tpl = _PRODUCT_TEMPLATES[i % len(_PRODUCT_TEMPLATES)]
            title, cat_path, price_range, desc, _kw = tpl
            # 同模板多次出现时加变体后缀，保证标题/货号区分度
            variant = ""
            if i >= len(_PRODUCT_TEMPLATES):
                variant = " " + random.choice(["经典款", "新款", "限定色", "加厚款", "礼盒装"])
            price = round(random.uniform(*price_range), 2)
            products.append({
                "platform_product_id": f"MP{shop_id}{i:05d}",
                "title": title + variant,
                "price": price,
                "stock": random.randint(0, 500),
                "description": desc,
                "images_json": [f"https://mock.local/img/{shop_id}/{i}_{n}.jpg" for n in range(3)],
                "category_path": cat_path,
                "status": 1 if random.random() > 0.05 else 0,
                "last_sync_at": datetime.now(),
            })
        return products

    # ---------- 会话 ----------
    async def get_conversations(self, shop_id: int) -> List[dict]:
        """生成 30 个会话，覆盖尺码/快递/质量，字段对齐 conversations。"""
        conversations = []
        qtypes = list(_BUYER_QUESTION_TEMPLATES.keys())
        for i in range(30):
            qtype = qtypes[i % len(qtypes)]
            buyer_q = random.choice(_BUYER_QUESTION_TEMPLATES[qtype])
            service_a = _SERVICE_REPLY_TEMPLATES[qtype]
            buyer_nick = self.fake.name()
            base_time = datetime.now() - timedelta(hours=random.randint(0, 72))
            messages = [
                {"role": "buyer", "content": buyer_q,
                 "time": base_time.strftime("%Y-%m-%d %H:%M:%S")},
                {"role": "service", "content": service_a,
                 "time": (base_time + timedelta(minutes=2)).strftime("%Y-%m-%d %H:%M:%S")},
            ]
            # 部分会话追问一轮，留最后一条买家消息待回复
            handled = random.choice(["pending", "replied", "closed"])
            if handled == "pending":
                follow = random.choice(_BUYER_QUESTION_TEMPLATES[random.choice(qtypes)])
                messages.append({
                    "role": "buyer", "content": follow,
                    "time": (base_time + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S"),
                })
            last_time = base_time + timedelta(minutes=5)
            conversations.append({
                "platform_conversation_id": f"MC{shop_id}{i:05d}",
                "buyer_nick": buyer_nick,
                "messages_json": messages,
                "last_message_at": last_time,
                "handled_status": handled,
                "_question_type": qtype,  # 内部提示，落库时丢弃
            })
        return conversations

    # ---------- 订单 ----------
    async def fetch_orders(self, shop_id: int, start_time: datetime) -> List[dict]:
        """生成 100 个订单，字段对齐 external_orders；含 product_title 供催单。"""
        orders = []
        statuses = (
            ["pending"] * 20 + ["paid"] * 25 + ["shipped"] * 25
            + ["completed"] * 22 + ["refunding"] * 4 + ["refunded"] * 4
        )
        for i in range(100):
            tpl = _PRODUCT_TEMPLATES[i % len(_PRODUCT_TEMPLATES)]
            title, _cat, price_range, _desc, _kw = tpl
            qty = random.randint(1, 3)
            unit_price = round(random.uniform(*price_range), 2)
            total = round(unit_price * qty, 2)
            discount = round(total * random.choice([0, 0, 0.05, 0.1]), 2)
            pay_amount = round(total - discount, 2)
            status = statuses[i % len(statuses)]
            created = start_time + timedelta(
                seconds=random.randint(0, max(1, int((datetime.now() - start_time).total_seconds())))
            )
            pay_time = created + timedelta(minutes=random.randint(1, 120)) if status != "pending" else None
            ship_time = (pay_time + timedelta(hours=random.randint(1, 48))
                         if status in ("shipped", "completed") and pay_time else None)
            orders.append({
                "platform_order_id": f"MO{shop_id}{i:06d}",
                "buyer_openid": f"openid_{shop_id}_{i}",
                "buyer_nick": self.fake.name(),
                "total_amount": total,
                "discount_amount": discount,
                "pay_amount": pay_amount,
                "status": status,
                "sku_details_json": [{"title": title, "price": unit_price, "qty": qty}],
                "product_title": title,  # 催单用（agent-design.md 契约）
                "receiver_name": self.fake.name(),
                "receiver_phone": self.fake.phone_number(),
                "receiver_address": self.fake.address().replace("\n", " "),
                "pay_time": pay_time,
                "ship_time": ship_time,
                "created_at": created,
            })
        return orders

    # ---------- 发消息（模拟）----------
    async def send_message(self, shop_id: int, buyer_openid: str, content: str) -> bool:
        """模拟发送，不发起真实请求，恒成功。"""
        return True

    async def send_notification(self, buyer_id: int, order_id: int, content: str) -> dict:
        return {"id": 0, "conversation_id": 0}
