"""인터넷 되는 PC에서 실행 → 오프라인에 필요한 모델/데이터를 bundle 폴더로 내려받는다.
prepare_offline_bundle.ps1 가 호출한다. 단독 실행: python deploy/_fetch_models.py <bundle_dir>
"""
import os
import sys

bundle = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), "bundle")
models = os.path.join(bundle, "models")
easyocr_dir = os.path.join(bundle, "easyocr")
nltk_dir = os.path.join(bundle, "nltk_data")
for d in (models, easyocr_dir, nltk_dir):
    os.makedirs(d, exist_ok=True)

# 1) RAG 임베딩 모델(ko-sroberta) → 로컬 폴더. 오프라인에서 RAG_EMBED_MODEL을 이 경로로 지정.
print("[1/3] RAG 임베딩 모델 다운로드…")
from huggingface_hub import snapshot_download

snapshot_download("jhgan/ko-sroberta-multitask",
                  local_dir=os.path.join(models, "ko-sroberta"))

# 2) EasyOCR 모델(ko, en) → bundle/easyocr. 오프라인에서 OCR_MODEL_DIR로 지정.
print("[2/3] EasyOCR 모델 다운로드…")
import easyocr

easyocr.Reader(["ko", "en"], gpu=False, model_storage_directory=easyocr_dir, download_enabled=True)

# 3) unstructured가 쓰는 NLTK 데이터 → bundle/nltk_data. 오프라인에서 NLTK_DATA로 지정.
print("[3/3] NLTK 데이터 다운로드…")
import nltk

for pkg in ["punkt", "punkt_tab", "averaged_perceptron_tagger", "averaged_perceptron_tagger_eng"]:
    try:
        nltk.download(pkg, download_dir=nltk_dir)
    except Exception as e:
        print(f"  (경고) {pkg} 다운로드 실패: {e}")

print("완료 →", bundle)
