"""개인정보(PII) 마스킹."""
import pytest

from cluster_screening import config
from cluster_screening.pipeline import masking


@pytest.fixture(autouse=True)
def _on(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_PII_MASKING", True)


def test_주민_법인번호_마스킹():
    assert masking.mask_pii("법인 110111-1234567") == "법인 110111-*******"
    assert masking.mask_pii("주민 8001011234567") == "주민 800101-*******"


def test_사업자번호는_유지():
    assert masking.mask_pii("사업자 123-45-67890") == "사업자 123-45-67890"


def test_성명_마스킹():
    assert masking.mask_name("홍길동") == "홍○○"
    assert masking.mask_name("김수") == "김○"


def test_masking_off(monkeypatch):
    monkeypatch.setattr(config, "ENABLE_PII_MASKING", False)
    assert masking.mask_pii("110111-1234567") == "110111-1234567"
    assert masking.mask_name("홍길동") == "홍길동"


def test_mask_judgment_결과_리댁션():
    record = {"docs": {"사업자등록증": {"fields": {"대표자": "홍길동"}}}}
    judgment = {"results": [{"detail": "대표자 홍길동 확인",
                             "evidence": "법인 110111-1234567", "basis": ""}],
                "performance": []}
    masking.mask_judgment(judgment, record)
    r = judgment["results"][0]
    assert "홍○○" in r["detail"] and "홍길동" not in r["detail"]
    assert "110111-*******" in r["evidence"]
