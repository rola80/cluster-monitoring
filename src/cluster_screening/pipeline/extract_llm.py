"""OpenAI 기반 구조화 추출 — 재무제표 항목(셀) / 4대보험 명부 고용인력(연번 최댓값).

표·연도별 값처럼 정규식이 약한 부분만 LLM으로 '해당 셀 값'과 **그 값이 있는 페이지**를 뽑는다.
사람이 검증할 수 있도록 값과 함께 페이지(근거 위치)를 반환한다. 키 없거나 실패 시 빈 값/폴백.
"""
import json
import re

from .. import config

_RRN = re.compile(r"\d{6}\s*-\s*[1-4]")   # 주민등록번호 앞자리(가입자 수 폴백용)


def _marked(pages_text):
    """페이지별 텍스트 → '[p.N]' 마커가 붙은 단일 텍스트(LLM이 페이지를 알 수 있게)."""
    if isinstance(pages_text, str):
        pages_text = [pages_text]
    return "\n".join(f"[p.{i + 1}]\n{t}" for i, t in enumerate(pages_text or []) if t)


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
    """재무제표 → ({항목: {연도: 정수}}, page). 지정 항목의 '해당 셀'만 + 값이 있는 페이지."""
    items = items or config.FINANCIAL_ITEMS
    text = _marked(pages_text)
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
    """4대보험/고용보험 명부 → (고용인력, page). 고용인력=연번 일련번호의 마지막(최댓값)."""
    text = _marked(pages_text)
    if not text.strip():
        return None, None
    out = _chat_json(
        "다음은 4대보험(또는 고용보험) 가입자명부다([p.N]은 페이지). 가입자(근로자) 수 = "
        '연번(일련번호) 컬럼의 마지막 값(최댓값)을 정수로, 그 값이 있는 페이지도. '
        '오직 JSON만: {"고용인력": 정수 또는 null, "page": 페이지번호 또는 null}.\n\n' + text[:8000])
    if isinstance(out, dict) and isinstance(out.get("고용인력"), int):
        return out["고용인력"], out.get("page")
    n = len(_RRN.findall(text))   # 폴백: 주민번호 개수 = 인원
    return (n or None), None
