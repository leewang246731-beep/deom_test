"""
DashScope Embedding 封装（text-embedding-v4, 1024 维）
批量调用，每批最多 25 条。供 ChromaDB 向量化入库与检索。
"""
import dashscope
from dashscope import TextEmbedding

from app.core.config import settings

dashscope.api_key = settings.DASHSCOPE_API_KEY

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
        resp = TextEmbedding.call(model=MODEL, input=batch, dimension=DIMENSION)
        if resp.status_code != 200:
            raise RuntimeError(f"DashScope Embedding 失败: {resp.status_code} {resp.message}")
        all_embeddings.extend(item["embedding"] for item in resp.output["embeddings"])
    return all_embeddings


def embed_query(query: str) -> list[float]:
    """单条查询向量化。"""
    return embed_texts([query])[0]
