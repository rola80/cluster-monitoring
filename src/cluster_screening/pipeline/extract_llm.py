"""OpenAI 기반 구조화 추출 — 재무제표 항목(셀) / 4대보험 명부 고용인력(연번 최댓값).

하이브리드 PII 처리: **외부 LLM(OpenAI)로 보내는 텍스트는 전송 직전 `masking.scrub_outbound`로
마스킹 + 검증**한다(주민/법인번호 등이 외부로 나가지 않도록 '분석 전 마스킹'; 잔여 PII 0건 로그 확인).
필요한 숫자(매출·연번)는 마스킹 대상이 아니라 보존된다. 로컬 폴백(주민번호 개수)만 원본을 쓴다.
"""
import json
import re

from .. import config
from . import masking

_RRN = re.compile(r"\d{6}\s*-\s*[1-4]")   # 주민등록번호 앞자리(가입자 수 폴백용, 로컬 전용)


def _aslist(pages_text):
    return [pages_text] if isinstance(pages_text, str) else (pages_text or [])


def _marked(pages_text):
    """페이지별 텍스트 → '[p.N]' 마커 단일 텍스트(마스킹 없음).
    외부 전송용 마스킹·검증은 호출부에서 masking.scrub_outbound로 처리한다."""
    pages = _aslist(pages_text)
    return "\n".join(f"[p.{i + 1}]\n{t}" for i, t in enumerate(pages) if t)


def _chat_json(prompt):
    if not config.OPENAI_API_KEY or not (prompt or "").strip():
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=config.OPENAI_API_KEY)
        r = client.chat.completions.create(
            model=config.FINANCIAL_MODEL,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}, temperature=0)
        return json.loads(r.choices[0].message.content)
    except Exception:
        return None


def extract_financials(pages_text, items=None):
    """재무제표 → ({항목: {연도: 정수}}, page). 외부 전송 텍스트는 마스킹+검증(scrub_outbound)됨."""
    items = items or config.FINANCIAL_ITEMS
    text = masking.scrub_outbound(_marked(pages_text), "재무제표")  # 마스킹+PII 잔여 검증 후 전송
    if not text.strip():
        return {}, None
    out = _chat_json(
        "다음은 한 기업 재무제표(손익계산서 등) 텍스트다([p.N]은 페이지 표시). "
        f"아래 항목의 금액만 연도별로 정확히 추출하라: {', '.join(items)}. "
        "각 값은 해당 셀 숫자만(쉼표·단위 제거, 정수), 없으면 null. 값들이 있는 페이지 번호도. "
        '오직 JSON만: {"data": {"항목명": {"연도": 정수 또는 null}}, "page": 페이지번호 또는 null}.\n\n'
        + text[:8000])
    if not isinstance(out, dict):
        return {}, None
    return (out.get("data") or {}), out.get("page")


def extract_headcount(pages_text):
    """4대보험/고용보험 명부 → (고용인력, page). 외부 전송은 마스킹+검증, 폴백(주민번호 수)은 원본."""
    raw = _marked(pages_text)                        # 폴백 계산용 원본(로컬 전용, 외부 전송 안 함)
    if not raw.strip():
        return None, None
    text = masking.scrub_outbound(raw, "4대보험/고용보험 명부")   # 마스킹+PII 잔여 검증 후 전송
    out = _chat_json(
        "다음은 4대보험(또는 고용보험) 가입자명부다([p.N]은 페이지). 가입자(근로자) 수 = "
        '연번(일련번호) 컬럼의 마지막 값(최댓값)을 정수로, 그 값이 있는 페이지도. '
        '오직 JSON만: {"고용인력": 정수 또는 null, "page": 페이지번호 또는 null}.\n\n' + text[:8000])
    if isinstance(out, dict) and isinstance(out.get("고용인력"), int):
        return out["고용인력"], out.get("page")
    n = len(_RRN.findall(raw))   # 폴백: 원본에서 주민번호 개수 = 인원
    return (n or None), None
