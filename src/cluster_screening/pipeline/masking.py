"""개인정보(PII) 마스킹 — 하이브리드 방식.

두 지점에서 마스킹한다:
1. **분석 전(외부 전송 전)**: 재무제표·명부 등을 OpenAI로 보내기 전에 `mask_pii`로 주민/법인번호·
   전화·이메일을 가린다(extract_llm에서 호출). → 민감 PII가 외부로 나가지 않음.
   필요한 숫자(매출·연번)는 마스킹 대상이 아니라 보존된다.
2. **출력**: 사람이 보는 판정 결과/리포트에 `mask_judgment`로 성명 + 구조화 PII를 가린다.

대조에 필요한 식별정보(사업자번호·대표자·상호)는 원본으로 판정한 뒤 출력에서만 마스킹한다.
- 주민/법인 등록번호(13자리): 앞 6자리만 남기고 뒤 7자리 마스킹.
- 성명(대표자 등 알려진 이름): 첫 글자만 남기고 마스킹.
- 전화·이메일: 마스킹.
※ 사업자등록번호(###-##-#####)는 사업체 식별자라 마스킹하지 않는다(대조에 필요).
"""
import re

from .. import config

_RRN = re.compile(r"(\d{6})[-\s]?\d{7}")          # 주민/법인등록번호(13자리)
_PHONE = re.compile(r"01[016789][-\s]?\d{3,4}[-\s]?\d{4}")
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")


def mask_pii(text):
    """문자열의 구조화 PII(주민/법인번호·전화·이메일) 마스킹."""
    if not text or not config.ENABLE_PII_MASKING:
        return text
    t = _RRN.sub(r"\1-*******", text)
    t = _PHONE.sub("010-****-****", t)
    t = _EMAIL.sub("***@***", t)
    return t


def mask_name(name):
    """성명 마스킹: 홍길동 → 홍○○, 김수 → 김○."""
    name = (name or "").strip()
    if not config.ENABLE_PII_MASKING or len(name) <= 1:
        return name
    return name[0] + "○" * (len(name) - 1)


def _redact(text, names):
    """알려진 이름 + 구조화 PII 마스킹."""
    if not text or not config.ENABLE_PII_MASKING:
        return text
    for nm in sorted((n for n in names if n and len(n) >= 2), key=len, reverse=True):
        text = text.replace(nm, mask_name(nm))
    return mask_pii(text)


def mask_judgment(judgment, record):
    """판정 결과(사람이 보는 문자열)에 마스킹 적용. record에서 알려진 이름(대표자)을 수집해 리댁션.
    원본 판정은 이미 끝났으므로 결과 문자열만 가린다."""
    if not config.ENABLE_PII_MASKING:
        return judgment
    names = {d.get("fields", {}).get(k)
             for d in record.get("docs", {}).values() for k in ("대표자", "성명")}
    names.discard(None)
    for r in judgment.get("results", []):
        r["detail"] = _redact(r.get("detail", ""), names)
        r["evidence"] = _redact(r.get("evidence", ""), names)
        r["basis"] = mask_pii(r.get("basis", ""))
    for p in judgment.get("performance", []):
        p["집계값"] = _redact(p.get("집계값", ""), names)
        p["근거(파일·페이지)"] = mask_pii(p.get("근거(파일·페이지)", ""))
    return judgment
