"""파일 내용 해시(SHA-256) 기반 추출 캐시.

OCR 등 추출은 비싸므로, 같은 파일(바이트 동일)을 다시 처리하면 캐시된 결과를 재사용해
재실행이 즉시 끝나게 한다. 캐시 키=파일 내용 해시 → 파일이 하나만 바뀌어도 나머지는 재사용.
"""
import hashlib
import json
import os

from .. import config
from . import extract_text


def _file_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def extract(path):
    """extract_text.extract의 캐시 래퍼. 반환 dict에 'cached'(bool) 표시."""
    if not config.ENABLE_EXTRACT_CACHE:
        return extract_text.extract(path)

    os.makedirs(config.EXTRACT_CACHE_DIR, exist_ok=True)
    cpath = os.path.join(config.EXTRACT_CACHE_DIR, _file_hash(path) + ".json")
    if os.path.exists(cpath):
        try:
            with open(cpath, encoding="utf-8") as f:
                ext = json.load(f)
            ext["cached"] = True
            return ext
        except Exception:
            pass  # 손상 캐시 → 재추출

    ext = extract_text.extract(path)
    ext["cached"] = False
    try:
        with open(cpath, "w", encoding="utf-8") as f:
            json.dump({k: v for k, v in ext.items() if k != "cached"}, f, ensure_ascii=False)
    except Exception:
        pass
    return ext
