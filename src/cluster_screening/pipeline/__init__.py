"""한 기업의 구비서류를 받아 분류·추출·판정까지 수행하는 오케스트레이터."""
import os
import shutil
import tempfile

import yaml

from . import classify, extract_fields, extract_text, ingest

_RULES = None


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
    """src_path: zip/폴더/PDF. 반환: record(분류·추출 결과 포함, 임시경로는 record['_workdir'])."""
    rules = _RULES or load_rules()
    workdir = workdir or tempfile.mkdtemp(prefix="cluster_")
    pdfs = ingest.extract_all(src_path, workdir=workdir, pw=pw)
    docs = {}
    doc_log = []
    for i, p in enumerate(pdfs):
        if progress:
            progress(i, len(pdfs), os.path.basename(p))
        ext = extract_text.extract(p)
        typ, conf = classify.classify(p, ext["text"])
        fields = extract_fields.extract_fields(typ, ext["text"]) if typ != "미분류" else {}
        entry = {"present": True, "file": os.path.basename(p), "method": ext["method"],
                 "confidence": conf, "fields": fields, "pages": ext.get("pages")}
        # 동일 유형 중복 시 필드가 더 많은 것을 채택
        if typ not in docs or len(fields) > len(docs[typ].get("fields", {})):
            docs[typ] = entry
        doc_log.append({"file": entry["file"], "유형": typ, "신뢰도": conf,
                        "추출방식": ext["method"], "필드수": len(fields)})

    # 신청일: 인자 우선, 없으면 입주신청서에서
    if apply_date is None:
        apply_date = docs.get("입주신청서", {}).get("fields", {}).get("신청일")

    record = {"docs": docs, "apply_date": apply_date, "doc_log": doc_log,
              "n_pdfs": len(pdfs), "_workdir": workdir}
    return record, rules
