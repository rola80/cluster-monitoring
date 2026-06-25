"""테스트 공용 픽스처/헬퍼.

룰엔진 단위테스트는 결정형 판정만 검증한다 → RAG 근거첨부는 끄고(빠르고 결정적),
실제 rules.yaml을 정답 규칙표로 사용한다.
"""
import pytest

from cluster_screening import config, pipeline


@pytest.fixture(autouse=True)
def _disable_rag_basis(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_RAG_BASIS", False)


@pytest.fixture(scope="session")
def rules():
    return pipeline.load_rules()


@pytest.fixture
def make_doc():
    """서류 1건(추출 필드 포함) 생성 팩토리."""
    def _doc(**fields):
        return {"present": True, "file": "x.pdf", "method": "text",
                "confidence": 0.9, "fields": dict(fields), "pages": 1}
    return _doc


@pytest.fixture
def make_record():
    """판정 입력 record 생성 팩토리. doc_log 미지정 시 docs로부터 1건씩 생성."""
    def _rec(docs=None, apply_date=None, doc_log=None):
        docs = docs or {}
        if doc_log is None:
            doc_log = [{"file": f"{t}.pdf", "유형": t, "신뢰도": 0.9,
                        "추출방식": "text", "필드수": len(d.get("fields", {}))}
                       for t, d in docs.items()]
        return {"docs": docs, "apply_date": apply_date, "doc_log": doc_log,
                "n_pdfs": len(doc_log)}
    return _rec
