"""虚拟物流数据生成器 (tuozhan.md §2.4)"""
import random

CITIES = ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆", "苏州", "长沙"]
COURIERS = [{"name": "张伟", "phone": "13800001001"}, {"name": "李强", "phone": "13800001002"},
             {"name": "王芳", "phone": "13800001003"}, {"name": "刘洋", "phone": "13800001004"},
             {"name": "陈静", "phone": "13800001005"}, {"name": "赵磊", "phone": "13800001006"},
             {"name": "周婷", "phone": "13800001007"}]
COMPANIES = ["顺丰速运", "中通快递", "圆通速递"]


def generate_courier() -> dict:
    c = random.choice(COURIERS)
    return {"name": c["name"], "phone": c["phone"], "city": random.choice(CITIES)}


def generate_tracking_no(company: str = None) -> str:
    prefix = {"顺丰速运": "SF", "中通快递": "ZTO", "圆通速递": "YTO"}.get(company, "EXP")
    return f"{prefix}{random.randint(1000000000, 9999999999)}"


def generate_node_data(logistics_id: int, status: str) -> dict:
    """根据状态生成逼真的物流节点。"""
    city = random.choice(CITIES)
    courier = random.choice(COURIERS)

    templates = {
        "PICKED": {"node_name": "已揽收", "node_desc": f"快递员{courier['name']}({courier['phone']})已取件",
                    "city": city, "operator": courier["name"]},
        "IN_TRANSIT": {
            "node_name": f"到达{random.choice(CITIES)}中转中心",
            "node_desc": f"包裹到达中转中心，正发往下一站", "city": city,
        },
        "OUT_FOR_DELIVERY": {
            "node_name": "派送中",
            "node_desc": f"快递员{courier['name']}({courier['phone']})正在派送，请保持电话畅通",
            "city": city, "operator": courier["name"],
        },
        "DELIVERED": {"node_name": "已签收", "node_desc": "包裹已签收，感谢使用", "city": city},
        "FAILED": {"node_name": "派送失败", "node_desc": "快递员联系不上买家，请确认联系方式",
                    "city": city},
        "STUCK": {"node_name": "异常滞留",
                   "node_desc": f"因{'天气原因' if random.random()>0.5 else '物流拥堵'}导致包裹滞留，正在加急处理",
                   "city": city},
        "CANCELLED": {"node_name": "已取消", "node_desc": "物流已取消", "city": city},
    }
    return templates.get(status, {"node_name": status, "node_desc": "", "city": city})


def get_script_template(merchant_id: int, status_code: str, db=None) -> str:
    """获取商户对应的物流话术模板。"""
    if db:
        try:
            from app.models.vm_logistics import VmLogisticsScriptTemplate
            row = db.query(VmLogisticsScriptTemplate).filter(
                VmLogisticsScriptTemplate.merchant_id == merchant_id,
                VmLogisticsScriptTemplate.status_code == status_code,
            ).first()
            if row:
                return row.script_template
        except Exception:
            pass
    return _default_template(status_code)


def _default_template(status_code: str) -> str:
    defaults = {
        "PICKED": "亲，您的订单{order_no}已由{company}揽收，运单号{track_no}，预计{estimated}天送达~",
        "IN_TRANSIT": "您的包裹已到达{city}中转站，正在加速分拣中，预计{estimated}天送达❤️",
        "OUT_FOR_DELIVERY": "快递员{courier}({phone})正在派送您的包裹，请保持电话畅通~",
        "DELIVERED": "您的包裹已签收，满意请给五星好评哦⭐",
        "FAILED": "亲，快递员反馈联系不上您({detail})，请确认联系方式或联系我们安排改址/自提",
        "STUCK": "您的包裹因{detail}滞留，我们已联系快递加急处理，抱歉🙏",
    }
    return defaults.get(status_code, "您的包裹当前状态：{status}")
