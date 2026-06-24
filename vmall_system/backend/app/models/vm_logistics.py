"""物流表 (升级版 — tuozhan.md §2.1)"""
from sqlalchemy import JSON, BigInteger, Column, DateTime, ForeignKey, Integer, SmallInteger, String, func
from app.database.session import Base


class VmLogistics(Base):
    __tablename__ = "vm_logistics"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    order_id = Column(BigInteger, ForeignKey("vm_orders.id"), nullable=False)
    company = Column(String(50), nullable=False)
    tracking_no = Column(String(50), nullable=False)
    status = Column(String(30), default="PENDING", comment="PENDING/PICKED/IN_TRANSIT/OUT_FOR_DELIVERY/DELIVERED/FAILED/STUCK/CANCELLED")
    status_label = Column(String(20), default="待发货")
    estimated_days = Column(Integer, default=3, comment="预计送达天数")
    exception_code = Column(String(30), nullable=True, comment="FAILED/STUCK/ADDRESS_ERROR")
    exception_detail = Column(String(255), nullable=True, comment="异常详情描述")
    courier_name = Column(String(50), nullable=True, comment="快递员姓名")
    courier_phone = Column(String(20), nullable=True, comment="快递员电话")
    current_city = Column(String(50), nullable=True, comment="当前所在城市")
    events_json = Column(JSON, nullable=True, comment="[{time,status,location}] (兼容旧字段)")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class VmLogisticsTrack(Base):
    """物流轨迹节点明细表（独立存储，便于追溯）"""
    __tablename__ = "vm_logistics_tracks"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    logistics_id = Column(BigInteger, ForeignKey("vm_logistics.id", ondelete="CASCADE"), nullable=False)
    status_code = Column(String(30), nullable=False, comment="节点状态码")
    node_name = Column(String(50), nullable=False, comment="节点名称（已揽收/到达XX中转站）")
    node_desc = Column(String(255), nullable=False, comment="节点详细描述")
    node_time = Column(DateTime, server_default=func.now(), comment="节点发生时间")
    city = Column(String(50), nullable=True, comment="所在城市")
    operator = Column(String(50), nullable=True, comment="操作人")
    is_current = Column(SmallInteger, default=0, comment="是否为当前节点")
    is_exception = Column(SmallInteger, default=0, comment="是否异常节点")


class VmLogisticsScriptTemplate(Base):
    """物流话术模板表（商户可自定义）"""
    __tablename__ = "vm_logistics_script_templates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    merchant_id = Column(Integer, nullable=False, comment="商户ID")
    status_code = Column(String(30), nullable=False, comment="触发状态码")
    script_template = Column(String(500), nullable=False, comment="话术模板，变量{order_no}/{company}/{track_no}/{city}/{estimated}/{courier}/{phone}/{detail}")
    tone = Column(String(20), default="warm")
    is_default = Column(SmallInteger, default=0, comment="是否为系统默认")
    created_at = Column(DateTime, server_default=func.now())
