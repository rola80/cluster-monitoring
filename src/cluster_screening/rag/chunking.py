"""페이지 텍스트 → 검색 단위 청크 + metadata 6항목.

metadata: source · page · parser_type · chunk_id · token_count · warning  (+ article)
2단계 분할:
  1) 조(條) 분할 — 실제 '제N조(제목)' 경계로 나눠 각 청크가 정확히 어느 조에 속하는지(article) 보장.
  2) 의미단위 묶음 — 조 안을 항(①②③)·호(1. 2.)·목(가. 나.)·문장('~다.') 단위로 쪼갠 뒤,
     문맥이 끊기지 않게 단위를 절대 분할하지 않고 size(문자) 예산까지 묶는다(문장 중간 절단 방지).
"""
import re

from .. import config

_ARTICLE = re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?")          # 조 번호(이름 추출용)
# 분할 경계는 '제N조(제목)' 형태의 실제 조 제목만 — 본문 속 인라인 참조("제9조제1항에 따른")는 제외
_HEADING = re.compile(r"제\s*\d+\s*조(?:의\s*\d+)?\s*\(")
# 의미단위 경계: 종결('~다.') 뒤 / 항(①-⑳) 앞 / 호(1. 2.) 앞 / 목(가. 나.) 앞
_UNIT = re.compile(r"(?<=다\.)\s+|(?=[①-⑳])|(?=\n\s*\d+[.)]\s)|(?=\n\s*[가-힣][.)]\s)")


def _approx_tokens(text):
    """간이 토큰 수(공백 분할). 정확한 토크나이저 의존 없이 metadata 유지 목적."""
    return len(text.split())


def _semantic_units(text):
    """의미단위(항·호·목·문장)로 분리. 빈 조각 제거. 분리점이 없으면 통째로 1개."""
    text = (text or "").strip()
    if not text:
        return []
    units = [u.strip() for u in _UNIT.split(text) if u and u.strip()]
    return units or [text]


def _pack(units, size, overlap):
    """의미단위를 size(문자) 예산까지 묶어 청크 생성(단위는 절대 쪼개지 않음). 뒤 overlap 문자만큼 겹침."""
    chunks, cur, cur_len = [], [], 0
    for u in units:
        if cur and cur_len + len(u) > size:
            chunks.append(" ".join(cur))
            keep, klen = [], 0
            for x in reversed(cur):            # overlap: 뒤에서부터 overlap 문자만큼 단위 유지
                if klen >= overlap:
                    break
                keep.insert(0, x)
                klen += len(x)
            cur, cur_len = keep, sum(len(x) for x in keep)
        cur.append(u)
        cur_len += len(u)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def _segments_by_article(text):
    """실제 조 제목('제N조(제목)') 경계로 분할 → [(article, segment)]. 첫 조 앞 서문은 article=''.
    조 제목이 없는 문서(공고 등)는 통째로 1개 → 의미단위 묶음 단계에서 문맥 단위로 나뉜다."""
    text = text or ""
    spans = list(_HEADING.finditer(text))
    if not spans:
        return [("", text)]
    segs = []
    if spans[0].start() > 0 and text[:spans[0].start()].strip():
        segs.append(("", text[:spans[0].start()]))      # 서문(첫 조 앞)
    for i, m in enumerate(spans):
        end = spans[i + 1].start() if i + 1 < len(spans) else len(text)
        name = _ARTICLE.match(text, m.start()).group().replace(" ", "")  # '제N조' 부분만
        segs.append((name, text[m.start():end]))
    return segs


def chunk_pages(pages, size=None, overlap=None):
    """페이지 목록 → 청크 목록(각 청크는 metadata 동반). 조 분할 후 의미단위 묶음."""
    size = size or config.RAG_CHUNK_CHARS
    overlap = overlap or config.RAG_CHUNK_OVERLAP
    chunks = []
    for pg in pages:
        j = 0
        for article, seg in _segments_by_article(pg["text"] or ""):
            for piece in _pack(_semantic_units(seg), size, overlap):
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
