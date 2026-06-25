"""서류 텍스트에서 핵심 필드 추출. 앵커 라벨 + 정규식 기반."""
import re
from datetime import date

RE_BIZNO = re.compile(r"\d{3}\s*-\s*\d{2}\s*-\s*\d{5}")
RE_CORPNO = re.compile(r"\d{6}\s*-\s*\d{7}")
RE_DATE = re.compile(r"(\d{4})\s*[년.\-/]\s*(\d{1,2})\s*[월.\-/]\s*(\d{1,2})")


def _clean(s):
    return re.sub(r"\s+", " ", s).strip() if s else s


def normalize_name(s):
    """상호 비교용 정규화: 공백·괄호(영문)·법인격 표기 제거."""
    if not s:
        return ""
    s = re.sub(r"\(.*?\)", "", s)        # (ABR Co.,Ltd) 등 괄호 제거
    s = re.sub(r"[A-Za-z.,&]", "", s)     # 영문/기호 제거
    s = s.replace("주식회사", "").replace("(주)", "").replace("㈜", "")
    return re.sub(r"\s+", "", s).strip()


def parse_kdate(s):
    m = RE_DATE.search(s or "")
    if not m:
        return None
    y, mo, d = map(int, m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _label_pos(text, label):
    """'개 업 연 월 일'처럼 글자 사이 공백이 있어도 매칭. 라벨 끝 위치 반환."""
    pat = re.compile(r"\s*".join(map(re.escape, label)))
    m = pat.search(text or "")
    return m.end() if m else -1


def _after(text, anchors, window=40):
    """anchor 라벨(공백 허용) 뒤 window 글자에서 값 후보 반환."""
    text = text or ""
    for a in anchors:
        i = _label_pos(text, a)
        if i != -1:
            seg = text[i: i + window].lstrip(" :：)]}.\t")
            return _clean(seg.split("\n")[0])
    return None


def extract_bizno(text):
    m = RE_BIZNO.search(text or "")
    return re.sub(r"\s", "", m.group()) if m else None


def extract_corpno(text):
    m = RE_CORPNO.search(text or "")
    return re.sub(r"\s", "", m.group()) if m else None


def extract_company_name(text):
    v = _after(text, ["법인명(단체명)", "상         호", "상  호", "상 호", "법인명", "상호", "기업명", "회사명", "명     칭", "명칭"])
    if v:
        v = re.split(r"(대표자|성명|등록번호|소재지|개업|사업장|주민|생년|\d)", v)[0]
        return _clean(v) or None
    return None


def extract_ceo(text):
    v = _after(text, ["대 표 자", "대표자", "대표이사", "성         명", "성  명", "성 명", "성명"])
    if v:
        v = re.split(r"(주민|생년|사업|소재|등록|상호|\d{6})", v)[0]
        return _clean(v)
    return None


def extract_open_date(text):
    # 사업자등록증: 개업연월일 ('개 업 연 월 일' 공백 허용)
    for a in ["개업연월일", "개업일"]:
        i = _label_pos(text or "", a)
        if i != -1:
            return parse_kdate(text[i:i + 60])
    return None


def extract_incorp_date(text):
    # 법인등기부: 회사성립연월일
    for a in ["회사성립연월일", "성립연월일"]:
        i = _label_pos(text or "", a)
        if i != -1:
            return parse_kdate(text[i:i + 80])
    return None


def extract_apply_date(text):
    # 입주신청서: 신청/작성일자
    for a in ["신청일", "작성일", "제출일", "년월일"]:
        i = _label_pos(text or "", a)
        if i != -1:
            d = parse_kdate(text[i:i + 60])
            if d:
                return d
    return parse_kdate(text or "")  # 최후: 문서 내 첫 날짜


def detect_tax_arrears(text):
    """납세증명서: 체납 없음/있음 판단."""
    t = (text or "").replace(" ", "")
    if not t:
        return None
    if "체납액이없" in t or "체납된사실이없" in t or "체납사실이없" in t or "체납액없음" in t:
        return "체납없음"
    if "발급목적" in t or "납세증명" in t:
        # 증명서이긴 한데 체납문구 미검출 → 확인필요
        if "체납" in t:
            return "확인필요"
        return "체납없음"
    return None


# ── 유형별 추출 ──
def extract_fields(doc_type, text):
    f = {}
    if doc_type == "사업자등록증":
        f["사업자등록번호"] = extract_bizno(text)
        f["상호"] = extract_company_name(text)
        f["대표자"] = extract_ceo(text)
        f["개업연월일"] = extract_open_date(text)
    elif doc_type == "법인등기부등본":
        f["상호"] = extract_company_name(text)
        f["법인등록번호"] = extract_corpno(text)
        f["회사성립연월일"] = extract_incorp_date(text)
    elif doc_type == "입주신청서":
        f["기업명"] = extract_company_name(text)
        f["사업자등록번호"] = extract_bizno(text)
        f["대표자"] = extract_ceo(text)
        f["신청일"] = extract_apply_date(text)
    elif doc_type == "국세지방세납세증명서":
        f["사업자등록번호"] = extract_bizno(text)
        f["상호"] = extract_company_name(text)
        f["체납상태"] = detect_tax_arrears(text)
    elif doc_type in ("인감증명서", "재무제표_부가세과세표준증명원"):
        f["사업자등록번호"] = extract_bizno(text)
        f["상호"] = extract_company_name(text)
    # 주주명부는 주주(투자조합 등)의 번호가 섞여 회사 식별필드를 추출하지 않음(존재만 신호)
    # 가점 증빙은 존재 자체를 신호로 사용
    return {k: v for k, v in f.items() if v is not None}
