"""재무/고용인력 추출 — 키 없을 때 폴백 동작."""
from cluster_screening import config
from cluster_screening.pipeline import extract_llm


def test_headcount_fallback_주민번호수(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")  # LLM 미사용 → 폴백
    text = "1 홍길동 800101-1234567\n2 김철수 900202-2345678\n3 이영희 850303-2000000"
    cnt, page = extract_llm.extract_headcount(text)
    assert cnt == 3 and page is None   # 주민번호 3개 = 인원


def test_headcount_빈텍스트는_None():
    assert extract_llm.extract_headcount("") == (None, None)


def test_financials_키없으면_빈딕트(monkeypatch):
    monkeypatch.setattr(config, "OPENAI_API_KEY", "")
    assert extract_llm.extract_financials("손익계산서 매출액 1,000") == ({}, None)
