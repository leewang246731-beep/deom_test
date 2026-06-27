"""
Embedding 服务 — DashScope OpenAI 兼容模式 (text-embedding-v4, 1024 维)
批量调用，每批最多 25 条。供 ChromaDB 向量化入库与检索。
"""
import time

from openai import OpenAI

from app.core.config import settings

_client = OpenAI(
    api_key=settings.DASHSCOPE_API_KEY,
    base_url=settings.LLM_API_BASE,
    timeout=settings.LLM_TIMEOUT,
)

MODEL = settings.EMBEDDING_MODEL
DIMENSION = 1024
BATCH_SIZE = 10


def embed_texts(texts: list[str]) -> list[list[float]]:
    """批量生成文本向量，返回与 texts 等长的向量列表。"""
    if not texts:
        return []
    all_embeddings = []
    for i in range(0, len(texts), BATCH_SIZE):
        batch = texts[i:i + BATCH_SIZE]
        last_error = None
        for attempt in range(settings.LLM_MAX_RETRIES + 1):
            try:
                resp = _client.embeddings.create(
                    model=MODEL,
                    input=batch,
                    dimensions=DIMENSION,
                )
                all_embeddings.extend(
                    item.embedding for item in resp.data
                )
                last_error = None
                break
            except Exception as e:
                last_error = e
                if attempt < settings.LLM_MAX_RETRIES:
                    time.sleep(0.5 * (attempt + 1))
                continue
        if last_error:
            raise RuntimeError(
                f"Embedding 失败 (已重试 {settings.LLM_MAX_RETRIES} 次): {last_error}"
            )
    return all_embeddings


def embed_query(query: str) -> list[float]:
    """单条查询向量化。"""
    return embed_texts([query])[0]
