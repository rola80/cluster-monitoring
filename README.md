# 녹색융합클러스터 입주기업 신청서류 적합성 검토 및 성과 정리 자동화 (cluster_screening)

기업이 제출한 **구비서류(zip·PDF)** 를 넣으면 **수집 → 분류 → 텍스트추출 → 필드추출 → 룰 판정 → 리포트**
까지 처리하고, 공고·운영규정·관리지침을 **RAG로 검색해 판정마다 "근거 조항"을 붙인**
**감사 가능한 판정 리포트(xlsx)** 를 만드는 도구입니다.

![Python](https://img.shields.io/badge/Python-3.14-3776AB?logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-UI-FF4B4B?logo=streamlit&logoColor=white)
![OpenAI](https://img.shields.io/badge/Embedding-text--embedding--3--small-412991?logo=openai&logoColor=white)
![Chroma](https://img.shields.io/badge/Chroma-1.5-FF6F61)
![pyhwp](https://img.shields.io/badge/pyhwp-HWP-0050A0)
![pytest](https://img.shields.io/badge/pytest-42_passing-0A9EDC?logo=pytest&logoColor=white)
![ruff](https://img.shields.io/badge/ruff-clean-D7FF64?logo=ruff&logoColor=black)
![uv](https://img.shields.io/badge/uv-managed-DE5FE9)

> 프로젝트 지침: [CLAUDE.md](CLAUDE.md) · 작업 현황/할 일: [NEXTSESSION.md](NEXTSESSION.md)

---

## 아키텍처

(A) 기준 문서를 RAG로 인덱싱하고, (B) 회사 서류를 판정하며 (A)의 근거 조항을 붙입니다.

```mermaid
flowchart TD
    subgraph A["(A) 기준 문서 — 판정 근거 (UI ①)"]
        REF["기준 PDF·HWP<br/>공고·운영규정·관리지침"] --> L["적재(Load)<br/>pdfplumber·pyhwp"]
        L --> S["분할(Split)<br/>제N조 + 의미단위"]
        S --> E["임베딩(Embed)<br/>OpenAI text-embedding-3-small"]
        E --> V[("Chroma · cosine · 로컬")]
    end

    subgraph B["(B) 회사 구비서류 검토 (UI ②)"]
        U["업로드 zip·PDF"] --> ING["수집 ingest<br/>중첩 zip 해제"]
        ING --> EXT["추출 extract<br/>텍스트레이어→OCR · 캐시 · 병렬"]
        EXT --> CLS["분류 classify"] --> FLD["필드추출 extract_fields"]
        FLD --> RUL["룰판정 rules_engine<br/>결정형 Python"]
    end

    V -. "근거 조항 첨부" .-> RUL
    RUL --> REP["리포트 report<br/>xlsx 5시트"] --> DL[/다운로드/]
```

### 흐름 한눈에 보기
1. **① 기준 문서 업로드** → 적재→분할→임베딩→인덱싱(각 단계 결과 확인) → "이 기준으로 판정합니다"(판단기준+가점)
2. **② 회사 구비서류 업로드** → (암호 zip이면 비번 요청) → 검토 → 판정 + **근거 조항** + 가점 + 리포트
3. 못 읽거나 애매하면 **거절하지 않고 `확인필요`** 로 사람에게 넘김. 못 불러온 파일은 **알림**으로 표시.

## 판정 체계

| 값 | 의미 |
|----|------|
| **적합 / 부적합** | 요건 충족/미충족이 근거와 함께 확인 |
| **확인필요** | 추출 신뢰도 낮음·스캔 미해독 → 사람 확인 |
| **해당없음** | 적용되지 않는 항목 |

종합판정: 하나라도 `부적합`→부적합 / `확인필요` 있으면 확인필요 / 모두 통과면 적합. 최종 판정은 LLM이 아니라 **감사 가능한 Python 규칙**.

## 판단기준 ↔ 코드

`rules.yaml`의 `check` 값 ↔ `pipeline/rules_engine.py` 동명 함수(1:1).

| 기준 | 함수 / 핵심 |
|---|---|
| 창업 7년 이내 | `check_business_age` — 법인 등기부 회사성립연월일(없으면 개업연월일), **달력 7주년** 비교 |
| 벤처기업 자격 | `check_venture` |
| 국세·지방세 체납 | `check_tax_arrears` |
| 허위·부정(일치) | `check_consistency` — 사업자번호 불일치=부적합 / 상호·대표자=확인필요 |
| 필수서류 완비 | `check_completeness` — 9종(법인=등기부·주주명부 포함) 조건부 |
| 가점 | `evaluate_bonus` — **건당=점수×건수**, 정액 1회, 감점(국가R&D 제재)=확인필요, 합산 ≤5점 |
| 성과 년도별 | `evaluate_performance` — 건수 자동집계, 금액·인원은 확인필요 |

## RAG 단계별 구현 현황

| 단계 | 상태 | 비고 |
|---|---|---|
| 적재(Load) | 🟢 | PDF·HWP / 스캔 근거문서 OCR은 미연결 |
| 분할(Split) | 🟢 | 제N조 + **의미단위(항·호·목·문장)** 묶음 |
| 임베딩(Embed) | 🟢 | **OpenAI text-embedding-3-small**(offline 폴백 가능) |
| 벡터DB(Index) | 🟢 | 로컬 Chroma(cosine·영속) |
| 검색(Retrieval) | 🟢 | top-k + min_score / rerank·hybrid 미구현 |
| 판정 통합 | 🟢 | 근거 조항 evidence 첨부 |
| 평가(Eval) | 🔴 | 정량 평가셋 없음 |
| 생성(LLM 답변) | ⚪ | 설계상 부재(결정형 판정) |

## 기능 모듈

| 모듈 | 역할 |
|---|---|
| `app.py` / `run.py` | Streamlit UI / protobuf-safe 런처(`cluster-app`) |
| `cli.py` | CLI (`cluster-screening`) |
| `pipeline/ingest.py` | (중첩) zip 해제·PDF 수집(zip-slip 차단) |
| `pipeline/extract_text.py` | 텍스트레이어(pdfplumber) → OCR(EasyOCR), 앞 N페이지 |
| `pipeline/extract_cache.py` | **내용해시 캐시**(재처리 시 OCR 생략) |
| `pipeline/classify.py` · `extract_fields.py` | 분류 / 앵커·정규식 필드추출 |
| `pipeline/rules_engine.py` | 룰 판정 + 가점 + 성과 + RAG 근거 첨부 |
| `pipeline/report.py` | xlsx 리포트(5시트) |
| `rag/ingestion·chunking·index·retriever·cli` | 근거 문서 RAG |

## 핵심 설정 (`.env`)

| 항목 | 기본값 | 설명 |
|---|---|---|
| `OPENAI_API_KEY` | (없음) | RAG 임베딩(OpenAI). 없으면 임베딩 offline 모드 |
| `RAG_EMBED_PROVIDER` | `openai`(키 있으면)/`offline` | 임베딩 제공자 |
| `RAG_MIN_SCORE` / `ENABLE_RAG_BASIS` | `0.3` / `1` | 근거 조항 첨부 + 노이즈 필터 |
| `OCR_DPI` / `OCR_MAX_PAGES` | `200` / `8` | OCR 해상도 / 앞 N페이지만 |
| `ENABLE_EXTRACT_CACHE` / `EXTRACT_WORKERS` | `1` / `4` | 추출 캐시 / 파일 병렬 수 |
| `ZIP_PASSWORD` | (없음) | zip 비번(UI/CLI 입력 가능, 하드코딩 금지) |

## 시작하기

```bash
uv sync --extra rag --extra unstructured   # 의존성(임베딩·Chroma·HWP·unstructured)
cp .env.example .env                        # OPENAI_API_KEY 입력(임베딩용)

uv run cluster-app                          # UI (protobuf-safe 런처) → http://localhost:8501
uv run cluster-screening <zip|폴더|pdf> --name 기업명 --apply 2026-03-16 --pw "<zip비번>"   # CLI
uv run rag-index ; uv run rag-search "체납 기업 제외"   # RAG 콘솔(선택)
```
> UI는 `streamlit run`이 아니라 **`uv run cluster-app`** 으로 띄우세요(인덱싱 단계 protobuf 충돌 회피).

## 성능

- 필드 불필요 유형(사업계획서·주주명부·동의서·명부)은 **파일명으로 식별 시 OCR 생략**
- OCR **앞 8페이지·200DPI**, **내용해시 캐시**(재실행 즉시), **파일 단위 병렬 추출**
- 처리 중 **단계별 로그** + 파일별 **불러오기 상태(O/X)**·실패 알림

## 보안 / Git

- 비밀값은 `.env`에서만(하드코딩 금지). `.env`·`data/`·`chroma/`·`.extract_cache/`·`*.xlsx`는 `.gitignore`.
- 신청 서류 PII: 처리 후 임시폴더 즉시 삭제, zip 해제 시 경로탈출 차단. 단독 사용 도구라 앱 로그인 없음.

## 프로젝트 구조

```
프로젝트루트/
├── pyproject.toml  uv.lock  .python-version  .streamlit/config.toml
├── .env                      # 비밀(git 비추적)
├── README.md  CLAUDE.md  NEXTSESSION.md
├── src/cluster_screening/
│   ├── app.py  run.py  cli.py  config.py  rules.yaml
│   ├── pipeline/            # 수집·추출·캐시·분류·필드·룰판정·리포트
│   └── rag/                 # 근거 문서 RAG
├── tests/                   # pytest(룰엔진·청킹·캐시·파이프라인)
├── data/reference/          # 기준 PDF·HWP (git 제외)
└── chroma/                  # RAG 벡터 인덱스 (git 제외)
```

## 품질 / 다음 단계

```bash
uv run pytest        # 42 케이스
uv run ruff check .  # 정적검사
```
진행 현황·할 일은 **[NEXTSESSION.md](NEXTSESSION.md)**. (폐쇄망 배포는 일단 보류 — 추후 재구성)
