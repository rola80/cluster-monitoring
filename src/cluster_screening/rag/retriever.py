"""질의 → 근거 조항 top-k 검색(벡터 + 키워드 그라운딩).

순수 벡터 검색은 의미가 비슷하면 키워드가 없어도 끌어오므로, **질의의 핵심 키워드가 본문에
실제로 들어 있는 조항만** 남긴다(없으면 빈 결과 = '근거 조항 없음').
"""
import re

from .. import config
from . import index

# 흔한 규정어 — 이 단어만 겹치는 건 근거로 보지 않는다(그라운딩 키워드에서 제외).
_STOP = {"기업", "경우", "또는", "그리고", "해당", "관한", "대한", "위한", "따른", "따라",
         "사항", "범위", "대상", "제외", "포함", "규정", "법률", "조항", "각호", "각목",
         "이내", "이상", "이하", "신청", "서류", "제출", "지원", "사업", "다음", "정하는"}
_TOKEN = re.compile(r"[가-힣]{2,}|[A-Za-z]{3,}|\d{2,}")
# 흔한 조사(끝에 붙는 것) — 제거해 어간만 매칭("지방세를"→"지방세")
_PARTICLE = re.compile(r"(으로|에서|에게|부터|까지|마다|를|을|이|가|은|는|의|에|와|과|로|등|및)$")


def _stem(tok):
    s = _PARTICLE.sub("", tok)
    return s if len(s) >= 2 else tok


def _keywords(text):
    """질의에서 핵심 키워드(2자+ 한글/숫자, 영문 3자+) 추출. 조사 제거 + 흔한 규정어 제외."""
    out = set()
    for t in _TOKEN.findall(text or ""):
        s = _stem(t)
        if len(s) >= 2 and s not in _STOP:
            out.add(s)
    return out


def _grounded(hit_text, query_kw):
    """질의 키워드가 본문에 부분문자열로 하나라도 있으면 True('체납'⊂'체납한'도 인정)."""
    t = hit_text or ""
    return (not query_kw) or any(k in t for k in query_kw)


def search(query, top_k=None, ground=True):
    """벡터 top-k 후 키워드 그라운딩 필터. 질의 키워드가 본문에 없는 조항은 제외(없으면 [])."""
    top_k = top_k or config.RAG_TOP_K
    col = index.get_collection()
    cnt = col.count()
    if cnt == 0:
        return []
    fetch = min(cnt, top_k * 4 if ground else top_k)   # 그라운딩 탈락 대비 여유 있게 후보 수집
    res = col.query(query_embeddings=index.embed([query]), n_results=fetch)
    hits = [{"text": doc, "score": round(1 - dist, 3), **meta}
            for doc, meta, dist in zip(res["documents"][0], res["metadatas"][0], res["distances"][0])]
    if ground:
        qk = _keywords(query)
        hits = [h for h in hits if _grounded(h["text"], qk)]
    return hits[:top_k]


def evidence_for(query, top_k=1, min_score=None):
    """판정 통합용: 그라운딩된 최상위 근거를 'source p.N 제M조' 문자열로. 없으면 ''."""
    min_score = config.RAG_MIN_SCORE if min_score is None else min_score
    hits = search(query, top_k)
    if not hits or hits[0]["score"] < min_score:
        return ""
    h = hits[0]
    loc = f'{h["source"]} p.{h["page"]}'
    if h.get("article"):
        loc += f' {h["article"]}'
    return f'{loc} (유사도 {h["score"]})'
