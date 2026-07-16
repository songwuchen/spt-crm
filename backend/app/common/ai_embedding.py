"""向量嵌入客户端 —— 统一走 OpenAI 兼容 /embeddings 接口。

支持通义(DashScope)、OpenAI、以及任意 OpenAI 兼容端点。所有模型统一请求到
EMBEDDING_DIM(1024)维,与 pgvector 列/索引维度对齐。cfg 为已解密的嵌入配置:
    {"base_url": ..., "api_key": ..., "model": ..., "dimensions": 1024}
"""
import logging

import httpx

from app.common.ai_providers import EMBEDDING_DIM

logger = logging.getLogger("spt_crm.ai.embedding")

_BATCH = 10  # DashScope 兼容接口单次 input 上限较小,分批更稳


def _to_vec_literal(vec: list[float]) -> str:
    """把浮点向量序列化为 pgvector 字面量 '[0.1,0.2,...]'。"""
    return "[" + ",".join(repr(float(x)) for x in vec) + "]"


async def _embed_batch(client: httpx.AsyncClient, cfg: dict, inputs: list[str]) -> list[list[float]]:
    base_url = (cfg.get("base_url") or "").rstrip("/")
    api_key = cfg.get("api_key") or ""
    model = cfg.get("model") or "text-embedding-v3"
    dimensions = int(cfg.get("dimensions") or EMBEDDING_DIM)

    payload = {"model": model, "input": inputs, "encoding_format": "float"}
    # 仅在 <=1024 时下发 dimensions(部分模型不支持该参数则由 provider 决定,通义/openai均支持)
    if dimensions and dimensions <= EMBEDDING_DIM:
        payload["dimensions"] = dimensions

    resp = await client.post(
        f"{base_url}/embeddings",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
    )
    resp.raise_for_status()
    data = resp.json()
    # OpenAI 兼容返回按 index 排序,防御性地按 index 重排
    rows = sorted(data.get("data", []), key=lambda r: r.get("index", 0))
    return [r.get("embedding", []) for r in rows]


async def embed_texts(cfg: dict, texts: list[str]) -> list[list[float]]:
    """返回与 texts 等长的向量列表(每个长度 = EMBEDDING_DIM)。失败抛异常。"""
    if not texts:
        return []
    out: list[list[float]] = []
    async with httpx.AsyncClient(timeout=60) as client:
        for i in range(0, len(texts), _BATCH):
            batch = texts[i:i + _BATCH]
            vecs = await _embed_batch(client, cfg, batch)
            if len(vecs) != len(batch):
                raise ValueError(f"嵌入返回数量不匹配: 期望 {len(batch)} 实际 {len(vecs)}")
            out.extend(vecs)
    # 维度校验
    for v in out:
        if len(v) != EMBEDDING_DIM:
            raise ValueError(f"嵌入维度不匹配: 期望 {EMBEDDING_DIM} 实际 {len(v)}(请选用 {EMBEDDING_DIM} 维模型)")
    return out


async def embed_query(cfg: dict, text: str) -> list[float] | None:
    vecs = await embed_texts(cfg, [text])
    return vecs[0] if vecs else None


async def test_embedding(cfg: dict) -> tuple[bool, str | None, int]:
    """联通性测试。返回 (ok, error, dim)。"""
    try:
        v = await embed_query(cfg, "连接测试")
        if not v:
            return False, "未返回向量", 0
        return True, None, len(v)
    except httpx.HTTPStatusError as e:
        body = ""
        try:
            body = e.response.text[:200]
        except Exception:
            pass
        return False, f"HTTP {e.response.status_code}: {body}", 0
    except Exception as e:
        return False, str(e), 0
