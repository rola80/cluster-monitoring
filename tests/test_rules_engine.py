"""룰엔진(결정형 판정) 회귀 테스트. 판정값: 적합/부적합/확인필요/해당없음."""
from datetime import date
import pytest
from cluster_screening.pipeline import rules_engine as re_


# 필수 공통서류(법인 조건부 2종 제외) 7종 — 개인사업자 완비 기본셋
COMMON7 = ["사업계획서", "사업자등록증", "재무제표_부가세과세표준증명원",
           "인감증명서", "국세지방세납세증명서", "4대보험가입자명부", "개인정보수집이용동의서"]


# ── _entity_type ──
def test_entity_type_개인(make_record, make_doc):
    rec = make_record({"사업자등록증": make_doc(사업자등록번호="123-45-67890")})
    assert re_._entity_type(rec) == "개인"


def test_entity_type_법인_등기부존재(make_record, make_doc):
    rec = make_record({"법인등기부등본": make_doc()})
    assert re_._entity_type(rec) == "법인"


def test_entity_type_법인_법인등록번호로감지(make_record, make_doc):
    rec = make_record({"사업자등록증": make_doc(법인등록번호="110111-1234567")})
    assert re_._entity_type(rec) == "법인"


# ── check_completeness (조건부 필수) ──
def test_completeness_개인_7종완비_적합(rules, make_record, make_doc):
    rec = make_record({t: make_doc() for t in COMMON7})
    r = re_.check_completeness(rec, rules)
    assert r["status"] == "적합"


def test_completeness_개인_누락_부적합(rules, make_record, make_doc):
    docs = {t: make_doc() for t in COMMON7 if t != "인감증명서"}
    r = re_.check_completeness(make_record(docs), rules)
    assert r["status"] == "부적합"
    assert "인감증명서" in r["detail"]


def test_completeness_법인_등기부주주명부없으면_부적합(rules, make_record, make_doc):
    # 법인등록번호로 법인 판정 → 등기부·주주명부가 필수가 됨
    docs = {t: make_doc() for t in COMMON7}
    docs["사업자등록증"] = make_doc(법인등록번호="110111-1234567")
    r = re_.check_completeness(make_record(docs), rules)
    assert r["status"] == "부적합"
    assert "법인등기부등본" in r["detail"] and "주주명부" in r["detail"]


def test_completeness_법인_9종완비_적합(rules, make_record, make_doc):
    docs = {t: make_doc() for t in COMMON7 + ["주주명부"]}
    docs["사업자등록증"] = make_doc(법인등록번호="110111-1234567")
    docs["법인등기부등본"] = make_doc()
    r = re_.check_completeness(make_record(docs), rules)
    assert r["status"] == "적합"


# ── check_business_age ──
def test_business_age_5년_적합(rules, make_record, make_doc):
    rec = make_record({"사업자등록증": make_doc(개업연월일=date(2021, 3, 3))},
                      apply_date=date(2026, 3, 16))
    r = re_.check_business_age(rec, rules)
    assert r["status"] == "적합"
    assert "5.0년" in r["detail"]


def test_business_age_초과_부적합(rules, make_record, make_doc):
    rec = make_record({"사업자등록증": make_doc(개업연월일=date(2010, 1, 1))},
                      apply_date=date(2026, 1, 1))
    assert re_.check_business_age(rec, rules)["status"] == "부적합"


def test_business_age_법인_등기부미추출시_개업연월일폴백(rules, make_record, make_doc):
    # 법인이지만 등기부에 회사성립연월일 없음 → 사업자등록증 개업연월일로 폴백
    docs = {
        "법인등기부등본": make_doc(),  # 회사성립연월일 없음
        "사업자등록증": make_doc(법인등록번호="110111-1234567", 개업연월일=date(2022, 5, 1)),
    }
    r = re_.check_business_age(make_record(docs, apply_date=date(2026, 1, 1)), rules)
    assert r["status"] == "적합"
    assert "폴백" in r["evidence"]


def test_business_age_날짜없으면_확인필요(rules, make_record, make_doc):
    rec = make_record({"사업자등록증": make_doc()}, apply_date=date(2026, 1, 1))
    assert re_.check_business_age(rec, rules)["status"] == "확인필요"


def test_business_age_경계_정확히7주년은_적합(rules, make_record, make_doc):
    # 달력 기준: 신청일이 기준일의 7주년이면 '7년 이내'로 적합(자동 거절 금지).
    rec = make_record({"사업자등록증": make_doc(개업연월일=date(2019, 1, 1))},
                      apply_date=date(2026, 1, 1))
    assert re_.check_business_age(rec, rules)["status"] == "적합"


def test_business_age_경계_7주년_하루지나면_부적합(rules, make_record, make_doc):
    rec = make_record({"사업자등록증": make_doc(개업연월일=date(2019, 1, 1))},
                      apply_date=date(2026, 1, 2))
    assert re_.check_business_age(rec, rules)["status"] == "부적합"


def test_business_age_윤일_2_29_기준(rules, make_record, make_doc):
    # 기준일 2/29 → 7년 뒤(2027-02-28)까지 적합, 그 다음날 부적합
    rec_ok = make_record({"사업자등록증": make_doc(개업연월일=date(2020, 2, 29))},
                         apply_date=date(2027, 2, 28))
    assert re_.check_business_age(rec_ok, rules)["status"] == "적합"


# ── check_venture ──
def test_venture_확인서있으면_적합(rules, make_record, make_doc):
    rec = make_record({"벤처기업확인서": make_doc()})
    assert re_.check_venture(rec, rules)["status"] == "적합"


def test_venture_없으면_해당없음(rules, make_record):
    assert re_.check_venture(make_record({}), rules)["status"] == "해당없음"


# ── check_tax_arrears ──
def test_tax_체납없음_적합(rules, make_record, make_doc):
    rec = make_record({"국세지방세납세증명서": make_doc(체납상태="체납없음")})
    assert re_.check_tax_arrears(rec, rules)["status"] == "적합"


def test_tax_체납있음_부적합(rules, make_record, make_doc):
    rec = make_record({"국세지방세납세증명서": make_doc(체납상태="체납있음")})
    assert re_.check_tax_arrears(rec, rules)["status"] == "부적합"


def test_tax_미제출_부적합(rules, make_record):
    assert re_.check_tax_arrears(make_record({}), rules)["status"] == "부적합"


def test_tax_상태불명_확인필요(rules, make_record, make_doc):
    rec = make_record({"국세지방세납세증명서": make_doc()})  # 체납상태 미추출
    assert re_.check_tax_arrears(rec, rules)["status"] == "확인필요"


# ── check_consistency ──
def test_consistency_사업자번호일치_적합(rules, make_record, make_doc):
    docs = {
        "사업자등록증": make_doc(사업자등록번호="123-45-67890", 상호="에이비알", 대표자="홍길동"),
        "입주신청서": make_doc(사업자등록번호="123-45-67890", 기업명="에이비알", 대표자="홍길동"),
    }
    assert re_.check_consistency(make_record(docs), rules)["status"] == "적합"


def test_consistency_사업자번호불일치_부적합(rules, make_record, make_doc):
    docs = {
        "사업자등록증": make_doc(사업자등록번호="123-45-67890"),
        "국세지방세납세증명서": make_doc(사업자등록번호="999-99-99999"),
    }
    assert re_.check_consistency(make_record(docs), rules)["status"] == "부적합"


def test_consistency_대표자불일치_확인필요(rules, make_record, make_doc):
    docs = {
        "사업자등록증": make_doc(사업자등록번호="123-45-67890", 대표자="홍길동"),
        "입주신청서": make_doc(사업자등록번호="123-45-67890", 대표자="김철수"),
    }
    assert re_.check_consistency(make_record(docs), rules)["status"] == "확인필요"


# ── evaluate_bonus ──
def test_bonus_상한5점(rules, make_record, make_doc):
    # 특허(2)+사회적기업(2)+인증(2)+녹색채권(3) = 9 → 상한 5
    docs = {"특허증빙": make_doc(), "사회적기업인증서": make_doc(),
            "인증서": make_doc(), "한국형녹색채권증빙": make_doc()}
    rows, total = re_.evaluate_bonus(make_record(docs), rules)
    assert total == rules["meta"]["bonus_cap"] == 5


def test_bonus_증빙없으면_0점(rules, make_record):
    rows, total = re_.evaluate_bonus(make_record({}), rules)
    assert total == 0


# ── evaluate_performance ──
def test_performance_특허건수_집계(rules, make_record, make_doc):
    doc_log = [{"file": "p1.pdf", "유형": "특허증빙", "신뢰도": .9, "추출방식": "text", "필드수": 0},
               {"file": "p2.pdf", "유형": "특허증빙", "신뢰도": .9, "추출방식": "text", "필드수": 0}]
    rec = make_record({"특허증빙": make_doc()}, doc_log=doc_log)
    rows = re_.evaluate_performance(rec, rules)
    patent = next(r for r in rows if r["지표"] == "국내특허등록")
    assert patent["상태"] == "집계" and "2건" in patent["집계값"]


def test_performance_재무_확인필요(rules, make_record, make_doc):
    rec = make_record({"재무제표_부가세과세표준증명원": make_doc()})
    rows = re_.evaluate_performance(rec, rules)
    sales = next(r for r in rows if r["지표"] == "매출액")
    assert sales["상태"] == "확인필요"  # 제출됨, 연도별 수치는 사람 확인


def test_performance_근거없으면_미제출(rules, make_record):
    rows = re_.evaluate_performance(make_record({}), rules)
    assert all(r["상태"] == "미제출" for r in rows)


# ── evaluate (종합판정) ──
def _full_pass_record(make_record, make_doc):
    docs = {t: make_doc() for t in COMMON7}
    docs["사업자등록증"] = make_doc(사업자등록번호="123-45-67890", 상호="에이비알",
                                대표자="홍길동", 개업연월일=date(2021, 3, 3))
    docs["국세지방세납세증명서"] = make_doc(체납상태="체납없음", 사업자등록번호="123-45-67890")
    docs["입주신청서"] = make_doc(사업자등록번호="123-45-67890", 기업명="에이비알", 대표자="홍길동")
    return make_record(docs, apply_date=date(2026, 3, 16))


def test_evaluate_적합(rules, make_record, make_doc):
    j = re_.evaluate(_full_pass_record(make_record, make_doc), rules)
    assert j["overall"] == "적합"
    assert all("basis" in r for r in j["results"])  # basis 키 항상 존재
    assert "performance" in j


def test_evaluate_부적합_우선(rules, make_record, make_doc):
    rec = _full_pass_record(make_record, make_doc)
    rec["docs"]["국세지방세납세증명서"]["fields"]["체납상태"] = "체납있음"
    assert re_.evaluate(rec, rules)["overall"] == "부적합"


def test_evaluate_확인필요(rules, make_record, make_doc):
    rec = _full_pass_record(make_record, make_doc)
    # 체납상태 제거 → 확인필요(부적합은 없음)
    del rec["docs"]["국세지방세납세증명서"]["fields"]["체납상태"]
    assert re_.evaluate(rec, rules)["overall"] == "확인필요"
