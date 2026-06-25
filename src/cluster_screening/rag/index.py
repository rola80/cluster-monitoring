"""임베딩(오프라인 sentence-transformers) → Chroma 벡터스토어(로컬 영속) 구축.

무거운 의존성(sentence-transformers, chromadb)은 함수 안에서 지연 로딩한다
(모듈 import만으로 모델을 내려받지 않도록).
"""
from .. import config
from . import chunking, ingestion

_MODEL = None

_META_KEYS = ("source", "page", "parser_type", "token_count", "warning", "article")


def _embedder():
    """SentenceTransformer 싱글톤(최초 1회 모델 로드)."""
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer(config.RAG_EMBED_MODEL)
    return _MODEL


def embed(texts):
    """문장 리스트 → 정규화된 임베딩(코사인용) 리스트."""
    model = _embedder()
    return model.encode(list(texts), normalize_embeddings=True).tolist()


def _client():
    import chromadb
    from chromadb.config import Settings
    # 익명 텔레메트리 OFF — 오프라인 정책 + chromadb의 OpenTelemetry/protobuf 충돌 회피
    return chromadb.PersistentClient(
        path=config.RAG_PERSIST_DIR,
        settings=Settings(anonymized_telemetry=False),
    )


def get_collection(reset=False):
    """근거 문서 컬렉션 핸들. reset=True면 기존 인덱스를 지우고 새로 만든다."""
    client = _client()
    if reset:
        try:
            client.delete_collection(config.RAG_COLLECTION)
        except Exception:
            pass
    return client.get_or_create_collection(
        config.RAG_COLLECTION, metadata={"hnsw:space": "cosine"})


def build_index(ref_dir=None):
    """근거 PDF 적재 → 청킹 → 임베딩 → Chroma 적재. 통계 dict 반환."""
    pages = ingestion.load_pages(ref_dir)
    chunks = chunking.chunk_pages(pages)
    if not chunks:
        return {"pdfs": 0, "pages": len(pages), "chunks": 0, "sources": []}

    col = get_collection(reset=True)
    col.add(
        ids=[c["chunk_id"] for c in chunks],
        documents=[c["text"] for c in chunks],
        embeddings=embed([c["text"] for c in chunks]),
        metadatas=[{k: c[k] for k in _META_KEYS} for c in chunks],
    )
    sources = sorted({c["source"] for c in chunks})
    return {"pdfs": len(sources), "pages": len(pages), "chunks": len(chunks), "sources": sources}
