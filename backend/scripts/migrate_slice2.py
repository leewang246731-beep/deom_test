"""Slice 2 幂等迁移：ExternalOrder +after_sale_id/+after_sale_status, order_reminders 表"""
import pymysql
from app.core.config import settings

def migrate():
    conn = pymysql.connect(
        host=settings.DB_HOST, port=settings.DB_PORT,
        user=settings.DB_USER, password=settings.DB_PASSWORD,
        database=settings.DB_NAME,
    )
    cur = conn.cursor()

    # 1. ExternalOrder 新列（幂等：先查是否存在）
    cur.execute("SHOW COLUMNS FROM external_orders LIKE 'after_sale_id'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE external_orders ADD COLUMN after_sale_id BIGINT NULL COMMENT 'vMall售后单id'")
        print("  + external_orders.after_sale_id")

    cur.execute("SHOW COLUMNS FROM external_orders LIKE 'after_sale_status'")
    if not cur.fetchone():
        cur.execute("ALTER TABLE external_orders ADD COLUMN after_sale_status VARCHAR(20) NULL COMMENT 'created/approved/rejected'")
        print("  + external_orders.after_sale_status")

    # 2. order_reminders 表（幂等）
    cur.execute("SHOW TABLES LIKE 'order_reminders'")
    if not cur.fetchone():
        cur.execute("""
            CREATE TABLE order_reminders (
                id BIGINT PRIMARY KEY AUTO_INCREMENT,
                merchant_id BIGINT NOT NULL,
                shop_id BIGINT NOT NULL,
                order_id BIGINT NOT NULL,
                buyer_openid VARCHAR(100) NULL,
                content TEXT NULL,
                channel VARCHAR(20) DEFAULT 'vmall',
                sent_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_merchant (merchant_id),
                INDEX idx_order (order_id)
            )
        """)
        print("  + order_reminders table")

    conn.commit()
    conn.close()
    print("Slice 2 migration complete.")

if __name__ == "__main__":
    migrate()
