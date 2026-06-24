"""근거 문서(공고·규정·지침) 적재 + 텍스트 추출 + 진단.

판정 근거 검색의 Source. 지원 형식:
  - PDF : pdfplumber(텍스트 레이어). config.USE_UNSTRUCTURED=1 이면 unstructured(미설치/실패 시 폴백).
  - HWP : pyhwp(hwp5)로 본문 텍스트 추출(한글 정부 규정 원본이 HWP인 경우가 많음).
HWP는 고정 페이지 개념이 없어 page=1로 적재하되, 청킹 단계에서 '제N조'로 근거 위치를 태깅한다.
텍스트가 거의 없으면(스캔 의심) warning을 남긴다(OCR 적용은 후속 과제).
"""
import os
import glob
import pdfplumber
from .. import config

_EXTS = (".pdf", ".hwp")


def list_reference_files(ref_dir=None):
    """근거 문서 경로 목록(PDF·HWP, 하위 폴더 포함)."""
    ref_dir = ref_dir or config.RAG_REFERENCE_DIR
    if not os.path.isdir(ref_dir):
        return []
    files = []
    for ext in _EXTS:
        files += glob.glob(os.path.join(ref_dir, "**", f"*{ext}"), recursive=True)
    return sorted(files)


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


def _pages_hwp(path):
    """pyhwp(hwp5)로 HWP 본문 텍스트 추출. 전체를 page=1 한 덩어리로 반환."""
    import tempfile
    from contextlib import closing
    from hwp5.hwp5txt import TextTransform
    from hwp5.xmlmodel import Hwp5File

    transform = TextTransform().transform_hwp5_to_text
    fd, tmp = tempfile.mkstemp(suffix=".txt")
    os.close(fd)
    try:
        with closing(Hwp5File(path)) as hwp5file:
            with open(tmp, "wb") as dest:
                transform(hwp5file, dest)
        with open(tmp, encoding="utf-8") as f:
            text = f.read()
    finally:
        os.remove(tmp)
    return [(1, text, "hwp5")]


def _extract_file(path):
    """파일 1개 → [(page_no, text, parser_type), ...]. 확장자로 추출기 선택."""
    low = path.lower()
    if low.endswith(".hwp"):
        return _pages_hwp(path)
    # PDF
    if config.USE_UNSTRUCTURED:
        try:
            return _pages_unstructured(path)
        except Exception:
            pass  # 미설치/파싱 실패 → 폴백
    return _pages_pdfplumber(path)


def load_pages(ref_dir=None):
    """근거 문서들을 페이지 단위로 적재.

    반환: [{source, page, text, parser_type, warning}, ...]
    """
    pages = []
    for path in list_reference_files(ref_dir):
        source = os.path.basename(path)
        try:
            extracted = _extract_file(path)
        except Exception as e:
            pages.append({"source": source, "page": 1, "text": "",
                          "parser_type": "none", "warning": f"추출 실패: {e}"})
            continue
        for page_no, text, parser in extracted:
            scanned = len(text.strip()) < config.TEXT_LAYER_MIN_CHARS
            pages.append({
                "source": source,
                "page": page_no,
                "text": text,
                "parser_type": "none" if scanned else parser,
                "warning": "텍스트 없음(스캔/추출실패 의심) — 확인 필요" if scanned else "",
            })
    return pages
