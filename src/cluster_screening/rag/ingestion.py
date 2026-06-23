"""근거 문서(공고·규정·지침) PDF 적재 + 페이지별 텍스트 추출 + 진단.

판정 근거 검색의 Source. 기본은 pdfplumber(텍스트 레이어)로 페이지 단위 추출.
config.USE_UNSTRUCTURED=1 이면 unstructured로 레이아웃·요소 단위 파싱(미설치/실패 시 pdfplumber 폴백).
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


def _pages_pdfplumber(path):
    """[(page_no, text, parser_type), ...] — 텍스트 레이어."""
    out = []
    with pdfplumber.open(path) as pdf:
        for i, pg in enumerate(pdf.pages, start=1):
            out.append((i, pg.extract_text() or "", "text-layer"))
    return out


def _pages_unstructured(path):
    """unstructured로 요소 추출 → 페이지별 텍스트로 합침. 실패 시 예외(호출부에서 폴백)."""
    from unstructured.partition.pdf import partition_pdf
    elements = partition_pdf(filename=path, strategy=config.UNSTRUCTURED_STRATEGY)
    by_page = {}
    for el in elements:
        page = getattr(el.metadata, "page_number", None) or 1
        if el.text:
            by_page.setdefault(page, []).append(el.text)
    return [(page, "\n".join(texts), "unstructured") for page, texts in sorted(by_page.items())]


def _extract_file(path):
    """파일 1개 → 페이지 목록. USE_UNSTRUCTURED면 unstructured 우선, 실패 시 pdfplumber."""
    if config.USE_UNSTRUCTURED:
        try:
            return _pages_unstructured(path)
        except Exception:
            pass  # 미설치/파싱 실패 → 폴백
    return _pages_pdfplumber(path)


def load_pages(ref_dir=None):
    """근거 PDF들을 페이지 단위로 적재.

    반환: [{source, page, text, parser_type, warning}, ...]
    """
    pages = []
    for path in list_reference_pdfs(ref_dir):
        source = os.path.basename(path)
        for page_no, text, parser in _extract_file(path):
            scanned = len(text.strip()) < config.TEXT_LAYER_MIN_CHARS
            pages.append({
                "source": source,
                "page": page_no,
                "text": text,
                "parser_type": "none" if scanned else parser,
                "warning": "텍스트 레이어 없음(스캔 의심) — OCR 미적용" if scanned else "",
            })
    return pages
