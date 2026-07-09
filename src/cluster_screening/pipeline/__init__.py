"""한 기업의 구비서류를 받아 분류·추출·판정까지 수행하는 오케스트레이터."""
import os
import shutil
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml

from .. import config
from . import classify, extract_cache, extract_fields, ingest, masking

_RULES = None

# 필드 추출이 필요 없는(완비성 '존재'만 확인하는) 유형 — 파일명으로 식별되면 OCR 생략(속도)
# (4대보험·고용보험 명부는 고용인력=연번 추출이 필요하므로 제외하지 않음)
NO_FIELD_TYPES = {"사업계획서", "주주명부", "개인정보수집이용동의서"}

# 사람이 직접 확인해야 하는 추출방식(사유):
#  - scan: 스캔·이미지 문서를 외부 AI 전송 보류(개인정보 보호) → 원본을 사람이 직접 확인
#  - ocr/docling: 로컬 OCR로 판독했으나 오독 가능 → 원본과 대조 확인
REVIEW_REASONS = {
    "scan": "개인정보 포함 가능성 — 외부 AI 전송 보류, 직접 확인 필요",
    "ocr": "OCR 판독(오독 가능) — 원본 대조 확인 필요",
    "docling": "OCR 판독(오독 가능) — 원본 대조 확인 필요",
}


def cleanup(record):
    """처리 후 임시 작업 디렉터리(추출된 구비서류 원문=PII) 삭제. 호출부에서 finally로 호출."""
    wd = (record or {}).get("_workdir")
    if wd and os.path.isdir(wd):
        shutil.rmtree(wd, ignore_errors=True)


def load_rules(path=None):
    global _RULES
    path = path or os.path.join(os.path.dirname(__file__), "..", "rules.yaml")
    with open(path, encoding="utf-8") as f:
        _RULES = yaml.safe_load(f)
    return _RULES


def process_company(src_path, apply_date=None, pw="", progress=None, workdir=None):
    """src_path: zip/폴더/PDF. 반환: record(분류·추출 결과 포함, 임시경로는 record['_workdir']).
    추출은 내용해시 캐시 + 파일 단위 병렬. progress(done, total, message)로 단계별 로그를 흘린다."""
    rules = _RULES or load_rules()
    masking.reset_audit()   # 이번 실행의 PII 마스킹 감사 기록 초기화(외부 전송 전 검증 로그 수집)
    workdir = workdir or tempfile.mkdtemp(prefix="cluster_")
    pdfs = ingest.extract_all(src_path, workdir=workdir, pw=pw)
    n = len(pdfs)
    t_all = time.perf_counter()

    def log(done, msg):
        if progress:
            progress(done, n, msg)

    log(0, f"압축 해제 완료 — PDF {n}개 (워커 {config.EXTRACT_WORKERS})")

    # 1) 파일명 1차 분류 → 필드 불필요 유형은 OCR 생략, 나머지만 추출 대상
    plan = [(p, classify.classify(p, "")[0]) for p in pdfs]
    need = [p for p, t in plan if t not in NO_FIELD_TYPES]

    # 2) 추출(내용해시 캐시 + 파일 병렬) — 완료되는 대로 로그
    extracted = {}
    done = 0
    workers = max(1, config.EXTRACT_WORKERS)

    def _extract_timed(p):
        t0 = time.perf_counter()
        ext = extract_cache.extract(p)
        return ext, round(time.perf_counter() - t0, 2)

    def _record(p, ext, secs):
        nonlocal done
        done += 1
        tag = "캐시" if ext.get("cached") else ext.get("method", "")
        log(done, f"[{done}/{n}] {os.path.basename(p)} · {tag} · {len(ext.get('text') or '')}자 · {secs}s")

    if workers > 1 and len(need) > 1:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(_extract_timed, p): p for p in need}
            for fut in as_completed(futs):
                p = futs[fut]
                ext, secs = fut.result()
                extracted[p] = ext
                _record(p, ext, secs)
    else:
        for p in need:
            ext, secs = _extract_timed(p)
            extracted[p] = ext
            _record(p, ext, secs)

    # 3) 조립(원래 순서) — 분류·필드추출
    docs, doc_log = {}, []
    for p, typ_fn in plan:
        if typ_fn in NO_FIELD_TYPES:
            ext = {"text": "", "method": "filename", "pages": None}
            typ, conf, fields = typ_fn, 1.0, {}
            done += 1
            log(done, f"[{done}/{n}] {os.path.basename(p)} · 파일명분류({typ}) · OCR생략")
        else:
            ext = extracted[p]
            typ, conf = classify.classify(p, ext["text"])
            fields = (extract_fields.extract_fields(typ, ext["text"], ext.get("pages_text"))
                      if typ != "미분류" else {})
        nchars = len(ext.get("text") or "")
        method = ext["method"]
        # 불러옴: 추출 성공(text/ocr) 또는 파일명 생략(존재 확인).
        #  method 'none'=실패, 'scan'=정책상 외부전송 보류 → 둘 다 X(사람 확인 대상)
        loaded = method == "filename" or (method not in ("none", "scan") and nchars > 0)
        entry = {"present": True, "file": os.path.basename(p), "method": method,
                 "confidence": conf, "fields": fields, "pages": ext.get("pages")}
        if typ not in docs or len(fields) > len(docs[typ].get("fields", {})):  # 중복 시 필드 많은 것
            docs[typ] = entry
        doc_log.append({"file": entry["file"], "유형": typ, "신뢰도": conf,
                        "추출방식": method, "글자수": nchars, "필드수": len(fields),
                        "불러옴": "O" if loaded else "X",
                        # 스캔·이미지/OCR 판독 등 사람이 직접 확인해야 하는 사유(없으면 빈 값)
                        "직접확인": REVIEW_REASONS.get(method, "")})

    log(n, f"분석 완료 — 총 {round(time.perf_counter() - t_all, 1)}s · 판정 중…")
    if apply_date is None:  # 신청일: 인자 우선, 없으면 입주신청서에서
        apply_date = docs.get("입주신청서", {}).get("fields", {}).get("신청일")
    record = {"docs": docs, "apply_date": apply_date, "doc_log": doc_log,
              "n_pdfs": n, "_workdir": workdir}
    return record, rules
