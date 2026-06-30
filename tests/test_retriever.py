"""RAG 검색 키워드 그라운딩(질의 키워드가 본문에 실제로 있는지)."""
from cluster_screening.rag import retriever


def test_keywords_흔한규정어_제외():
    kw = retriever._keywords("국세 또는 지방세를 체납한 기업 제외")
    assert {"국세", "지방세", "체납한"} <= kw
    assert "기업" not in kw and "또는" not in kw and "제외" not in kw  # stopword


def test_grounded_부분문자열_인정():
    qk = retriever._keywords("국세 지방세 체납")
    assert retriever._grounded("국세 또는 지방세를 체납한 기업은 제외한다.", qk)  # '체납'⊂'체납한'


def test_grounded_키워드없으면_False():
    qk = retriever._keywords("국세 지방세 체납")
    assert not retriever._grounded("기술원장은 위원회를 구성한다.", qk)


def test_grounded_빈질의는_통과():
    assert retriever._grounded("아무 본문", set())
