FROM python:3.13-slim

WORKDIR /app

# 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libssl-dev && rm -rf /var/lib/apt/lists/*

# Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 应用代码
COPY . .

# 数据目录
RUN mkdir -p /app/data/chroma /app/data/uploads

EXPOSE 8012

# 启动: 建表 + 迁移 + 种子数据 + 启动服务
CMD ["sh", "-c", "\
  python -c 'from app.database.session import Base, engine; import app.models; Base.metadata.create_all(bind=engine)' && \
  python -c \"\nfrom sqlalchemy import text\nfrom app.database.session import engine\nwith engine.connect() as c:\n  for col, typ in [('file_path','VARCHAR(500)'),('file_type','VARCHAR(20)')]:\n    try: c.execute(text(f'ALTER TABLE kb_documents ADD COLUMN {col} {typ}'))\n    except: pass\n  c.commit()\n\" 2>/dev/null || true && \
  python seed.py --backfill --full 2>/dev/null || true && \
  uvicorn main:app --host 0.0.0.0 --port 8012 \
"]
