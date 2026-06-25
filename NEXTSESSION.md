# NEXTSESSION.md — 작업 현황 / 다음 할 일

> 한 것은 `[x]`, 안 한 것은 `[ ]`. 새 세션은 `CLAUDE.md`(지침) → 이 파일 순으로 읽고 시작한다.

## 목표 시스템 (요약)
환경기업지원사업 제출서류를, **기준 문서(공고·규정·지침)를 RAG 근거로** 자동 검토해
**근거 조항이 달린 판정 리포트(xlsx)** 를 만든다. 판정은 결정형 Python 규칙(감사 가능), LLM 생성 없음.

---

## 1. 완료 ✅

### 기반·패키징
- [x] uv 패키징(`pyproject.toml`·`uv.lock`·`.python-version`), src 표준 레이아웃, `PROJECT_ROOT`
- [x] 콘솔 스크립트: `cluster-app`(UI 런처), `cluster-screening`(CLI), `rag-index`/`rag-search`
- [x] pytest 42케이스(룰엔진·청킹·캐시·파이프라인), ruff 정적검사, 데드코드 제거
- [x] 로그인 제거(단독 사용 도구), 제목 "환경기업지원사업 제출서류검토기"

### RAG (근거 문서)
- [x] 적재 ingestion — PDF(pdfplumber/unstructured) + **HWP(pyhwp)**
- [x] 분할 chunking — 실제 '제N조' 제목 경계 + **의미단위(항·호·목·문장) 묶음**(문장 중간 절단 방지)
- [x] 임베딩 — **OpenAI text-embedding-3-small**(기본) / sentence-transformers(offline 폴백), `RAG_EMBED_PROVIDER`
- [x] 인덱싱 — 로컬 Chroma(cosine, 영속, protobuf 충돌 회피 런처)
- [x] 검색 retriever + `evidence_for`, min_score 노이즈 필터
- [x] (B) 통합 — 판정마다 근거 조항 evidence 첨부(RAG OFF 시 우아한 degradation)

### 판정·UI
- [x] 메인 2단계 UI — ① 기준문서 단계별(적재→분할→임베딩→인덱싱, 각 결과 표시) ② 회사 검토
- [x] 압축 비밀번호는 **암호 zip 감지 시에만** 요청
- [x] 판단기준: 창업 7년(달력 7주년)·벤처·체납·일치·필수서류 조건부 완비
- [x] 성과 년도별 정리(건수 자동집계 + 금액·인원 확인필요)
- [x] **가점**: 건당(per_case)=점수×건수, 정액 1회, 감점(국가R&D 제재)=확인필요, 합산 상한 5점
- [x] 결과 세션 보존(다운로드·검색 rerun에도 유지), 리포트 xlsx 5시트

### 속도·로깅·보안
- [x] 속도: 필드 불필요 유형 OCR 생략 + OCR 앞 8페이지·200DPI + **내용해시 캐시** + **파일 병렬 추출**
- [x] **파일별 불러오기 상태(O/X)** + 실패/미분류 파일 알림(사람 확인) + **단계별 처리 로그**
- [x] 보안: `.env`·`data/`·`chroma/`·`.extract_cache/`·`*.xlsx` gitignore, PII 임시폴더 즉시 삭제,
      zip-slip 차단, zip 비번 하드코딩 제거(.env/입력만), 노출 OpenAI 키 폐기

---

## 2. 다음 할 일 ⬜

### RAG 고도화
- [ ] 스캔(이미지) 근거문서 OCR 연결(현재 텍스트레이어만)
- [ ] 검색 고도화 — rerank · hybrid(BM25+vector) · query rewriting
- [ ] 평가셋(질문→근거조항) + recall@k 등 정량 지표

### 판정 정밀화
- [ ] 성과 연도별 정밀 추출(재무제표 매출·영업이익, 명부 인원)
- [ ] 가점 유효기간·주최기관 요건 자동 검증(현재 사람 확인)
- [ ] 녹색산업·녹색연관산업 분야 적합성 판정
- [ ] 여러 기업 일괄 처리 + 총괄표, 연장평가 모드

### 운영·보안
- [ ] PII(주민번호·사업자번호) 마스킹·암호화
- [ ] mypy 타입체크 + CI(Python 3.14 런너·의존성 가용성 확인)
- [ ] (보류) **폐쇄망 오프라인 배포** — 사용자 요청으로 일단 제거, 나중에 재구성
- [ ] (선택) git 히스토리에서 과거 zip 비번 흔적 제거 — 저장소 공개 시
