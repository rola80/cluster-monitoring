"""판정 엔진. rules.yaml의 criterion별 check 함수를 실행해 결과를 낸다.
판정값: 적합 / 부적합 / 확인필요 / 해당없음. 모든 결과에 근거(evidence)를 남긴다(감사 가능)."""
import re
from datetime import date

from .extract_fields import normalize_name


def _collect(record, field, sources=None):
    """서류에서 동일 필드값을 (서류, 값)으로 수집. sources 지정 시 해당 유형만."""
    out = []
    for dt, d in record["docs"].items():
        if sources and dt not in sources:
            continue
        v = d.get("fields", {}).get(field)
        if v:
            out.append((dt, v))
    return out


def _entity_type(record):
    docs = record["docs"]
    if "법인등기부등본" in docs or any(
            d.get("fields", {}).get("법인등록번호") for d in docs.values()):
        return "법인"
    return "개인"


def R(status, detail, evidence=""):
    return {"status": status, "detail": detail, "evidence": evidence}


def _add_years(d, n):
    """달력 기준 n년 뒤 날짜(기준일의 n주년). 2/29는 비윤년에서 2/28로."""
    try:
        return d.replace(year=d.year + n)
    except ValueError:  # 2월 29일 → 해당 연도에 없음
        return d.replace(year=d.year + n, day=28)


# ── criterion checks ──
def check_completeness(record, rules):
    et = _entity_type(record)
    # when: 법인 인 서류(법인등기부·주주명부)는 법인사업자에 한해 필수
    req = [r for r in rules["required_docs"] if r.get("when") in (None, et)]
    present = set(record["docs"].keys())
    missing = [r["name"] for r in req if r["name"] not in present]
    n = len(req)
    got = len(present & {r["name"] for r in req})
    if missing:
        return R("부적합", f"필수서류 누락: {', '.join(missing)}", f"제출 {got}/{n}종 (구분:{et})")
    return R("적합", "필수 공통서류 완비", f"{n}/{n}종 제출 (구분:{et})")


def check_business_age(record, rules):
    yrs = rules["meta"]["business_age_years"]
    et = _entity_type(record)
    apply_d = record.get("apply_date")
    docs = record["docs"]
    base, src = None, ""
    if et == "법인":
        base = docs.get("법인등기부등본", {}).get("fields", {}).get("회사성립연월일")
        src = "법인등기부 회사성립연월일"
        if not base:  # 등기부 스캔 등으로 미추출 시 개업연월일로 폴백
            base = docs.get("사업자등록증", {}).get("fields", {}).get("개업연월일")
            src = "사업자등록증 개업연월일(등기부 미추출 폴백)"
    else:
        base = docs.get("사업자등록증", {}).get("fields", {}).get("개업연월일")
        src = "사업자등록증 개업연월일"
    if not base:
        return R("확인필요", f"{src} 미추출(스캔/OCR 확인 필요)", f"구분:{et}")
    if not apply_d:
        apply_d = date.today()
    years = (apply_d - base).days / 365.25  # 표시용(근사 경과연수)
    # 판정은 달력 기준: 신청일이 '기준일의 7주년'을 지나지 않았으면 7년 이내(경계일 포함=적합).
    # (자동 거절 금지: 365.25 부동소수로 정확히 7년차가 부적합 처리되던 문제 보정)
    limit_date = _add_years(base, yrs)
    ev = f"{src}={base}, 신청일={apply_d}, 7년기준일={limit_date}, 경과={years:.1f}년 (구분:{et})"
    if apply_d <= limit_date:
        return R("적합", f"창업 {years:.1f}년차 (7년 이내)", ev)
    return R("부적합", f"창업 {years:.1f}년 경과 (7년 초과)", ev)


def check_venture(record, rules):
    if "벤처기업확인서" in record["docs"]:
        return R("적합", "벤처기업확인서 제출(유효기간 사람 확인)", "벤처기업 자격 경로")
    return R("해당없음", "벤처기업확인서 미제출 → 창업기업 경로로 판단", "")


def check_tax_arrears(record, rules):
    d = record["docs"].get("국세지방세납세증명서")
    if not d:
        return R("부적합", "납세증명서 미제출", "")
    state = d.get("fields", {}).get("체납상태")
    if state == "체납없음":
        return R("적합", "체납 없음(납세증명)", d.get("fields", {}).get("사업자등록번호", ""))
    if state == "체납있음":
        return R("부적합", "체납 확인됨", "")
    return R("확인필요", "체납문구 미검출(스캔/OCR 확인 필요)", f"method={d.get('method')}")


def check_consistency(record, rules):
    AUTH_BIZNO = {"사업자등록증", "입주신청서", "국세지방세납세증명서", "재무제표_부가세과세표준증명원"}
    AUTH_NAME = {"사업자등록증", "입주신청서", "국세지방세납세증명서"}
    AUTH_CEO = {"사업자등록증", "입주신청서"}

    # 1) 사업자등록번호(강한 식별자) — 불일치 시 부적합
    bizs = _collect(record, "사업자등록번호", AUTH_BIZNO)
    biz_set = {re.sub(r"\D", "", v): dt for dt, v in bizs}
    if len(biz_set) > 1:
        detail = " vs ".join(f"{k}({dt})" for k, dt in biz_set.items())
        return R("부적합", "사업자등록번호 불일치(허위·오기 의심)", detail)

    # 2) 상호·대표자 — 약한 신호(추출 노이즈). 불일치 시 확인필요
    soft = []
    names = [(dt, normalize_name(v)) for dt, v in _collect(record, "상호", AUTH_NAME)]
    names += [(dt, normalize_name(d["fields"]["기업명"])) for dt, d in record["docs"].items()
              if dt in AUTH_NAME and d.get("fields", {}).get("기업명")]
    names = [(dt, n) for dt, n in names if n]
    uniq = {n for _, n in names}
    # 포함관계면 동일로 간주(예: '에이비알' ⊂ '주식회사에이비알')
    if len(uniq) > 1 and not all(any(a in b or b in a for b in uniq if b != a) for a in uniq):
        soft.append("상호 표기 불일치: " + " vs ".join(f"{n}({dt})" for dt, n in names))

    ceos = _collect(record, "대표자", AUTH_CEO)
    ceo_set = {v.replace(" ", "") for _, v in ceos}
    if len(ceo_set) > 1:
        soft.append("대표자 불일치: " + " vs ".join(f"{v}({dt})" for dt, v in ceos))

    if soft:
        return R("확인필요", "상호/대표자 표기 차이 — 사람 확인 권장", " / ".join(soft))

    checked = []
    if bizs:
        checked.append("사업자등록번호")
    if names:
        checked.append("상호")
    if ceos:
        checked.append("대표자")
    return R("적합", "신뢰서류 간 핵심정보 일치", f"대조필드: {', '.join(checked) or '없음'}")


CHECKS = {f.__name__: f for f in
          [check_completeness, check_business_age, check_venture,
           check_tax_arrears, check_consistency]}


def evaluate_bonus(record, rules):
    rows, total = [], 0
    for b in rules.get("bonus", []):
        doc = b.get("doc")
        present = bool(doc) and doc in record["docs"]
        # 인증서는 일반 '인증서' 유형 + 사회적기업/벤처 등 세분 유형 포함
        if b["id"] == "B3":
            present = any(t in record["docs"] for t in ["인증서"])
        if b["id"] == "B2":
            present = "사회적기업인증서" in record["docs"]
        pts = b["points"] if present and b["points"] > 0 else 0
        if present and b["points"] > 0:
            total += pts
        rows.append({
            "id": b["id"], "항목": b["name"], "배점": b["points"],
            "증빙제출": "O" if present else "X",
            "잠정점수": pts if present else 0,
            "비고": ("유효성 사람 확인" if present else "") + (f" / {b['note']}" if b.get("note") else ""),
        })
    total = min(total, rules["meta"]["bonus_cap"])
    return rows, total


def evaluate_performance(record, rules):
    """성과 년도별 정리: 근거서류 제출 여부를 확인하고 집계 가능한 항목(건수)은 자동 집계.
    연도별 금액·인원 등 정밀 수치는 추출 신뢰도 문제로 '확인필요'(사람 확인)로 둔다."""
    # docs 는 유형당 1건만 보존하므로 건수는 doc_log(전체 파일)에서 유형별로 센다.
    counts = {}
    for d in record.get("doc_log", []):
        counts[d.get("유형")] = counts.get(d.get("유형"), 0) + 1
    rows = []
    for p in rules.get("performance", []):
        srcs = p.get("source", [])
        present = [s for s in srcs if s in record["docs"]]
        n_docs = sum(counts.get(s, 0) for s in srcs)
        if not present:
            status, value, note = "미제출", "", "근거서류 미제출 → 확인필요"
        elif p.get("extract") == "count":
            status, value, note = "집계", f"{n_docs}건(서류 기준)", "연도·국내/해외 구분은 사람 확인"
        else:  # financial / headcount — 연도별 정밀 수치는 사람 확인
            status, value, note = "확인필요", "", "근거서류 제출됨 / 연도별 수치는 사람 확인"
        rows.append({"id": p["id"], "지표": p["name"], "단위": p.get("unit", ""),
                     "근거서류": " / ".join(srcs), "제출": "O" if present else "X",
                     "집계값": value, "상태": status, "비고": note})
    return rows


def _basis_lookup(query):
    """(A) RAG에서 판정 근거 조항을 찾아 evidence에 첨부.
    rag 미설치/인덱스 없음/오류 시 조용히 '' 반환(우아한 degradation — 파이프라인은 그대로 동작)."""
    from .. import config
    if not getattr(config, "ENABLE_RAG_BASIS", False) or not query:
        return ""
    try:
        from ..rag import retriever
        return retriever.evidence_for(query)
    except Exception:
        return ""


def evaluate(record, rules):
    results = []
    for c in rules["criteria"]:
        fn = CHECKS.get(c["check"])
        res = fn(record, rules) if fn else R("확인필요", "미구현 check", c["check"])
        basis = _basis_lookup(c.get("basis") or f'{c["name"]} {c.get("detail", "")}')
        results.append({"id": c["id"], "section": c["section"], "name": c["name"],
                        "basis": basis, **res})
    bonus_rows, bonus_total = evaluate_bonus(record, rules)
    performance = evaluate_performance(record, rules)  # 성과표(종합판정에는 영향 없음)

    statuses = [r["status"] for r in results]
    if "부적합" in statuses:
        overall = "부적합"
    elif "확인필요" in statuses:
        overall = "확인필요"
    else:
        overall = "적합"
    return {"results": results, "bonus": bonus_rows, "bonus_total": bonus_total,
            "performance": performance, "overall": overall}
