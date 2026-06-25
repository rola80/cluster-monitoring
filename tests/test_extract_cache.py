"""추출 캐시: 같은 파일 재처리 시 OCR 생략(캐시 재사용)."""
from cluster_screening import config
from cluster_screening.pipeline import extract_cache


def test_cache_hit(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_EXTRACT_CACHE", True)
    monkeypatch.setattr(config, "EXTRACT_CACHE_DIR", str(tmp_path / "c"))
    f = tmp_path / "a.pdf"
    f.write_bytes(b"hello world bytes")
    calls = {"n": 0}

    def fake(path):
        calls["n"] += 1
        return {"text": "X", "method": "text", "pages": 1}

    monkeypatch.setattr(extract_cache.extract_text, "extract", fake)
    r1 = extract_cache.extract(str(f))
    r2 = extract_cache.extract(str(f))
    assert r1["text"] == r2["text"] == "X"
    assert r1["cached"] is False and r2["cached"] is True
    assert calls["n"] == 1  # 두 번째는 캐시 → 추출 1회만


def test_cache_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "ENABLE_EXTRACT_CACHE", False)
    f = tmp_path / "b.pdf"
    f.write_bytes(b"xyz")
    calls = {"n": 0}

    def fake(path):
        calls["n"] += 1
        return {"text": "Y", "method": "ocr", "pages": 2}

    monkeypatch.setattr(extract_cache.extract_text, "extract", fake)
    extract_cache.extract(str(f))
    extract_cache.extract(str(f))
    assert calls["n"] == 2  # 캐시 off → 매번 추출
