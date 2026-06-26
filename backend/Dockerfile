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
RUN mkdir -p /app/data/chroma

EXPOSE 8012

# 启动: 建表 + 种子数据 + 启动服务
CMD ["sh", "-c", "\
  python -c 'from app.database.session import Base, engine; import app.models; Base.metadata.create_all(bind=engine)' && \
  python seed.py --backfill --full 2>/dev/null || true && \
  uvicorn main:app --host 0.0.0.0 --port 8012 \
"]
