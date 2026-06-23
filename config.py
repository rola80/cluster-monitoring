"""환경설정. 모든 외부 연동(OCR, LLM)은 토글로 끄고 켤 수 있다."""
import os
from pathlib import Path

# 프로젝트 루트의 .env를 (있으면) 로드해 환경변수로 주입한다.
# python-dotenv가 없거나 .env가 없어도 조용히 넘어간다(시스템 환경변수만 사용).
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
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

# ── Docling(선택) ── 표/레이아웃 복원이 필요할 때만. 느리고 RAM이 커서 기본 OFF.
USE_DOCLING = os.getenv("USE_DOCLING", "0") == "1"
DOCLING_TABLES = os.getenv("DOCLING_TABLES", "0") == "1"  # TableFormer(표구조) — 가장 무거움

# ── LLM (OpenAI) ── 비정형/OCR보정 필드 추출 폴백. 키 없으면 자동 비활성.
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ENABLE_LLM = bool(OPENAI_API_KEY)
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4.1-mini")        # 워크호스
LLM_MODEL_VISION = os.getenv("LLM_MODEL_VISION", "gpt-4.1")  # 스캔 OCR 폴백

# ── 추출 임계값 ──
TEXT_LAYER_MIN_CHARS = 40   # 페이지당 이 미만이면 스캔으로 간주 → OCR 경로
ZIP_PASSWORD = os.getenv("ZIP_PASSWORD", "")  # 구비서류 zip 비밀번호(있으면)
