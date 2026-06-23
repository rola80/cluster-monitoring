"""하이브리드 추출: 텍스트 레이어가 있으면 pdfplumber, 없으면(스캔) OCR.

반환: {"text": str, "method": "text"|"ocr"|"none", "pages": int, "ocr_used": bool}
OCR는 config.ENABLE_OCR 이고 tesseract(가급적 kor 언어팩)가 있을 때만 동작.
"""
import pdfplumber
from .. import config


def _text_layer(pdf_path):
    parts, n = [], 0
    with pdfplumber.open(pdf_path) as pdf:
        n = len(pdf.pages)
        for pg in pdf.pages:
            t = pg.extract_text() or ""
            parts.append(t)
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
        imgs = []
        doc = fitz.open(pdf_path)
        zoom = dpi / 72
        for page in doc:
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            from PIL import Image
            imgs.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
        return imgs
    except Exception:
        pass
    imgs = []
    with pdfplumber.open(pdf_path) as pdf:
        for pg in pdf.pages:
            imgs.append(pg.to_image(resolution=dpi).original)
    return imgs


def _ocr(pdf_path):
    import pytesseract
    text = []
    for img in _rasterize(pdf_path, config.OCR_DPI):
        text.append(pytesseract.image_to_string(img, lang=config.OCR_LANG))
    return "\n".join(text)


def extract(pdf_path):
    text, n = _text_layer(pdf_path)
    per_page = len(text.replace("\n", "")) / max(n, 1)
    if per_page >= config.TEXT_LAYER_MIN_CHARS:
        return {"text": text, "method": "text", "pages": n, "ocr_used": False}

    # 스캔으로 판단 → OCR
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
