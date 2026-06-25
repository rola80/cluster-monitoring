"""페이지 텍스트 → 검색 단위 청크 + metadata 6항목.

metadata: source · page · parser_type · chunk_id · token_count · warning  (+ article)
정부 규정은 '제N조'가 자연스러운 근거 경계 → **먼저 제N조 경계로 분할**한 뒤, 긴 조는 윈도우로 나눈다.
이렇게 하면 각 청크가 정확히 어느 조에 속하는지(article)가 보장되어 evidence가 조항을 정확히 가리킨다.
"""
import re

from .. import config

_ARTICLE = re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?")


def _approx_tokens(text):
    """간이 토큰 수(공백 분할). 정확한 토크나이저 의존 없이 metadata 유지 목적."""
    return len(text.split())


def _window_strs(text, size, overlap):
    """긴 텍스트를 size 문자 윈도우(overlap 겹침)로 나눈다."""
    text = text or ""
    if not text.strip():
        return []
    if len(text) <= size:
        return [text]
    step = max(size - overlap, 1)
    out, start = [], 0
    while start < len(text):
        piece = text[start:start + size]
        if piece.strip():
            out.append(piece)
        start += step
    return out


def _segments_by_article(text):
    """'제N조' 경계로 분할 → [(article, segment)]. 첫 조 앞 서문은 article=''."""
    text = text or ""
    spans = list(_ARTICLE.finditer(text))
    if not spans:
        return [("", text)]
    segs = []
    if spans[0].start() > 0 and text[:spans[0].start()].strip():
        segs.append(("", text[:spans[0].start()]))      # 서문(첫 조 앞)
    for i, m in enumerate(spans):
        end = spans[i + 1].start() if i + 1 < len(spans) else len(text)
        segs.append((m.group().replace(" ", ""), text[m.start():end]))
    return segs


def chunk_pages(pages, size=None, overlap=None):
    """페이지 목록 → 청크 목록(각 청크는 metadata 동반). 조 단위 분할 후 윈도우."""
    size = size or config.RAG_CHUNK_CHARS
    overlap = overlap or config.RAG_CHUNK_OVERLAP
    chunks = []
    for pg in pages:
        j = 0
        for article, seg in _segments_by_article(pg["text"] or ""):
            for piece in _window_strs(seg, size, overlap):
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
                j += 1
    return chunks
