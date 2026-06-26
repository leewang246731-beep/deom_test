FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libssl-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8020

CMD ["sh", "-c", "\
  python -c 'from app.database.session import Base, engine; import app.models; Base.metadata.create_all(bind=engine)' && \
  python seed_vmall.py 2>/dev/null || true && \
  uvicorn main:app --host 0.0.0.0 --port 8020 \
"]
