"""RAG 청킹 — 조(條) 단위 분할 + metadata. (rag extra 불필요: 순수 파이썬)"""
from cluster_screening.rag import chunking

META6 = {"source", "page", "parser_type", "chunk_id", "token_count", "warning", "article"}


def test_segments_by_article_분할():
    text = "총칙 서문. 제1조(목적) 가나다. 제2조(정의) 라마바. 제9조(제외) 체납 기업은 제외."
    arts = [a for a, _ in chunking._segments_by_article(text)]
    assert "" in arts  # 서문
    assert {"제1조", "제2조", "제9조"} <= set(arts)


def test_segments_조없으면_통째():
    segs = chunking._segments_by_article("조 표기가 전혀 없는 일반 문단입니다.")
    assert len(segs) == 1 and segs[0][0] == ""


def test_chunk_article_정확도():
    text = "제1조(목적) " + "가" * 40 + " 제9조(제외) 국세 또는 지방세를 체납한 기업은 제외한다 " + "나" * 40
    pages = [{"source": "규정.pdf", "page": 1, "parser_type": "hwp5", "warning": "", "text": text}]
    chunks = chunking.chunk_pages(pages, size=120, overlap=10)
    hits = [c for c in chunks if "체납" in c["text"]]
    assert hits and all(c["article"] == "제9조" for c in hits)  # 체납 문구는 제9조로 태깅


def test_chunk_metadata_6항목():
    pages = [{"source": "규정.pdf", "page": 1, "parser_type": "hwp5", "warning": "", "text": "제1조 내용 " * 30}]
    chunks = chunking.chunk_pages(pages, size=100, overlap=10)
    assert chunks
    for c in chunks:
        assert META6 <= set(c)
        assert c["token_count"] > 0
    ids = [c["chunk_id"] for c in chunks]
    assert len(ids) == len(set(ids))  # chunk_id 유일
