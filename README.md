# 창업·벤처 녹색융합클러스터 — 입주 신청서류 적합 검토기 (MVP)

기업별 구비서류(zip/PDF)를 넣으면 **모집공고·운영규정·관리지침의 판단기준**에 따라
신청요건 적합 여부를 자동 검토하고, 근거가 달린 **판정 리포트(xlsx)**를 만든다.

판정 흐름: `구비서류 → (중첩 zip 해제) → 서류 분류 → 하이브리드 텍스트 추출(텍스트레이어/OCR)
→ 필드 추출 → 룰엔진 판정 → 리포트`

## 1. 설치

```bash
pip install -r requirements.txt

# 스캔 PDF용 한글 OCR (선택, 강력 권장)
#  Ubuntu:  sudo apt-get install tesseract-ocr tesseract-ocr-kor poppler-utils
#  macOS :  brew install tesseract tesseract-lang poppler
```

## 2. 실행

### Streamlit UI
```bash
streamlit run cluster_screening/app.py
```
사이드바에서 기업명·신청일·zip 비밀번호를 넣고, 구비서류(zip 또는 PDF 여러 개)를 업로드 → "검토 실행".

### CLI
```bash
python -m cluster_screening.cli <폴더|zip|pdf> --name 기업명 --apply 2026-03-16 --pw 비밀번호 --out 판정결과.xlsx
```

## 3. 환경설정 (환경변수)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `ENABLE_OCR` | `1` | 스캔 PDF OCR 사용 여부 |
| `OCR_LANG` | `kor+eng` | tesseract 언어 |
| `OCR_DPI` | `300` | 래스터화 해상도 |
| `OPENAI_API_KEY` | (없음) | 설정 시 LLM 필드추출 폴백 활성 |
| `LLM_MODEL` | `gpt-4.1-mini` | 텍스트 필드추출 워크호스 |
| `LLM_MODEL_VISION` | `gpt-4.1` | 스캔 OCR 비전 폴백 |
| `ZIP_PASSWORD` | (없음) | 구비서류 zip 비밀번호 |

OCR/LLM이 없어도 동작한다(텍스트 레이어가 있는 PDF는 그대로 처리, 스캔본은 `확인필요`로 표시).

## 4. 판단기준 ↔ 코드 매핑

판단기준은 `rules.yaml`에 표로 정의되어 있고, 각 기준의 `check` 값은
`pipeline/rules_engine.py`의 동명 함수와 1:1로 연결된다(감사 가능한 결정형 규칙).

| 기준 | check 함수 | 핵심 로직 |
|---|---|---|
| 창업 7년 이내 | `check_business_age` | 법인=회사성립연월일(없으면 개업연월일), 개인=개업연월일, 신청일과 비교 |
| 벤처기업 자격 | `check_venture` | 벤처기업확인서 제출 여부 |
| 국세·지방세 체납 | `check_tax_arrears` | 납세증명서 체납문구 검출 |
| 허위·부정(일치) | `check_consistency` | 신뢰서류 간 사업자번호/상호/대표자 일치 |
| 필수서류 완비 | `check_completeness` | 필수 공통서류 7종 제출 |
| 가점/감점 | `evaluate_bonus` | 증빙 제출 시 잠정 점수(합산 최대 5점), 유효성은 사람 확인 |

판정값: **적합 / 부적합 / 확인필요 / 해당없음**. 모든 결과에 근거(evidence)가 기록된다.

## 5. 한계와 설계 원칙

- **자동 거절 금지**: 추출 신뢰도가 낮거나 스캔본은 `부적합`이 아니라 `확인필요`로 표시한다.
- 가점·유효기간·녹색산업 분야 적합성 등 판단 여지가 큰 항목은 사람이 최종 확인한다.
- 정부 발급 서류는 라벨 고정 → 앵커/정규식 추출이 1순위, 비정형·OCR보정은 LLM 폴백.
- 분류·추출 정확도는 과거 평가결과를 정답셋으로 측정·개선(Phase 7).

## 6. 구조
```
cluster_screening/
  app.py            Streamlit UI
  cli.py            CLI 실행기
  config.py         설정/토글
  rules.yaml        판단기준(규칙표)
  pipeline/
    ingest.py        (중첩) zip 해제·PDF 수집
    classify.py      서류 분류
    extract_text.py  하이브리드 텍스트 추출(텍스트레이어/OCR)
    extract_fields.py 필드 추출(앵커/정규식 + LLM 폴백)
    rules_engine.py  룰 판정
    report.py        리포트(xlsx) 생성
```
