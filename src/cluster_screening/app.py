"""Streamlit UI: 기업별 구비서류(zip) 업로드 → 적합 판정 → 리포트 다운로드.
실행:  streamlit run cluster_screening/app.py
"""
import os
import shutil
import tempfile
from datetime import date

import streamlit as st

from cluster_screening import auth, config, pipeline
from cluster_screening.pipeline import report, rules_engine

st.set_page_config(page_title="입주기업 서류적합 검토", layout="wide")

# ── 로그인 게이트 ── (미로그인 시 로그인 폼만 표시하고 앱 본문은 차단)
if not auth.streamlit_login_gate():
    st.stop()
auth.streamlit_logout_button()

st.title("창업·벤처 녹색융합클러스터 — 신청서류 적합 검토")

with st.sidebar:
    st.header("설정")
    company = st.text_input("기업명", "")
    apply_d = st.date_input("입주신청일", value=date.today())
    pw = st.text_input("구비서류 zip 비밀번호(있으면)", type="password",
                       value=config.ZIP_PASSWORD)
    st.caption(f"OCR: {'ON' if config.ENABLE_OCR else 'OFF'} · "
               f"LLM: {'ON('+config.LLM_MODEL+')' if config.ENABLE_LLM else 'OFF'}")

    # ── 근거 검색(RAG) ── 공고·규정·지침에서 판정 근거 조항 검색
    st.divider()
    st.subheader("📚 근거 검색(RAG)")
    rag_q = st.text_input("근거 조항 검색", key="rag_q",
                          placeholder="예: 국세·지방세 체납 기업 제외")
    if rag_q:
        try:
            from cluster_screening.rag import retriever
            with st.spinner("검색 중…"):
                hits = retriever.search(rag_q, top_k=5)
            if not hits:
                st.caption("인덱스가 비어 있습니다. 터미널에서 `uv run rag-index` 를 먼저 실행하세요.")
            for h in hits:
                loc = f'{h["source"]} p.{h["page"]}'
                if h.get("article"):
                    loc += f' · {h["article"]}'
                with st.expander(f'[{h["score"]}] {loc}'):
                    if h.get("warning"):
                        st.caption(f"⚠ {h['warning']}")
                    st.write(h["text"][:500])
        except ModuleNotFoundError:
            st.caption("RAG 미설치: `uv sync --extra rag` 후 `uv run rag-index`.")
        except Exception as e:
            st.caption(f"검색 불가: {e}")

up = st.file_uploader("구비서류 업로드 (zip 또는 PDF 다중)",
                      type=["zip", "pdf"], accept_multiple_files=True)

if st.button("검토 실행", type="primary", disabled=not up):
    work = tempfile.mkdtemp(prefix="cluster_ui_")
    paths = []
    for f in up:
        p = os.path.join(work, f.name)
        with open(p, "wb") as out:
            out.write(f.getbuffer())
        paths.append(p)
    src = work if len(paths) > 1 or paths[0].endswith(".pdf") else paths[0]

    bar = st.progress(0.0, "분석 중…")
    def prog(i, n, fn):
        bar.progress((i + 1) / max(n, 1), f"[{i+1}/{n}] {fn}")
    record, rules = pipeline.process_company(src, apply_date=apply_d, pw=pw,
                                             progress=prog, workdir=work)
    judgment = rules_engine.evaluate(record, rules)
    bar.empty()

    color = {"적합": "green", "부적합": "red", "확인필요": "orange"}.get(judgment["overall"], "gray")
    st.markdown(f"## 종합판정: :{color}[{judgment['overall']}]  ·  가점(잠정) {judgment['bonus_total']}점")

    st.subheader("판단기준별 결과")
    st.dataframe([{"구분": r["section"], "판단기준": r["name"], "판정": r["status"],
                   "근거/세부": r["detail"], "evidence": r["evidence"],
                   "근거조항(규정·RAG)": r.get("basis", "")}
                  for r in judgment["results"]], use_container_width=True)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("가점 증빙")
        st.dataframe(judgment["bonus"], use_container_width=True)
    with c2:
        st.subheader("서류 처리내역")
        st.dataframe(record["doc_log"], use_container_width=True)

    st.subheader("성과 년도별 정리")
    st.caption("근거서류 제출 여부·건수는 자동, 연도별 금액·인원 정밀수치는 사람 확인")
    st.dataframe(judgment["performance"], use_container_width=True)

    out = os.path.join(work, f"판정결과_{company or '기업'}.xlsx")
    report.build_report(company or "(미지정)", record, judgment, out)
    with open(out, "rb") as f:
        st.download_button("판정 리포트(xlsx) 다운로드", f, file_name=os.path.basename(out),
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # 업로드·추출 원문(PII)·리포트 임시폴더 정리(다운로드 바이트는 위에서 이미 버튼에 적재됨)
    shutil.rmtree(work, ignore_errors=True)
