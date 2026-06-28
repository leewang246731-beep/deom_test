"""
系统启动前验证脚本
运行: python verify.py [--fix]
检查: Python版本, 依赖包, MySQL, Redis, ChromaDB, .env, 端口
"""
import sys
import os
import subprocess
import socket

try:  # GBK 控制台下强制 UTF-8，避免打印 ✅ 等字符时崩溃
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PASS = FAIL = 0


def ok(msg):
    global PASS; PASS += 1
    print(f"  ✅ {msg}")

def err(msg, fix=None):
    global FAIL; FAIL += 1
    hint = f"  → 修复: {fix}" if fix else ""
    print(f"  ❌ {msg}{hint}")

def check_port(host, port, label):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex((host, port))
        s.close()
        if result == 0:
            ok(f"{label} ({host}:{port}) 可达")
            return True
        else:
            err(f"{label} ({host}:{port}) 不可达", f"启动 {label} 服务")
            return False
    except Exception as e:
        err(f"{label} 检查失败: {e}")
        return False


def main():
    global PASS, FAIL
    fix_mode = "--fix" in sys.argv

    print("=" * 55)
    print("  多平台智能托管 SaaS — 系统验证")
    print("=" * 55)

    # 1. Python
    print("\n[1] Python 环境")
    v = sys.version_info
    if v.major >= 3 and v.minor >= 10:
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        err(f"Python {v.major}.{v.minor} (需要 >= 3.10)", "安装 Python 3.10+")

    # 2. 依赖包
    print("\n[2] 核心依赖")
    pkgs = {
        "fastapi": "FastAPI", "sqlalchemy": "SQLAlchemy", "pydantic": "Pydantic",
        "redis": "Redis-py", "jose": "python-jose", "bcrypt": "bcrypt",
        "chromadb": "ChromaDB", "httpx": "httpx", "apscheduler": "APScheduler",
    }
    for mod, name in pkgs.items():
        try:
            __import__(mod)
            ok(f"{name}")
        except ImportError:
            err(f"{name} 未安装", f"pip install {mod}")

    # 3. .env 配置
    print("\n[3] 配置文件 (.env)")
    env_path = os.path.join(BASE_DIR, ".env")
    if os.path.exists(env_path):
        ok(".env 存在")
        from app.core.config import settings
        ok(f"PLATFORM_MODE={settings.PLATFORM_MODE}")
        ok(f"DASHSCOPE_API_KEY={'***' if settings.DASHSCOPE_API_KEY else '(未设置 — AI功能不可用)'}")
        ok(f"API_PREFIX={settings.API_PREFIX}")
    else:
        err(".env 不存在", "从 .env.example 复制并修改配置")

    # 4. MySQL
    print("\n[4] MySQL 数据库")
    try:
        from app.core.config import settings
        check_port(settings.DB_HOST, settings.DB_PORT, "MySQL")
        from sqlalchemy import create_engine, text
        engine = create_engine(settings.DATABASE_URL, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        ok(f"数据库 {settings.DB_NAME} 连接成功")
    except Exception as e:
        err(f"数据库连接失败: {e}", "检查 MySQL 服务 + .env 配置")

    # 5. Redis
    print("\n[5] Redis")
    try:
        from app.core.config import settings
        check_port(settings.REDIS_HOST, settings.REDIS_PORT, "Redis")
        import redis
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT,
                        password=settings.REDIS_PASSWORD or None,
                        socket_connect_timeout=3)
        if r.ping():
            ok("Redis PING 成功")
    except Exception as e:
        err(f"Redis 连接失败: {e}", "启动 Redis 服务 (redis-server)")

    # 6. ChromaDB
    print("\n[6] ChromaDB (向量存储)")
    try:
        from app.core.config import settings
        chroma_dir = settings.CHROMA_PERSIST_DIR
        if os.path.exists(chroma_dir):
            ok(f"ChromaDB 目录存在: {chroma_dir}")
        else:
            err(f"ChromaDB 目录不存在: {chroma_dir}", "运行 seed.py --backfill 初始化")
    except Exception as e:
        err(f"ChromaDB 检查失败: {e}")

    # 7. 数据库表
    print("\n[7] 数据库表结构")
    try:
        from app.database.session import engine, Base
        import app.models  # noqa
        tables = Base.metadata.tables.keys()
        ok(f"已注册 {len(tables)} 张表: {', '.join(sorted(tables)[:8])}...")
    except Exception as e:
        err(f"表结构加载失败: {e}")

    # 8. 端口可用性
    print("\n[8] 服务端口")
    check_port("127.0.0.1", 8012, "SaaS Backend")
    # 前端端口只检查是否已被占用（dev server 稍后启动）
    for p, name in [(8093, "Admin"), (8094, "Merchant"), (8095, "Service")]:
        s = socket.socket()
        s.settimeout(1)
        in_use = s.connect_ex(("127.0.0.1", p)) == 0
        s.close()
        if in_use:
            ok(f"前端 {name} (:{p}) 端口已占用 (dev server 运行中?)")
        else:
            print(f"  ⚠️  前端 {name} (:{p}) 端口空闲")

    # 9. vMall 系统（可选）
    print("\n[9] vMall 系统 (可选)")
    vmall_dir = os.path.join(os.path.dirname(BASE_DIR), "vmall_system", "backend")
    if os.path.exists(vmall_dir):
        ok(f"vMall 目录存在: {vmall_dir}")
        vmall_env = os.path.join(vmall_dir, ".env")
        if os.path.exists(vmall_env):
            ok("vMall .env 存在")
        else:
            err("vMall .env 不存在", "配置 vmall_system/backend/.env")
    else:
        print("  ⚠️  vMall 系统未找到 (跨系统功能需 vMall 运行)")

    # 10. 前端依赖
    print("\n[10] 前端依赖")
    front_dir = os.path.join(os.path.dirname(BASE_DIR), "frontend")
    node_modules = os.path.join(front_dir, "node_modules")
    if os.path.exists(node_modules):
        ok("frontend/node_modules 存在")
    else:
        err("frontend/node_modules 不存在", "cd frontend && npm install")

    # Results
    total = PASS + FAIL
    print(f"\n{'='*55}")
    print(f"  结果: {PASS}/{total} 通过, {FAIL} 失败")
    if FAIL == 0:
        print("  ✅ 系统就绪，可以启动:")
        print("    cd backend && uvicorn main:app --host 0.0.0.0 --port 8012")
        print("    cd frontend && npm run dev:admin  (:8093)")
    else:
        print(f"  ❌ {FAIL} 项未通过，请修复后重试")
    print("=" * 55)
    return FAIL == 0


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
