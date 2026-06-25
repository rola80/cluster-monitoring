"""하이브리드 추출: 텍스트 레이어가 있으면 pdfplumber, 없으면(스캔) OCR.

OCR 엔진(우선순위):
  1) EasyOCR  — 한글+영어 내장, CPU, 최초 1회 모델 다운로드 후 오프라인(config.OCR_ENGINE="easyocr").
  2) tesseract — EasyOCR 미설치 시 폴백(config.OCR_LANG, 'kor' 언어팩 필요).
config.USE_DOCLING=True 면 스캔본을 Docling(레이아웃·표 복원)+EasyOCR로 처리(느리고 RAM 큼; 표 정밀추출용).

반환: {"text": str, "method": "text"|"ocr"|"docling"|"none", "pages": int, "ocr_used": bool}
"""
import pdfplumber

from .. import config

_EASYOCR = None   # EasyOCR Reader 싱글톤(모델 1회 로드 후 재사용)
_DOCLING = None   # Docling DocumentConverter 싱글톤


def _text_layer(pdf_path):
    parts, n = [], 0
    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
        for pg in pdf.pages:
            parts.append(pg.extract_text() or "")
    return "\n".join(parts), n


def _rasterize(pdf_path, dpi):
    """PDF → PIL 이미지 리스트. pdf2image → PyMuPDF → pdfplumber 순으로 시도."""
    try:
        from pdf2image import convert_from_path
        return convert_from_path(pdf_path, dpi=dpi)
    except Exception:
        pass
    try:
        import fitz  # PyMuPDF
        from PIL import Image
        imgs = []
        doc = fitz.open(pdf_path)
        zoom = dpi / 72
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            imgs.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
        return imgs
    except Exception:
        pass
    imgs = []
    with pdfplumber.open(pdf_path) as pdf:
        for pg in pdf.pages:
            imgs.append(pg.to_image(resolution=dpi).original)
    return imgs


# ── OCR 엔진들 ──
def _get_easyocr():
    global _EASYOCR
    if _EASYOCR is None:
        import easyocr
        kw = {"gpu": False, "verbose": False,
              "download_enabled": config.OCR_DOWNLOAD_ENABLED}  # 폐쇄망: 0이면 다운로드 안 함
        if config.OCR_MODEL_DIR:
            kw["model_storage_directory"] = config.OCR_MODEL_DIR  # 번들 모델 폴더
        _EASYOCR = easyocr.Reader(config.OCR_LANGS, **kw)
    return _EASYOCR


def _ocr_easyocr(pdf_path):
    import numpy as np
    reader = _get_easyocr()
    out = []
    for img in _rasterize(pdf_path, config.OCR_DPI):
        lines = reader.readtext(np.array(img), detail=0)  # 텍스트만(좌표 제외)
        out.append("\n".join(lines))
    return "\n".join(out)


def _ocr_tesseract(pdf_path):
    import pytesseract
    out = []
    for img in _rasterize(pdf_path, config.OCR_DPI):
        out.append(pytesseract.image_to_string(img, lang=config.OCR_LANG))
    return "\n".join(out)


def _ocr(pdf_path):
    """EasyOCR 우선, 미설치 시 tesseract."""
    if config.OCR_ENGINE == "easyocr":
        try:
            return _ocr_easyocr(pdf_path)
        except ImportError:
            return _ocr_tesseract(pdf_path)
    return _ocr_tesseract(pdf_path)


# ── Docling(선택) ──
def _get_docling():
    global _DOCLING
    if _DOCLING is None:
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
        from docling.datamodel.base_models import InputFormat
        from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions
        from docling.document_converter import DocumentConverter, PdfFormatOption
        opts = PdfPipelineOptions()
        opts.do_ocr = config.ENABLE_OCR
        opts.do_table_structure = config.DOCLING_TABLES
        opts.ocr_options = EasyOcrOptions(lang=config.OCR_LANGS)
        # 기본 docling_parse 백엔드는 일부 빌드에서 glyph 리소스 누락 → pypdfium2로 우회
        _DOCLING = DocumentConverter(format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=opts,
                                             backend=PyPdfiumDocumentBackend)})
    return _DOCLING


def _extract_docling(pdf_path, n):
    res = _get_docling().convert(pdf_path)
    return {"text": res.document.export_to_markdown(),
            "method": "docling", "pages": n, "ocr_used": True}


def extract(pdf_path):
    text, n = _text_layer(pdf_path)
    per_page = len(text.replace("\n", "")) / max(n, 1)
    if per_page >= config.TEXT_LAYER_MIN_CHARS:
        return {"text": text, "method": "text", "pages": n, "ocr_used": False}

    # 스캔으로 판단 → Docling(선택) 또는 OCR
    if config.ENABLE_OCR and config.USE_DOCLING:
        try:
            return _extract_docling(pdf_path, n)
        except Exception:
            pass  # docling 실패 → 일반 OCR로 폴백
    if config.ENABLE_OCR:
        try:
            otext = _ocr(pdf_path)
            if otext.strip():
                return {"text": otext, "method": "ocr", "pages": n, "ocr_used": True}
        except Exception as e:
            return {"text": text, "method": "none", "pages": n, "ocr_used": False,
                    "error": f"OCR 실패: {e}"}
    return {"text": text, "method": "none", "pages": n, "ocr_used": False,
            "note": "텍스트 레이어 없음(스캔) — OCR 미적용"}
