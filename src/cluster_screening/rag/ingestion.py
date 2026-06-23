"""근거 문서(공고·규정·지침) PDF 적재 + 페이지별 텍스트 추출 + 진단.

판정 근거 검색의 Source. 정부 규정은 보통 전자문서(텍스트 레이어)이므로 pdfplumber로 페이지 단위 추출.
텍스트가 거의 없으면(스캔 의심) warning을 남긴다(OCR 적용은 후속 과제).
"""
import os
import glob
import pdfplumber
from .. import config


def list_reference_pdfs(ref_dir=None):
    """근거 PDF 경로 목록(하위 폴더 포함)."""
    ref_dir = ref_dir or config.RAG_REFERENCE_DIR
    if not os.path.isdir(ref_dir):
        return []
    return sorted(glob.glob(os.path.join(ref_dir, "**", "*.pdf"), recursive=True))


def load_pages(ref_dir=None):
    """근거 PDF들을 페이지 단위로 적재.

    반환: [{source, page, text, parser_type, warning}, ...]
    """
    pages = []
    for path in list_reference_pdfs(ref_dir):
        source = os.path.basename(path)
        with pdfplumber.open(path) as pdf:
            for i, pg in enumerate(pdf.pages, start=1):
                text = pg.extract_text() or ""
                scanned = len(text.strip()) < config.TEXT_LAYER_MIN_CHARS
                pages.append({
                    "source": source,
                    "page": i,
                    "text": text,
                    "parser_type": "none" if scanned else "text-layer",
                    "warning": "텍스트 레이어 없음(스캔 의심) — OCR 미적용" if scanned else "",
                })
    return pages
