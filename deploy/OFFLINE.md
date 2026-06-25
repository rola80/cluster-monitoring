# 폐쇄망(오프라인) 배포 가이드

인터넷이 없는 폐쇄망에 이 프로젝트를 배포하는 절차. **대상 환경: Windows x64 / Python 3.14 + uv 설치됨 / 기능 전체(RAG+OCR), LLM 제외.**

> 핵심 원리: 인터넷 되는 PC에서 ① 의존성 wheel ② 임베딩·OCR 모델 ③ NLTK 데이터를 미리 받아
> `deploy\bundle` 로 묶고, 그 번들을 폐쇄망으로 옮겨 오프라인 설치한다.
> wheel은 플랫폼 의존적이라 **준비 PC도 동일한 Windows x64**여야 한다.

## 인터넷이 필요한 지점(미리 받아둘 것)
| 항목 | 출처 | 번들 위치 | 오프라인 설정 |
|---|---|---|---|
| 파이썬 의존성 | PyPI | `bundle/wheelhouse` | `uv pip install --no-index --find-links` |
| RAG 임베딩 모델(ko-sroberta) | HuggingFace | `bundle/models/ko-sroberta` | `RAG_EMBED_MODEL`=로컬경로, `HF_HUB_OFFLINE=1` |
| OCR 모델(EasyOCR ko,en) | jaided.ai | `bundle/easyocr` | `OCR_MODEL_DIR`=폴더, `OCR_DOWNLOAD_ENABLED=0` |
| unstructured NLTK 데이터 | nltk | `bundle/nltk_data` | `NLTK_DATA`=폴더 |
| OpenAI LLM | api.openai.com | — | **사용 불가 → `ENABLE_LLM=0`** |

## A. 준비 (인터넷 되는 Windows x64 PC)

```powershell
# 1) 프로젝트 받기 + 온라인으로 한 번 설치(모델 다운로드 위해 extra 포함)
uv sync --extra rag --extra unstructured

# 2) 번들 생성 (wheelhouse + 모델 + NLTK). 용량 큼(torch 등 수 GB), 시간 걸림.
.\deploy\prepare_offline_bundle.ps1
#  → deploy\bundle\ 아래에 requirements-offline.txt, wheelhouse\, models\, easyocr\, nltk_data\ 생성
```

## B. 이동
`deploy\bundle\` 폴더(또는 **프로젝트 전체 + deploy\bundle**)를 USB/내부망으로 폐쇄망에 복사.
`.venv`·`chroma`·`__pycache__` 는 옮기지 않는다(대상에서 새로 생성).

## C. 설치 (폐쇄망 대상)

```powershell
# 1) 오프라인 설치 (인터넷 미사용)
.\deploy\install_offline.ps1

# 2) 환경변수: 오프라인 예시를 .env 로 복사 후 절대경로 수정
Copy-Item .\deploy\.env.offline.example .\.env
#  .env 의 RAG_EMBED_MODEL / OCR_MODEL_DIR / NLTK_DATA 를 실제 설치 경로로 수정

# 3) 검증
uv run cluster-screening <zip|폴더|pdf> --name 테스트          # 핵심 파이프라인
#  근거 RAG:
Copy-Item <근거 PDF/HWP> .\data\reference\
uv run rag-index                                             # 오프라인 인덱싱(로컬 임베딩 모델)
uv run rag-search "국세 지방세 체납 기업 제외"
```

## 점검 체크리스트
- [ ] 준비 PC와 대상이 **같은 Windows x64 + 같은 Python 마이너 버전(3.14)** 인가
- [ ] `deploy\bundle\wheelhouse` 에 휠이 채워졌는가(torch·easyocr·chromadb·pyhwp 등)
- [ ] `.env` 의 3개 경로(RAG_EMBED_MODEL·OCR_MODEL_DIR·NLTK_DATA)가 **대상 실제 경로**인가
- [ ] `ENABLE_LLM=0` (폐쇄망은 LLM 미사용), `HF_HUB_OFFLINE=1`
- [ ] 첫 `rag-index`/OCR 실행이 네트워크 접근 없이 끝나는가(끊긴 환경에서 확인)

## 문제 해결
- **휠 없음/빌드 실패**: 준비 PC 플랫폼이 대상과 다를 때 발생. 동일 Windows x64에서 다시 `prepare_offline_bundle.ps1`.
- **모델 다운로드 시도(오프라인 에러)**: `.env` 의 모델 경로/`*_OFFLINE`/`OCR_DOWNLOAD_ENABLED=0` 누락 확인.
- **unstructured 사용 시 NLTK 에러**: `NLTK_DATA` 경로 확인. unstructured를 안 쓰면(USE_UNSTRUCTURED 미설정) 무관.
