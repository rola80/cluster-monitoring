"""페이지 텍스트 → 검색 단위 청크 + metadata 6항목.

metadata: source · page · parser_type · chunk_id · token_count · warning  (+ article)
정부 규정은 '제N조'가 자연스러운 근거 경계 → 각 청크에 가장 가까운 조 번호를 article로 남겨
판정 evidence가 "운영규정 제9조"처럼 조항을 가리킬 수 있게 한다.
"""
import re
from .. import config

_ARTICLE = re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?")


def _approx_tokens(text):
    """간이 토큰 수(공백 분할). 정확한 토크나이저 의존 없이 metadata 유지 목적."""
    return len(text.split())


def _windows(text, size, overlap):
    """문자 윈도우로 분할하여 (시작위치, 조각) 목록 반환. overlap만큼 겹친다."""
    text = text or ""
    if not text.strip():
        return []
    if len(text) <= size:
        return [(0, text)]
    step = max(size - overlap, 1)
    out = []
    start = 0
    while start < len(text):
        piece = text[start:start + size]
        if piece.strip():
            out.append((start, piece))
        start += step
    return out


def chunk_pages(pages, size=None, overlap=None):
    """페이지 목록 → 청크 목록(각 청크는 metadata 동반)."""
    size = size or config.RAG_CHUNK_CHARS
    overlap = overlap or config.RAG_CHUNK_OVERLAP
    chunks = []
    for pg in pages:
        text = pg["text"] or ""
        # 페이지 내 '제N조' 마커 위치 — 청크 시작 이전의 마지막 마커를 article로 채택
        markers = [(m.start(), m.group().replace(" ", "")) for m in _ARTICLE.finditer(text)]
        for j, (start, piece) in enumerate(_windows(text, size, overlap)):
            article = ""
            for pos, name in markers:
                if pos <= start:
                    article = name
                else:
                    break
            chunks.append({
                "text": piece,
                "source": pg["source"],
                "page": pg["page"],
                "parser_type": pg["parser_type"],
                "chunk_id": f'{pg["source"]}#p{pg["page"]}#{j}',
                "token_count": _approx_tokens(piece),
                "warning": pg["warning"],
                "article": article,
            })
    return chunks
