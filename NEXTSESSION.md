# NEXTSESSION.md — 다음 세션 작업 정의

> 이 파일은 **앞으로 할 일**을 정의한다. Claude Code로 작업을 진행할 때마다
> **완료한 항목은 취소선(`~~...~~`)으로 그어** 표시하고(삭제하지 않음) 한 줄 메모를 남긴다.
> 새 세션은 `CLAUDE.md`(프로젝트 지침) → 이 파일(할 일) 순으로 읽고 시작한다.

## 0. 사용자 지정 요구사항 (목표 시스템)

사용자가 정의한 목표 시스템(= `CLAUDE.md`에 반영된 비전). 핵심 미비 단계는 아래 §1~§6에 분해.
- 근거 문서(공고·규정·지침) **RAG 브랜치**로 "판정 근거 조항"을 검색.
- 판정 evidence = (어느 서류) + (페이지/위치) + (추출 원문 값) + **(적용 규칙/근거 조항)**.
- 각 추출/청크 단위에 **metadata 6항목**(source·page·parser_type·chunk_id·token_count·warning) 유지.
- 녹색산업 분야 적합성 판정 로직.
- 단계별 증분 개발(전체 한 번에 만들지 않음), 큰 변경 전 계획 승인.

## 1. 완료 ✅ (취소선 = 진행 완료)

- ~~로그인 인증(`auth.py`) — PBKDF2 해시·다중 사용자·Streamlit 게이트~~
- ~~README 서비스 흐름도(mermaid) + 코드 정합화(OCR=EasyOCR, 로그인 절차)~~
- ~~보안 점검: `.env`/`users.json` git 비추적·zip-slip 차단 확인~~ → **단, 노출된 OpenAI 키 폐기는 §2 미완**
- ~~uv 패키징: `pyproject.toml` + `uv.lock` + `.python-version`~~
- ~~`CLAUDE.md` / `CLAUDE.md.md` 통합 + 사용자 비전 반영~~
- ~~**엄밀 모듈화: `src/cluster_screening/` 표준 레이아웃 이전**, `.env`/`users.json`은 `PROJECT_ROOT` 기준 로드, import·CLI 검증~~
- ~~**검증항목 추가**: 필수서류 9종 조건부 완비(법인=등기부·주주명부 포함) + **성과 년도별 정리**(매출·영업이익·고용·국내/해외특허·수상·인증) 절차·리포트 시트·UI 표 추가, 스모크 검증~~ → 단, **연도별 정밀 수치 추출은 미구현**(현재 건수 자동집계 + 금액/인원은 확인필요)

## 2. 보안 (최우선) 🔴

- ~~**노출된 OpenAI API 키 폐기 후 재발급**~~ → 사용자가 노출 키 폐기 완료(2026-06-23). 새 키 필요 시 `.env`에만 저장(커밋 금지).
- [ ] 로그인 시도 제한/계정 잠금(brute-force 방어) — 공개 배포 시 필수.
- [ ] PII(주민번호·사업자번호) 마스킹·암호화 저장(Presidio + cryptography). 결과 xlsx·임시파일 원문 잔존 제거.
- [ ] 처리 후 임시 디렉터리(`tempfile.mkdtemp`) 정리 루틴.

## 3. (A) 근거 문서 RAG 브랜치 🟣

> 검색 MVP 완료. 임베딩=오프라인 sentence-transformers(ko-sroberta), 벡터스토어=로컬 Chroma. `uv sync --extra rag`.
- ~~**설계 승인**: 오프라인 임베딩 + 로컬 Chroma 확정~~
- ~~`rag/ingestion.py` — 공고·규정·지침 PDF 페이지 단위 적재·진단(warning)~~
- ~~`rag/chunking.py` — 청킹 + metadata 6항목 + '제N조' article 태깅~~
- ~~`rag/index.py` — 임베딩 → Chroma 인덱스 구축(텔레메트리 OFF)~~
- ~~`rag/retriever.py` + `rag/cli.py` — 근거 조항 top-k 검색, `rag-index`/`rag-search` 콘솔~~ → 합성 데이터 검증(제9조 검색 성공)
- ~~**(B)와 통합**: `rules_engine`가 판정 시 `retriever.evidence_for`로 각 기준의 근거 조항을 evidence에 첨부~~ → rules.yaml `basis` 질의 + `ENABLE_RAG_BASIS`/`RAG_MIN_SCORE`(노이즈 필터), 리포트·UI·CLI에 "근거조항" 노출, RAG OFF 시 우아한 degradation 검증
- ~~**unstructured 파싱 백엔드**: `USE_UNSTRUCTURED`로 ingestion에서 unstructured 사용(미설치/실패 시 pdfplumber 폴백). `uv sync --extra unstructured`~~
- ~~**HWP 지원**: 근거 원본이 HWP라 ingestion에 pyhwp(hwp5) 추출 추가(PDF·HWP 모두)~~
- ~~**실데이터 인덱싱**: 모집공고(2025-004)·관리지침(20250908) HWP 2종 인덱싱(88청크) → 판정에 실근거 조항 첨부 검증~~
- [ ] **근거 위치 정밀화**: HWP는 page=1 한 덩어리라 '제N조' 태깅이 부정확할 수 있음(긴 본문에서 직전 조 채택). 조 단위 분할(제N조 경계 split)로 개선 + RAG_MIN_SCORE 튜닝.
- [ ] **운영규정 추가**: 현재 모집공고·관리지침만. 운영규정 원본 확보 시 `data/reference/`에 추가 인덱싱.
- [ ] **스캔 근거문서 OCR**: 현재 PDF는 텍스트레이어만(스캔이면 warning). 필요 시 OCR/unstructured hi_res 연결.
- [ ] (선택) unstructured를 (B) 신청서류 `extract_text`에도 백엔드로 확장.

## 3b. 성과 년도별 정리 — 정밀 추출 (후속) 🟡

> 현재 골격: 근거서류 제출 여부 확인 + 건수(특허·수상·인증) 자동집계. 금액·인원은 `확인필요`.
- [ ] 표준재무제표에서 **연도별 매출액·영업이익** 추출(`extract: financial`).
- [ ] 4대보험·고용보험 명부에서 **연도별 고용인력(명)** 추출(`extract: headcount`).
- [ ] 특허 건수의 **국내/해외·연도** 구분(현재 P4·P5가 동일 서류수로 집계됨).
- [ ] 인증·수상의 유효연도 파싱.

## 4. evidence / metadata 강화 🟡

- [ ] evidence 포맷을 (서류·페이지/위치·원문값·근거조항) 4요소로 표준화(현재 detail/evidence 문자열).
- [ ] 추출 단위 metadata 6항목 부여 — 현재 `doc_log`는 {file·유형·신뢰도·추출방식·필드수}만 보유.
- [ ] `warning` 채워진 항목 → 판정 `확인필요`로 자동 연결되는지 추적.

## 4b. 폐쇄망(오프라인) 배포 🟤

> 대상: Windows x64 / Python 3.14 + uv / 전체 기능(RAG+OCR), LLM 제외. 가이드 `deploy/OFFLINE.md`.
- ~~오프라인 토글(`OCR_MODEL_DIR`/`OCR_DOWNLOAD_ENABLED`, `RAG_EMBED_MODEL` 로컬경로) + 번들 스크립트(prepare/install) + `.env.offline.example`~~ → `uv export` 검증
- [ ] **실제 번들 빌드·검증**: 인터넷 PC에서 `prepare_offline_bundle.ps1` 실행(wheelhouse·모델 수 GB) → 폐쇄망 모사 환경에서 `install_offline.ps1` + 인덱싱·OCR이 네트워크 없이 동작하는지 확인.
- [ ] (선택) Python 3.14·uv 자체가 없는 대상까지 커버하려면 인스톨러도 번들.

## 5. 구조 / 품질 🟢

- [ ] `config/` 분리 — 자격요건·가점표·문서종류 목록 등 룰 상수를 코드에서 분리(현재 `rules.yaml` + `rules_engine.py`).
- [ ] `app.py` UI/비즈니스 로직 분리(현재 버튼 핸들러에 처리·리포트 인라인) → service 계층.
- [ ] 타입 힌트·docstring 보강, `ruff`/`mypy` 정적검사 + CI 도입.
- [ ] `data/`·`outputs/`·`eval/` 폴더는 **필요해지는 시점에** 생성.

## 6. 검증 / 기능 확장 🔵

- [ ] **한글 OCR(EasyOCR) 실연동 검증** — 스캔본(입주신청서·납세증명서) 필드 추출 정확도.
- [ ] **OpenAI LLM 폴백 검증** — 키 설정 후 비정형 필드 추출 동작.
- [ ] 두 번째 기업(스타스테크) 데이터로 분류·추출 **회귀 정답셋**(`eval/`) + pytest.
- ~~룰엔진 단위 테스트(pytest)~~ → `tests/test_rules_engine.py` 29케이스(완비성 조건부·창업연차·체납·일치성·가점상한·성과·종합판정), `uv run pytest`
- ~~**창업연차 경계 보정**: 365.25 부동소수 대신 **기준일의 7주년(달력) 날짜와 신청일 비교**로 변경(`_add_years`, 2/29 처리). 정확히 7주년=적합, 다음날=부적합. 경계 테스트 추가~~
- [ ] 가점 유효기간/건수 실검증, 녹색산업 분야 적합성 판정, 여러 기업 일괄 처리 + 총괄표, 연장평가 모드.
