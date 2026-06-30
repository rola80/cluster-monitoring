"""하이브리드 추출: 텍스트 레이어가 있으면 pdfplumber, 없으면(스캔) OCR.

OCR 엔진(우선순위):
  1) EasyOCR  — 한글+영어 내장, CPU, 최초 1회 모델 다운로드 후 오프라인(config.OCR_ENGINE="easyocr").
  2) tesseract — EasyOCR 미설치 시 폴백(config.OCR_LANG, 'kor' 언어팩 필요).
config.USE_DOCLING=True 면 스캔본을 Docling(레이아웃·표 복원)+EasyOCR로 처리(느리고 RAM 큼; 표 정밀추출용).

반환: {"text": str, "method": "text"|"ocr"|"docling"|"none", "pages": int, "ocr_used": bool}
"""
import os
import threading

import pdfplumber

from .. import config

_EASYOCR = None   # EasyOCR Reader 싱글톤(모델 1회 로드 후 재사용)
_EASYOCR_LOCK = threading.Lock()  # 병렬 추출 시 모델 중복 로드 방지
_DOCLING = None   # Docling DocumentConverter 싱글톤


def _text_layer(pdf_path):
    """반환: (페이지별 텍스트 리스트, 페이지수)."""
    parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for pg in pdf.pages:
            parts.append(pg.extract_text() or "")
    return parts, len(parts)


def _rasterize(pdf_path, dpi, max_pages=0):
    """PDF → PIL 이미지 리스트(앞 max_pages만, 0=전체). pdf2image → PyMuPDF → pdfplumber 순."""
    try:
        from pdf2image import convert_from_path
        kw = {"dpi": dpi}
        if max_pages:
            kw["last_page"] = max_pages   # 앞 N페이지만 래스터화(속도)
        return convert_from_path(pdf_path, **kw)
    except Exception:
        pass
    try:
        import fitz  # PyMuPDF
        from PIL import Image
        imgs = []
        doc = fitz.open(pdf_path)
        zoom = dpi / 72
        for i, page in enumerate(doc):
            if max_pages and i >= max_pages:
                break
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            imgs.append(Image.frombytes("RGB", [pix.width, pix.height], pix.samples))
        return imgs
    except Exception:
        pass
    imgs = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, pg in enumerate(pdf.pages):
            if max_pages and i >= max_pages:
                break
            imgs.append(pg.to_image(resolution=dpi).original)
    return imgs


# ── OCR 엔진들 ──
def _get_easyocr():
    global _EASYOCR
    if _EASYOCR is None:
        with _EASYOCR_LOCK:                 # 병렬 추출 시 중복 로드 방지(이중 검사)
            if _EASYOCR is None:
                import easyocr
                # torch 스레드 균형: 워커 N개가 코어를 나눠 쓰도록(1추론=전체코어 → 직렬화 방지)
                try:
                    import torch
                    torch.set_num_threads(max(1, (os.cpu_count() or 4) // max(1, config.EXTRACT_WORKERS)))
                except Exception:
                    pass
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
    for img in _rasterize(pdf_path, config.OCR_DPI, config.OCR_MAX_PAGES):
        lines = reader.readtext(np.array(img), detail=0)  # 텍스트만(좌표 제외)
        out.append("\n".join(lines))
    return out


def _ocr_tesseract(pdf_path):
    import pytesseract
    out = []
    for img in _rasterize(pdf_path, config.OCR_DPI, config.OCR_MAX_PAGES):
        out.append(pytesseract.image_to_string(img, lang=config.OCR_LANG))
    return out


def _ocr_openai(pdf_path):
    """OpenAI Vision으로 스캔 페이지 텍스트 추출(앞 OCR_MAX_PAGES 페이지). 페이지당 1회 호출."""
    import base64
    import io

    from openai import OpenAI
    if not config.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY가 없어 Vision OCR을 쓸 수 없습니다(.env 확인).")
    client = OpenAI(api_key=config.OPENAI_API_KEY)
    prompt = "이 문서 이미지의 모든 텍스트(한국어·숫자·기호)를 원문 그대로 추출하라. 설명·요약 없이 텍스트만 출력."
    out = []
    for img in _rasterize(pdf_path, config.OCR_DPI, config.OCR_MAX_PAGES):
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="PNG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        resp = client.chat.completions.create(
            model=config.OCR_VISION_MODEL, temperature=0,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
            ]}],
        )
        out.append(resp.choices[0].message.content or "")
    return out


def _ocr(pdf_path):
    """OCR 엔진 분기 → 페이지별 텍스트 리스트. openai(Vision, 기본) | easyocr | tesseract."""
    eng = config.OCR_ENGINE
    if eng == "openai":
        return _ocr_openai(pdf_path)
    if eng == "easyocr":
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
    """반환 dict: text, pages_text(페이지별 리스트), method, pages, ocr_used."""
    parts, n = _text_layer(pdf_path)
    text = "\n".join(parts)
    per_page = len(text.replace("\n", "")) / max(n, 1)
    if per_page >= config.TEXT_LAYER_MIN_CHARS:
        return {"text": text, "pages_text": parts, "method": "text", "pages": n, "ocr_used": False}

    # 스캔으로 판단 → Docling(선택) 또는 OCR
    if config.ENABLE_OCR and config.USE_DOCLING:
        try:
            return _extract_docling(pdf_path, n)
        except Exception:
            pass  # docling 실패 → 일반 OCR로 폴백
    if config.ENABLE_OCR:
        try:
            opages = _ocr(pdf_path)            # 페이지별 OCR 텍스트 리스트
            otext = "\n".join(opages)
            if otext.strip():
                return {"text": otext, "pages_text": opages, "method": "ocr",
                        "pages": n, "ocr_used": True}
        except Exception as e:
            return {"text": text, "pages_text": parts, "method": "none", "pages": n,
                    "ocr_used": False, "error": f"OCR 실패: {e}"}
    return {"text": text, "pages_text": parts, "method": "none", "pages": n,
            "ocr_used": False, "note": "텍스트 레이어 없음(스캔) — OCR 미적용"}
