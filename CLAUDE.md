# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 코드 주석·UI·문서·커밋 메시지는 한국어로 유지한다. (기존 컨벤션)

## 목적
창업·벤처 녹색융합클러스터 **입주 신청서류(구비서류)를 받아 신청요건 적합 여부를 자동 검토**하고,
근거(evidence)가 달린 판정 리포트(xlsx)를 생성하는 도구. 판정 근거 문서는 모집공고(제2025-004호),
운영규정(제2·9조), 입주기업 관리지침.

## 실행 / 명령어

이 디렉터리는 `cluster_screening` 패키지이며, **반드시 상위 디렉터리에서 실행**한다
(임포트가 `from cluster_screening import ...` 형태이므로 패키지 루트가 부모 폴더여야 함).

```bash
pip install -r requirements.txt

# Streamlit UI (로그인 게이트 포함)
streamlit run cluster_screening/app.py

# CLI — 단일 기업 판정 → xlsx 리포트
python -m cluster_screening.cli <zip|폴더|pdf> --name 기업명 --apply 2026-03-16 --pw 260529 --out 판정결과.xlsx

# 로그인 계정 관리 (UI는 인증 필수, 등록 사용자 없으면 진입 불가)
python -m cluster_screening.auth add <아이디> [<비밀번호>]   # 비번 생략 시 안전 입력
python -m cluster_screening.auth list
python -m cluster_screening.auth delete <아이디>
```

자동화된 테스트 스위트는 아직 없다. 검증은 실제 구비서류로 CLI를 돌려 `종합판정`을 눈으로 확인하는 방식.
샘플 zip 비밀번호: `260529`.

## 핵심 설계 원칙 (반드시 준수)
- **자동 거절 금지**: 추출 신뢰도가 낮거나 스캔 미해독이면 `부적합`이 아니라 **`확인필요`**로 표시.
- **최종 판정은 결정형 Python 규칙으로** 한다(감사 가능). LLM은 비정형/OCR보정 **필드 추출 폴백에만** 사용,
  판정 로직에는 절대 쓰지 않는다.
- 가점·유효기간·녹색산업 분야 적합성 등 판단 여지가 큰 항목은 **잠정 처리 후 사람이 최종 확인**.
- 모든 판정은 `R(status, detail, evidence)` 형태로 근거를 남긴다.

## 아키텍처 / 데이터 흐름

데이터 흐름: `수집(ingest) → 분류(classify) → 텍스트추출(extract_text) → 필드추출(extract_fields) → 룰판정(rules_engine) → 리포트(report)`

오케스트레이터는 `pipeline/__init__.py`의 `process_company()` — 한 기업의 zip/폴더/PDF를 받아
서류별로 위 단계를 돌려 `record`(docs·apply_date·doc_log)를 만들고, `rules_engine.evaluate(record, rules)`가
종합판정을 낸다. `app.py`(UI)와 `cli.py`는 이 둘을 호출하는 얇은 진입점.

```
cluster_screening/
  app.py            Streamlit UI (auth.streamlit_login_gate 로 인증 후 본문 렌더)
  cli.py            CLI 진입점
  auth.py           로그인(표준 라이브러리 PBKDF2 해시, users.json) + Streamlit 게이트/로그아웃 + 계정 CLI
  config.py         설정 토글 — OCR/LLM/zip비번 전부 환경변수로 제어, .env 자동 로드
  rules.yaml        판단기준 규칙표 (criteria + bonus + required_docs)
  pipeline/
    ingest.py        (중첩) zip 해제·PDF 수집 (pyzipper로 AES zip 대응)
    classify.py      서류 분류 (파일명 힌트 가중치 20 > 본문 키워드)
    extract_text.py  하이브리드 추출: 텍스트레이어(pdfplumber) → 부족하면 OCR(기본 EasyOCR)
    extract_fields.py 앵커/정규식 추출(공백허용 라벨, normalize_name) + LLM 폴백
    rules_engine.py  criterion별 check_* 함수 실행 + evaluate_bonus + 종합판정
    report.py        xlsx 리포트(종합판정/판단기준별/가점/처리내역 4시트)
```

## 판단기준 ↔ 코드 매핑 (가장 중요한 규약)
`rules.yaml`의 각 criterion `check` 값은 `pipeline/rules_engine.py`의 **동명 함수와 1:1**로 연결된다
(`CHECKS` 딕셔너리로 디스패치). **새 판단기준 추가 시: `rules.yaml`에 항목 추가 + `rules_engine.py`에 동명
`check_*(record, rules)` 함수 작성**.

| 기준 | check 함수 | 핵심 로직 |
|---|---|---|
| 창업 7년 이내 | `check_business_age` | 법인=등기부 회사성립연월일(없으면 사업자등록증 개업연월일로 폴백), 개인=개업연월일, 신청일과 비교 |
| 벤처기업 자격 | `check_venture` | 벤처기업확인서 제출 여부 |
| 국세·지방세 체납 | `check_tax_arrears` | 납세증명서 체납상태 필드 |
| 허위·부정(일치) | `check_consistency` | 신뢰서류 간 사업자번호(강식별자, 불일치=부적합)/상호·대표자(약신호, 불일치=확인필요) |
| 필수서류 완비 | `check_completeness` | required_docs 7종 제출 여부 |
| 가점/감점 | `evaluate_bonus` | 증빙 존재 시 잠정 점수, 합산 최대 5점(bonus_cap), 유효성은 사람 확인 |

종합판정 규칙: 하나라도 `부적합`→`부적합`, 아니면 `확인필요` 있으면 `확인필요`, 모두 통과면 `적합`.

## 입력 데이터의 현실 (회귀 방지 — 코드 수정 전 숙지)
- 구비서류는 전부 PDF지만 **혼합형**: 전자문서(텍스트 레이어)와 스캔 이미지(텍스트 없음)가 섞임.
  `config.TEXT_LAYER_MIN_CHARS`(40) 미만이면 스캔으로 간주해 OCR 경로로 보낸다.
- 한글 정부 양식이라 라벨에 **글자 사이 공백**이 흔함("개 업 연 월 일") → `extract_fields`의 공백 허용 매칭.
- **주주명부의 "사업자등록번호"는 회사가 아니라 주주(투자조합)의 번호** → 일치성 검사는 신뢰서류
  (사업자등록증·입주신청서·납세증명서·재무제표)로만 한정. 주주명부에서 식별필드 추출 금지.
- 사업계획서는 본문에 '인증·특허·수상' 단어가 많아 가점서류로 오분류되기 쉬움 → 파일명 힌트가 본문을 압도(가중치 20).
- 중첩 zip + 비밀번호. 일부 문서는 매우 김(매출증빙 200+페이지).

## 환경설정 (config.py / .env)
모든 외부 연동은 토글로 끄고 켤 수 있고, OCR/LLM이 없어도 동작한다(스캔본은 `확인필요`로 표시).

| 변수 | 기본값 | 설명 |
|---|---|---|
| `ENABLE_OCR` | `1` | 스캔 PDF OCR 사용 여부 |
| `OCR_ENGINE` | `easyocr` | `easyocr`(한글 내장·오프라인) 또는 `tesseract` |
| `OCR_LANGS` | `ko,en` | EasyOCR 언어코드 |
| `OPENAI_API_KEY` | (없음) | 설정 시 `ENABLE_LLM` 자동 ON (LLM 필드추출 폴백) |
| `LLM_MODEL` / `LLM_MODEL_VISION` | `gpt-4.1-mini` / `gpt-4.1` | 텍스트 / 스캔 비전 폴백 |
| `ZIP_PASSWORD` | (없음) | 구비서류 zip 기본 비밀번호 |
| `USE_DOCLING` | `0` | 표/레이아웃 복원(무겁고 RAM 큼) |

## 보안 / 비밀
- `auth.py`: 비밀번호는 평문 저장 안 함 — PBKDF2-HMAC-SHA256(200k iter, per-user salt)로 `users.json`에 저장.
- `users.json`, `.env`는 비밀이므로 git에 올리지 않는다(.gitignore 확인).

## 참고: 기존 메모리 파일
`CLAUDE.md.md`(확장자 중복으로 Claude Code가 읽지 않음)에 검증 이력·TODO 후보가 더 자세히 적혀 있다.
프로젝트 진행 상태나 다음 할 일은 그쪽을 참고. (한글 OCR·OpenAI LLM 폴백은 미검증 상태로 기록됨.)
