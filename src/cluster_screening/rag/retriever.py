"""질의 → 근거 조항 top-k 검색.

판정 evidence에 붙일 근거(어느 문서·페이지·조항 + 본문)를 점수와 함께 돌려준다.
"""
from .. import config
from . import index


def search(query, top_k=None):
    """query와 가장 유사한 근거 청크 top-k. 반환: [{text, score, source, page, article, ...}]"""
    top_k = top_k or config.RAG_TOP_K
    col = index.get_collection()
    if col.count() == 0:
        return []
    res = col.query(query_embeddings=index.embed([query]), n_results=top_k)
    hits = []
    for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0]):
        # Chroma cosine distance(0~2) → 유사도 점수(1=완전일치)
        hits.append({"text": doc, "score": round(1 - dist, 3), **meta})
    return hits


def evidence_for(query, top_k=1, min_score=None):
    """판정 통합용 간이 헬퍼: 최상위 근거를 'source p.N 제M조' 문자열로.
    유사도가 min_score 미만이면 무관한 근거로 보고 ''(미첨부)."""
    min_score = config.RAG_MIN_SCORE if min_score is None else min_score
    hits = search(query, top_k)
    if not hits or hits[0]["score"] < min_score:
        return ""
    h = hits[0]
    loc = f'{h["source"]} p.{h["page"]}'
    if h.get("article"):
        loc += f' {h["article"]}'
    return f'{loc} (유사도 {h["score"]})'
