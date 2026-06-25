"""환경설정. 모든 외부 연동(OCR, LLM)은 토글로 끄고 켤 수 있다."""
import os
from . import PROJECT_ROOT

# 프로젝트 루트의 .env를 (있으면) 로드해 환경변수로 주입한다.
# python-dotenv가 없거나 .env가 없어도 조용히 넘어간다(시스템 환경변수만 사용).
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

# ── OCR ──
# 스캔 PDF(텍스트 레이어 없음) 처리.
# 기본 엔진은 EasyOCR(한글 내장, CPU, 최초 1회 모델 다운로드 후 오프라인).
#   - PaddleOCR 정식은 Python 3.14 휠이 없어 사용 불가, RapidOCR은 한글 모델 미제공 → EasyOCR 채택.
ENABLE_OCR = os.getenv("ENABLE_OCR", "1") == "1"
OCR_ENGINE = os.getenv("OCR_ENGINE", "easyocr")          # easyocr | tesseract
OCR_LANGS = os.getenv("OCR_LANGS", "ko,en").split(",")   # EasyOCR 언어코드(쉼표구분)
OCR_LANG = os.getenv("OCR_LANG", "kor+eng")              # tesseract 폴백용(kor 언어팩 필요)
OCR_DPI = int(os.getenv("OCR_DPI", "300"))
# 폐쇄망: 미리 받아둔 EasyOCR 모델 폴더 + 다운로드 차단(0)
OCR_MODEL_DIR = os.getenv("OCR_MODEL_DIR", "")           # 비우면 기본 위치(~/.EasyOCR)
OCR_DOWNLOAD_ENABLED = os.getenv("OCR_DOWNLOAD_ENABLED", "1") == "1"

# ── Docling(선택) ── 표/레이아웃 복원이 필요할 때만. 느리고 RAM이 커서 기본 OFF.
USE_DOCLING = os.getenv("USE_DOCLING", "0") == "1"
DOCLING_TABLES = os.getenv("DOCLING_TABLES", "0") == "1"  # TableFormer(표구조) — 가장 무거움

# ── unstructured(선택) ── 레이아웃·요소 단위 문서 파싱. 'uv sync --extra unstructured' 필요.
# 현재 RAG 근거문서 적재(ingestion)에서 선택적 백엔드로 사용. 미설치/실패 시 pdfplumber로 폴백.
USE_UNSTRUCTURED = os.getenv("USE_UNSTRUCTURED", "0") == "1"
UNSTRUCTURED_STRATEGY = os.getenv("UNSTRUCTURED_STRATEGY", "fast")  # fast(경량) | hi_res(레이아웃모델)

# ── LLM (OpenAI) ── 비정형/OCR보정 필드 추출 폴백. 키 없으면 자동 비활성.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ENABLE_LLM = bool(OPENAI_API_KEY)
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-mini")        # 워크호스
LLM_MODEL_VISION = os.getenv("LLM_MODEL_VISION", "gpt-4.1")  # 스캔 OCR 폴백

# ── 추출 임계값 ──
TEXT_LAYER_MIN_CHARS = 40   # 페이지당 이 미만이면 스캔으로 간주 → OCR 경로
ZIP_PASSWORD = os.getenv("ZIP_PASSWORD", "")  # 구비서류 zip 비밀번호(있으면)

# ── RAG (근거 문서: 공고·운영규정·관리지침) ──
# 임베딩은 오프라인(sentence-transformers), 벡터스토어는 로컬 Chroma. 'uv sync --extra rag' 필요.
RAG_REFERENCE_DIR = os.getenv("RAG_REFERENCE_DIR", str(PROJECT_ROOT / "data" / "reference"))
RAG_PERSIST_DIR = os.getenv("RAG_PERSIST_DIR", str(PROJECT_ROOT / "chroma"))
RAG_COLLECTION = os.getenv("RAG_COLLECTION", "reference")
RAG_EMBED_MODEL = os.getenv("RAG_EMBED_MODEL", "jhgan/ko-sroberta-multitask")  # 한국어 경량(오프라인)
RAG_CHUNK_CHARS = int(os.getenv("RAG_CHUNK_CHARS", "800"))
RAG_CHUNK_OVERLAP = int(os.getenv("RAG_CHUNK_OVERLAP", "150"))
RAG_TOP_K = int(os.getenv("RAG_TOP_K", "5"))
RAG_MIN_SCORE = float(os.getenv("RAG_MIN_SCORE", "0.3"))  # 이 미만 유사도면 근거조항 미첨부(노이즈 방지)
# 판정 evidence에 근거 조항(RAG)을 첨부. rag 미설치/인덱스 없음이면 자동 무첨부(우아한 degradation).
ENABLE_RAG_BASIS = os.getenv("ENABLE_RAG_BASIS", "1") == "1"
