# CLAUDE.md — 녹색융합클러스터 입주서류 자동검토 도구

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> 이 파일은 Claude Code가 매 작업 시 읽는 프로젝트 지침서다.
> 코드를 쓰기 전에 항상 이 문서의 **설계 원칙**과 **작업 방식**을 먼저 확인한다.
> 코드 주석·UI 문자열·문서·커밋 메시지는 모두 **한국어**로 유지한다.
> 앞으로 할 일은 `NEXTSESSION.md`에 정의돼 있고, **완료 항목은 취소선(`~~...~~`)** 으로 남긴다.

---

## 1. 프로젝트 개요

**한 줄 정의** — 창업·벤처 녹색융합클러스터 입주 신청서류(PDF 묶음)를 받아, 신청요건 적합 여부를
자동 검토하고 **근거가 달린 판정 리포트(xlsx)** 를 생성하는 도구.

**핵심 가치**
- 사람이 검토하던 입주 서류 심사를 **감사 가능한(auditable)** 방식으로 보조한다.
- 모든 판정에는 **근거(evidence)** 가 붙는다. 근거 없는 판정은 만들지 않는다.
- 도구는 사람을 **대체하지 않고 보조**한다. 애매하면 사람에게 넘긴다.

---

## 2. Commands

의존성·실행은 **uv**로 관리한다(`pyproject.toml` + `uv.lock`). 표준 src 레이아웃.

```bash
uv sync                                  # .venv + 의존성 + 패키지 editable 설치
uv sync --extra docling                  # 표/레이아웃 복원(Docling)까지 필요할 때만

uv run streamlit run src/cluster_screening/app.py      # UI (단독 사용 도구 — 로그인 없음)
uv run cluster-screening <zip|폴더|pdf> --name 기업명 --apply 2026-03-16 --pw "<zip비밀번호>" --out 결과.xlsx

# (A) 근거 문서 RAG — 무거운 의존성이라 extra로 분리
uv sync --extra rag
uv run rag-index                          # data/reference/ (PDF·HWP) 인덱싱 → chroma/
uv run rag-search "창업 7년 기준이 무엇인가"   # 근거 조항 검색
```

**폐쇄망(오프라인) 배포**: `deploy/OFFLINE.md` 참고. 인터넷 PC에서 `deploy/prepare_offline_bundle.ps1`로
번들(wheel+모델+NLTK) 생성 → 대상에서 `deploy/install_offline.ps1`. 오프라인 토글: `HF_HUB_OFFLINE`,
`RAG_EMBED_MODEL`(로컬경로), `OCR_MODEL_DIR`/`OCR_DOWNLOAD_ENABLED=0`, `NLTK_DATA`, `ENABLE_LLM=0`.

zip 비밀번호는 `.env`(`ZIP_PASSWORD`) 또는 `--pw`로만 전달(코드/문서 하드코딩 금지). 검증은 실제 서류로 CLI 실행 후 `종합판정` 확인.

---

## 3. 핵심 도메인 지식

### 판정 근거 문서 (= RAG Source)
- 모집공고 (제2025-004호) · 운영규정(제2·9조) · 입주기업 관리지침.
- 이 세 문서가 "기준"이며, RAG로 인덱싱하여 판정 근거 검색에 사용한다(→ §5 (A) 브랜치, 현재 미구현).

### 핵심 자격요건
- **입주신청일 기준 창업 7년 미경과**한 **중소기업 또는 벤처기업**.
- 그 외 모집공고/규정 요건은 근거 문서에서 확인하여 룰로 반영.

### 가점 항목
- 녹색채권 3점 / 사회적기업 2점 / 인증·특허 등 각 2점/건 / 국가R&D 제재 −5점.
- **합산 최대 5점**(상한 초과 시 5점 절삭). 가점은 **유효기간·건수**를 실제 검증해야 함(만료 인증/특허 주의).

### 녹색산업 분야 적합성
- 신청 기업 사업이 녹색산업 분야에 해당하는지 판정하는 로직 필요(개발 예정).

---

## 4. 판정 체계 (반드시 준수)

### 판정값 (4종)
| 값 | 의미 |
|----|------|
| **적합** | 요건 충족이 근거와 함께 확인됨 |
| **부적합** | 요건 미충족이 근거와 함께 확인됨 |
| **확인필요** | 추출 신뢰도가 낮거나 스캔 미해독 등으로 자동 판정 불가 → **사람이 확인** |
| **해당없음** | 해당 기업/서류에 적용되지 않는 항목 |

종합판정: 하나라도 `부적합`→`부적합`, 아니면 `확인필요` 있으면 `확인필요`, 모두 통과면 `적합`.

### 설계 원칙 (절대 위반 금지)
1. **자동 거절 금지** — 추출 신뢰도가 낮거나 스캔을 못 읽으면 `부적합`이 아니라 **`확인필요`** 로 표기.
2. **최종 판정은 결정형 Python 규칙으로만**(`rules_engine`). 규칙은 사람이 읽고 감사할 수 있어야 한다.
3. **LLM은 필드 추출 폴백 용도로만.** LLM이 최종 적합/부적합을 결정하지 않는다.
4. **모든 결과에 evidence를 남긴다.** evidence에는 최소한 (어느 서류) + (몇 페이지/위치) +
   (추출 원문 값) + (적용 규칙/근거 조항)이 포함된다.

---

## 5. 아키텍처

성격이 다른 **두 갈래**로 구성된다.

### (A) 근거 문서 RAG — `src/cluster_screening/rag/`  🟡 검색 MVP 구현(통합 예정)
공고·규정·지침을 인덱싱해 "이 판정의 근거 조항이 무엇인가"를 검색한다(NotebookLM처럼 Source 기반).
```
근거 문서(PDF) → ingestion(적재·진단) → chunking(+metadata 6항목, 제N조 태깅) → index(임베딩·Chroma) → retriever(근거 검색)
```
임베딩=오프라인 sentence-transformers(`RAG_EMBED_MODEL`, 기본 ko-sroberta), 벡터스토어=로컬 Chroma(`chroma/`).
무거운 의존성이라 `uv sync --extra rag`로 분리. 콘솔: `uv run rag-index` / `uv run rag-search "<질의>"`.
근거 문서는 `data/reference/`에 둔다(git 비추적). **PDF + HWP 지원**(HWP는 pyhwp로 추출 — 정부 규정 원본이 HWP).
현재 인덱싱됨: 모집공고(제2025-004호)·관리지침(20250908) HWP 2종.

### (B) 신청 서류 검토 파이프라인 — `src/cluster_screening/pipeline/`  ✅ 구현됨
```
수집(ingest) → 분류(classify) → 텍스트추출(extract_text) → 필드추출(extract_fields)
            → 룰판정(rules_engine) → 리포트(report)
```
오케스트레이터는 `pipeline/__init__.py`의 `process_company()`. `app.py`(UI)·`cli.py`는 얇은 진입점.

### 두 갈래가 만나는 지점  🟡 1차 통합됨
`rules_engine.evaluate()`가 각 criterion의 `basis` 질의로 `retriever.evidence_for()`를 호출해
**근거 조항**을 `result["basis"]`에 첨부한다(리포트·UI·CLI "근거조항" 컬럼). `ENABLE_RAG_BASIS`로 토글,
`RAG_MIN_SCORE`(기본 0.3) 미만은 노이즈로 보고 미첨부. rag 미설치/인덱스 없음이면 자동 무첨부(판정 불변).
ingestion 파서는 pdfplumber 기본, `USE_UNSTRUCTURED=1`(+`uv sync --extra unstructured`)로 unstructured 사용.

### 판단기준 ↔ 코드 (가장 중요한 규약)
`rules.yaml`의 각 criterion `check` 값은 `rules_engine.py`의 **동명 함수와 1:1**(`CHECKS` 디스패치).
**새 기준 추가 시: `rules.yaml` 항목 + `rules_engine.py` 동명 `check_*(record, rules)` 함수**를 짝지어 작성.
모든 판정은 `R(status, detail, evidence)` 형태로 근거를 남긴다.

| 기준 | check 함수 |
|---|---|
| 창업 7년 이내 | `check_business_age` (법인=등기부 회사성립연월일, 없으면 사업자등록증 개업연월일 폴백 / 개인=개업연월일) |
| 벤처기업 자격 | `check_venture` |
| 국세·지방세 체납 | `check_tax_arrears` |
| 허위·부정(일치) | `check_consistency` (사업자번호 불일치=부적합 / 상호·대표자 불일치=확인필요) |
| 필수서류 완비 | `check_completeness` (`rules.yaml` required_docs; `when: 법인` 항목은 법인사업자만 필수) |
| 가점/감점 | `evaluate_bonus` (잠정 점수, 합산 ≤5점, 유효성 사람 확인) |
| 성과 년도별 정리 | `evaluate_performance` (rules.yaml `performance`; 건수 자동집계, 연도별 금액·인원은 `확인필요`. 종합판정 미반영, 리포트 "성과 년도별 정리" 시트) |

---

## 6. 프로젝트 구조

표준 **src 레이아웃**. 비밀·런타임 파일(`.env`)은 **프로젝트 루트**에 두고
`PROJECT_ROOT`(패키지 `__init__.py`가 pyproject.toml을 찾아 결정)로 로드한다.
> 처음부터 전부 만들지 않는다. 폴더(`rag/`, `data/`, `outputs/`, `eval/`)는 **필요해지는 시점에** 만든다.
> 단독 사용 도구라 **로그인은 없음**(접근 제어가 필요하면 외부 리버스 프록시 등으로).

```
프로젝트루트/
  pyproject.toml  uv.lock  .python-version    # uv 패키징
  .env                                        # 비밀값 (절대 커밋 금지, git 비추적)
  .gitignore  requirements.txt
  README.md  CLAUDE.md  NEXTSESSION.md
  src/cluster_screening/
    __init__.py        패키지 + PROJECT_ROOT
    app.py             Streamlit UI
    cli.py             CLI 진입점
    config.py          설정 토글(OCR·LLM·zip비번; .env/환경변수)
    rules.yaml         판단기준 규칙표
    pipeline/          (B) 신청 서류 검토 파이프라인 (위 6모듈)
    rag/        🟡 (A) 근거 문서 RAG — ingestion·chunking·index·retriever·cli (검색 MVP)
  data/reference/  🔴 근거 PDF(공고·규정·지침) 투입 위치 (git 비추적)
  chroma/     🟡 RAG 벡터 인덱스(로컬 영속, git 비추적)
  outputs/    🔴 판정 리포트 결과물(xlsx) (예정)
  eval/       🔴 회귀 테스트 정답셋(검증용 기업 데이터) (예정)
```

---

## 7. 입력 데이터의 현실 (까다로운 부분 — 꼭 숙지)

- **전부 PDF지만 전자문서(텍스트 레이어)와 스캔 이미지가 혼재** → 하이브리드 추출.
  먼저 텍스트 레이어를 시도하고, 페이지당 `config.TEXT_LAYER_MIN_CHARS`(40) 미만이면 OCR로 폴백.
  스캔본 예: 입주신청서·개인정보동의서·납세증명서·(일부) 법인등기부·인감증명서.
- **중첩 zip + 비밀번호** → zip 안에 zip 가능. 비밀번호는 `.env`/인자로 받고 코드 하드코딩 금지.
  압축 해제 시 `os.path.basename`으로 경로를 떼어내 zip-slip(경로 탈출)을 차단한다.
- **한글 정부양식 라벨에 글자 사이 공백** → 예 `"개 업 연 월 일"`. `extract_fields`가 공백 허용 매칭.
- **주주명부의 "사업자등록번호"는 주주(투자조합) 번호** → 일치성 검사는 신뢰서류
  (사업자등록증·입주신청서·납세증명서·재무제표)로만 한정. 주주명부에서 식별필드 추출 금지.
- 사업계획서 본문에 '인증·특허·수상' 단어가 많아 가점서류로 오분류되기 쉬움 → 파일명 힌트 가중치 20.
- 스캔을 못 읽으면 `부적합`이 아니라 `확인필요`(설계 원칙 1). 일부 문서는 매우 김(매출증빙 200+페이지).

---

## 8. Metadata 규칙

각 Chunk(및 추출 단위) metadata에는 **최소한** 다음을 유지한다(RAG·추출 공통 목표; 현재 부분 적용).

| 항목 | 설명 |
|------|------|
| `source` | 원본 파일명/문서명 |
| `page` | 페이지 번호 |
| `parser_type` | 추출 방식 (text-layer / ocr / docling) |
| `chunk_id` | 청크 고유 ID |
| `token_count` | 토큰 수 |
| `warning` | 신뢰도 경고/문제 메모 (없으면 빈 값) |

`warning`이 채워진 항목은 판정 시 `확인필요`로 이어질 수 있으므로 끝까지 추적한다.

---

## 9. 보안 규칙

- API Key·zip 비밀번호 등 **비밀값은 `.env`에서만 읽는다.** 코드에 직접 쓰지 않는다.
- `.gitignore`에 `.env`·벡터 DB 폴더(예: `chroma/`)·`data/`·`outputs/`·`__pycache__` 포함.
  **키가 노출되면 즉시 폐기·재발급**한다.
- 단독 사용 도구라 앱 로그인은 없음. 접근 제어가 필요하면 외부(리버스 프록시·OS 권한 등)에서 처리.
- 신청 기업 서류에는 개인정보·민감정보가 있다. 처리 후 임시폴더는 `pipeline.cleanup`으로 삭제. 리포트에 불필요하게 원문을 남기지 않는다(PII 마스킹 예정).

---

## 10. 작업 방식 (Claude Code 협업 규칙)

- **큰 변경 전에는 먼저 계획과 파일 구조를 제안하고, 사용자 승인 후 구현한다.**
- **RAG·파이프라인 전체를 한 번에 구현하지 않는다.** 단계별로 만든다.
- 코드는 **비전공자가 읽기 쉽게**(과한 추상화·축약 지양). 모듈 간 상대 임포트(`from . import ...`).
- **각 파일 상단에 역할 주석**을 적는다. 룰엔진 규칙은 **명시적으로**(마법 한 줄보다 읽히는 여러 줄).

---

## 11. 현재 상태 & 다음 할 일 (2026-06 기준)

### 검증됨
- 에이비알 실제 서류 12종 **E2E 검증 완료** → 종합판정 "적합"(개업 2021-03-03 vs 신청 2026-03-16 = 5.0년차).
- **텍스트 레이어 추출 + 룰엔진 검증됨.** uv 패키징·src 레이아웃·RAG 통합·pytest·ruff 적용됨.

### 미검증 (로컬 활성화 필요)
- ⚠️ **한글 OCR(EasyOCR) 미검증** · ⚠️ **OpenAI LLM 폴백 미검증**(샌드박스에 키/모델 없었음).

### 다음 할 일
앞으로 할 일과 우선순위는 **`NEXTSESSION.md`** 에 정의. 진행하면 그 파일에서 완료 항목을 취소선으로 남긴다.
핵심 미비 단계: (A) 근거 문서 RAG 브랜치 + evidence에 근거 조항 통합, OCR/LLM 실검증, PII 마스킹, 회귀 정답셋.

---

## 부록: 빠른 체크리스트 (코드 작성/리뷰 시)

- [ ] 이 변경이 "큰 변경"인가? → 그렇다면 계획부터 제안했는가?
- [ ] 추출 실패를 `부적합`이 아니라 `확인필요`로 두었는가?
- [ ] 최종 판정을 LLM이 아니라 `rules_engine`이 결정하는가?
- [ ] 모든 판정에 evidence(서류 위치 + 근거 조항)가 붙는가?
- [ ] metadata 6개 항목을 유지하는가?
- [ ] 비밀값을 `.env`에서 읽는가?
- [ ] 파일 상단에 역할 주석이 있는가?
