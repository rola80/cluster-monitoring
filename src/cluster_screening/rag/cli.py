"""RAG 콘솔: 근거 문서 인덱싱 / 검색.

  uv run rag-index                                  # data/reference/*.pdf 인덱싱
  uv run rag-search "창업 7년 기준이 무엇인가"        # 근거 조항 검색
"""
import argparse
from .. import config
from . import index, retriever


def index_main():
    ap = argparse.ArgumentParser(description="근거 문서 RAG 인덱싱")
    ap.add_argument("--ref", default=None, help=f"근거 PDF 폴더(기본: {config.RAG_REFERENCE_DIR})")
    a = ap.parse_args()
    print("인덱싱 중… (최초 1회 임베딩 모델 다운로드가 있을 수 있음)")
    stat = index.build_index(a.ref)
    if not stat["chunks"]:
        print(f"근거 PDF가 없습니다. '{config.RAG_REFERENCE_DIR}' 에 공고·규정·지침 PDF를 넣으세요. "
              f"(읽은 페이지 {stat['pages']})")
        return
    print(f"완료: PDF {stat['pdfs']}종 · 페이지 {stat['pages']} · 청크 {stat['chunks']}")
    print("근거 문서:", ", ".join(stat["sources"]))


def search_main():
    ap = argparse.ArgumentParser(description="근거 문서 RAG 검색")
    ap.add_argument("query", help="검색 질의")
    ap.add_argument("-k", type=int, default=None, help="결과 개수(기본 RAG_TOP_K)")
    a = ap.parse_args()
    hits = retriever.search(a.query, a.k)
    if not hits:
        print("결과 없음. 먼저 `uv run rag-index` 로 인덱싱하세요.")
        return
    for h in hits:
        loc = f'{h["source"]} p.{h["page"]}' + (f' {h["article"]}' if h.get("article") else "")
        warn = f'  ⚠ {h["warning"]}' if h.get("warning") else ""
        print(f'\n[{h["score"]}] {loc}{warn}')
        print("  " + h["text"][:200].replace("\n", " ").strip())
