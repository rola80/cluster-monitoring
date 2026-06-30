"""Streamlit UI: ① 기준 문서(근거)를 RAG 단계별(적재→분할→임베딩→인덱싱)로 구축 →
② 회사 구비서류 업로드 → 적합 판정.
실행:  uv run cluster-app   (protobuf 충돌 회피 런처. `streamlit run`은 인덱싱 단계서 실패할 수 있음)
"""
import os
import shutil
import tempfile
import zipfile
from datetime import date

import streamlit as st

from cluster_screening import PROJECT_ROOT, config, pipeline
from cluster_screening.pipeline import report, rules_engine

st.set_page_config(page_title="환경기업지원사업 제출서류검토기", layout="wide")

# 제목 옆 KEITI 로고(파일 있으면 표시). assets/keiti_logo.png 에 로고를 두세요(또는 LOGO_PATH 환경변수).
_logo = os.getenv("LOGO_PATH", os.path.join(PROJECT_ROOT, "assets", "keiti_logo.png"))
_lc1, _lc2 = st.columns([1, 7], vertical_alignment="center")
if os.path.exists(_logo):
    _lc1.image(_logo)
_lc2.title("환경기업지원사업 제출서류검토기")

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_META = ("source", "page", "parser_type", "token_count", "warning", "article")


def _needs_password(uploads):
    """업로드된 zip 중 암호가 걸린 게 있으면 True(그때만 비밀번호 요청)."""
    for f in uploads or []:
        if not f.name.lower().endswith(".zip"):
            continue
        try:
            f.seek(0)
            enc = any(i.flag_bits & 0x1 for i in zipfile.ZipFile(f).infolist())
            f.seek(0)
            if enc:
                return True
        except Exception:
            f.seek(0)
            return True
    return False


# ════════════════ ① 기준 문서 — 판정 근거 ════════════════
st.header("① 기준 문서 — 판정 근거")
st.caption("모집공고·운영규정·관리지침을 올리면 검색용 근거로 처리합니다(적재→분할→임베딩→인덱싱 자동).")

ref_up = st.file_uploader("기준 문서 (PDF·HWP, 여러 개)", type=["pdf", "hwp"],
                          accept_multiple_files=True, key="ref_up")
has_default = os.path.isdir(config.RAG_REFERENCE_DIR) and any(
    n.lower().endswith((".pdf", ".hwp")) for n in os.listdir(config.RAG_REFERENCE_DIR))

no_key = config.RAG_EMBED_PROVIDER == "openai" and not config.OPENAI_API_KEY
if no_key:
    st.warning("OpenAI 임베딩에 `OPENAI_API_KEY`가 필요합니다(.env). offline 모드: `RAG_EMBED_PROVIDER=offline`")

bc1, bc2 = st.columns(2)
with bc1:
    do_proc = st.button("기준 문서 처리", type="primary", disabled=not ref_up or no_key)
with bc2:
    do_default = st.button("기본 문서 사용 (data/reference)", disabled=not has_default or no_key)

if do_proc or do_default:
    st.session_state.pop("ref_indexed", None)
    try:
        from cluster_screening.rag import chunking, ingestion
        from cluster_screening.rag import index as ragidx
        with st.status("기준 문서 처리 중…", expanded=True) as status:
            st.write("📥 문서 적재·텍스트 추출…")
            if do_proc:
                refdir = tempfile.mkdtemp(prefix="ref_")
                try:
                    for f in ref_up:
                        with open(os.path.join(refdir, f.name), "wb") as out:
                            out.write(f.getbuffer())
                    pages = ingestion.load_pages(refdir)
                finally:
                    shutil.rmtree(refdir, ignore_errors=True)
            else:
                pages = ingestion.load_pages()
            st.write("✂️ 의미단위로 분할…")
            chunks = chunking.chunk_pages(pages)
            st.write(f"🧮 임베딩 생성…({len(chunks)}청크)")
            embeds = ragidx.embed([c["text"] for c in chunks])
            st.write("🗄️ 인덱싱(검색 준비)…")
            col = ragidx.get_collection(reset=True)
            col.add(ids=[c["chunk_id"] for c in chunks],
                    documents=[c["text"] for c in chunks],
                    embeddings=embeds,
                    metadatas=[{k: c[k] for k in _META} for c in chunks])
            st.session_state["ref_indexed"] = {
                "chunks": len(chunks), "sources": sorted({c["source"] for c in chunks})}
            status.update(label=f"근거 문서 준비 완료 — {len(chunks)}청크", state="complete", expanded=False)
    except ModuleNotFoundError:
        st.error("RAG 미설치: `uv sync --extra rag` 필요.")
    except Exception as e:
        st.error(f"처리 실패: {e}")

ref_idx = st.session_state.get("ref_indexed")
if ref_idx:
    st.success(f"✅ 인덱싱 완료 — {ref_idx['chunks']}청크({', '.join(ref_idx['sources'])}) 검색 준비됨")
    _rules = pipeline.load_rules()
    with st.expander("📋 이 기준으로 판정합니다", expanded=True):
        st.markdown("**판단기준 (적합 / 부적합 / 확인필요)**")
        for c in _rules["criteria"]:
            st.markdown(f"- {c['name']}")
        st.markdown(f"**가점 (합산 최대 {_rules['meta']['bonus_cap']}점, 잠정)**")
        for b in _rules.get("bonus", []):
            tag = ("−5점 감점" if b["points"] < 0
                   else f"{b['points']}점" + ("/건" if b.get("per_case") else ""))
            st.markdown(f"- {b['name']} — **{tag}**")
        st.caption("각 판정에 위 문서의 근거 조항이 첨부됩니다. 가점은 증빙 건수로 잠정 산정하고 "
                   "유효기간·주최요건 등 유효성은 사람이 최종 확인합니다.")
    with st.expander("🔎 근거 조항 검색(선택)"):
        q = st.text_input("검색어", key="ref_q", placeholder="예: 국세·지방세 체납 기업 제외")
        if q:
            from cluster_screening.rag import retriever
            hits = retriever.search(q, top_k=5)
            if not hits:
                st.info("근거 조항 없음 — 질의 키워드를 포함한 조항을 찾지 못했습니다.")
            for h in hits:
                loc = f'{h["source"]} p.{h["page"]}' + (f' · {h["article"]}' if h.get("article") else "")
                with st.expander(f'[{h["score"]}] {loc}'):
                    st.write(h["text"][:500])

st.divider()

# ════════════════ ② 회사 구비서류 검토 ════════════════
st.header("② 회사 구비서류 검토")
if not ref_idx:
    st.caption("※ 위 ①에서 기준 문서 인덱싱을 마치면 판정에 근거 조항이 붙습니다. (없어도 룰 판정은 가능)")

cc1, cc2 = st.columns(2)
with cc1:
    company = st.text_input("기업명", "")
with cc2:
    apply_d = st.date_input("입주신청일", value=date.today())

up = st.file_uploader("회사 구비서류 (zip 또는 PDF 다중)", type=["zip", "pdf"],
                      accept_multiple_files=True, key="company_up")

pw = ""
need_pw = _needs_password(up)
if need_pw:
    st.warning("🔒 비밀번호가 걸린 압축파일이 감지됐습니다. 압축 비밀번호를 입력하세요.")
    pw = st.text_input("압축 비밀번호", type="password", key="zip_pw")

if st.button("검토 실행", type="primary", disabled=not up or (need_pw and not pw)):
    work = tempfile.mkdtemp(prefix="cluster_ui_")
    try:
        paths = []
        for f in up:
            p = os.path.join(work, f.name)
            with open(p, "wb") as out:
                out.write(f.getbuffer())
            paths.append(p)
        src = work if len(paths) > 1 or paths[0].endswith(".pdf") else paths[0]

        bar = st.progress(0.0, "분석 중…")
        logbox = st.empty()
        logs = []

        def prog(done, n, msg):
            logs.append(msg)
            bar.progress(min(done / max(n, 1), 1.0), msg)
            logbox.code("\n".join(logs[-12:]))   # 단계별 라이브 로그

        record, rules = pipeline.process_company(src, apply_date=apply_d, pw=pw,
                                                 progress=prog, workdir=work)
        judgment = rules_engine.evaluate(record, rules)
        bar.empty()
        logbox.empty()

        name = company or "기업"
        out_path = os.path.join(work, f"판정결과_{name}.xlsx")
        report.build_report(company or "(미지정)", record, judgment, out_path)
        with open(out_path, "rb") as fp:
            report_bytes = fp.read()
        st.session_state["result"] = {
            "name": name, "judgment": judgment, "logs": logs,
            "doc_log": record["doc_log"], "report_bytes": report_bytes,
        }
    except RuntimeError as e:
        st.error(f"처리 실패: {e}  — 압축 비밀번호를 확인하세요.")
    except Exception as e:
        st.error(f"처리 실패: {e}")
    finally:
        shutil.rmtree(work, ignore_errors=True)  # 업로드·추출 원문(PII) 즉시 삭제

res = st.session_state.get("result")
if res:
    j = res["judgment"]
    h1, h2 = st.columns([5, 1])
    with h1:
        color = {"적합": "green", "부적합": "red", "확인필요": "orange"}.get(j["overall"], "gray")
        st.markdown(f"## 종합판정: :{color}[{j['overall']}]  ·  가점(잠정) {j['bonus_total']}점")
    with h2:
        if st.button("결과 지우기"):
            del st.session_state["result"]
            st.rerun()

    st.download_button("판정 리포트(xlsx) 다운로드", res["report_bytes"],
                       file_name=f"판정결과_{res['name']}.xlsx", mime=XLSX_MIME)

    # 불러오기 상태 — 텍스트 추출 실패/미분류 파일을 사람이 확인하도록 알림
    fail = [d["file"] for d in res["doc_log"] if d.get("불러옴") == "X"]
    uncls = [d["file"] for d in res["doc_log"] if d["유형"] == "미분류"]
    if fail:
        st.error("⚠ 텍스트를 불러오지 못한 파일 — **사람이 직접 확인 필요**:\n\n- " + "\n- ".join(fail))
    if uncls:
        st.warning("❓ 유형이 분류되지 않은 파일(확인 권장):\n\n- " + "\n- ".join(uncls))
    if not fail and not uncls:
        st.caption("✅ 업로드한 모든 파일을 불러와 분류했습니다.")
    if res.get("logs"):
        with st.expander("🧾 처리 로그(단계별)"):
            st.code("\n".join(res["logs"]))

    st.subheader("판단기준별 결과")
    st.dataframe([{"구분": r["section"], "판단기준": r["name"], "판정": r["status"],
                   "근거/세부": r["detail"], "evidence": r["evidence"],
                   "근거조항(기준 문서)": r.get("basis", "")}
                  for r in j["results"]], use_container_width=True)

    cA, cB = st.columns(2)
    with cA:
        st.subheader("가점 증빙")
        st.dataframe(j["bonus"], use_container_width=True)
    with cB:
        st.subheader("서류 처리내역")
        st.dataframe(res["doc_log"], use_container_width=True)

    st.subheader("성과 년도별 정리")
    st.caption("건수·고용인력(연번)은 자동 추출, 금액 등은 사람 최종 확인")
    st.dataframe(j["performance"], use_container_width=True)

    fin = j.get("financials") or {}
    if fin.get("items"):
        st.subheader("재무 항목(연도별)")
        src = (fin.get("file") or "") + (f" p.{fin['page']}" if fin.get("page") else "")
        st.caption(f"제품매출·영업외손익·매출액·영업이익 — 출처: **{src or '재무제표'}** · 사람 최종 확인")
        frows = [{"항목": item, "연도": yr, "값": val, "출처": src}
                 for item, yv in fin["items"].items() for yr, val in (yv or {}).items()]
        st.dataframe(frows or [{"항목": "(추출 없음)", "연도": "", "값": "", "출처": src}],
                     use_container_width=True, hide_index=True)
