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


def _reset_ref(*keys):
    """기준 문서 단계 상태 초기화(상위 단계 재실행 시 하위 단계 무효화)."""
    for k in keys:
        st.session_state.pop(k, None)


# ════════════════ ① 기준 문서 — 단계별 RAG 구축 ════════════════
st.header("① 기준 문서 — 판정 근거 구축")
st.caption("모집공고·운영규정·관리지침을 **적재 → 분할 → 임베딩 → 인덱싱** 순으로 단계별로 처리합니다. "
           "각 단계 결과를 확인하며 진행하세요.")

ref_up = st.file_uploader("기준 문서 (PDF·HWP, 여러 개)", type=["pdf", "hwp"],
                          accept_multiple_files=True, key="ref_up")
has_default = os.path.isdir(config.RAG_REFERENCE_DIR) and any(
    n.lower().endswith((".pdf", ".hwp")) for n in os.listdir(config.RAG_REFERENCE_DIR))

# ── 단계 1: 적재(Load & Parse) ──
st.markdown("**1단계 · 적재(Load)** — 파일을 읽어 텍스트를 추출합니다.")
lc1, lc2 = st.columns(2)
with lc1:
    do_load = st.button("📥 업로드한 문서 적재", disabled=not ref_up)
with lc2:
    do_load_default = st.button("📁 기본 문서 적재 (data/reference)", disabled=not has_default)

if do_load or do_load_default:
    _reset_ref("ref_pages", "ref_chunks", "ref_embeds", "ref_indexed")
    try:
        from cluster_screening.rag import ingestion
        if do_load:
            refdir = tempfile.mkdtemp(prefix="ref_")
            try:
                for f in ref_up:
                    with open(os.path.join(refdir, f.name), "wb") as out:
                        out.write(f.getbuffer())
                pages = ingestion.load_pages(refdir)
            finally:
                shutil.rmtree(refdir, ignore_errors=True)
        else:
            pages = ingestion.load_pages()  # data/reference
        st.session_state["ref_pages"] = pages
    except Exception as e:
        st.error(f"적재 실패: {e}")

pages = st.session_state.get("ref_pages")
if pages:
    nchars = sum(len(p["text"]) for p in pages)
    srcs = sorted({p["source"] for p in pages})
    m1, m2, m3 = st.columns(3)
    m1.metric("문서", f"{len(srcs)}개")
    m2.metric("페이지", f"{len(pages)}개")
    m3.metric("추출 글자수", f"{nchars:,}")
    st.dataframe([{"문서": p["source"], "page": p["page"], "추출방식": p["parser_type"],
                   "글자수": len(p["text"]), "경고": p["warning"]} for p in pages],
                 use_container_width=True, hide_index=True)
    with st.expander("추출 텍스트 미리보기"):
        st.text((pages[0]["text"] or "")[:1200])

# ── 단계 2: 분할(Split / Chunk) ──
if pages:
    st.markdown("**2단계 · 분할(Split·Chunk)** — 실제 조(條) 제목 단위로 나누고 metadata를 붙입니다.")
    if st.button("✂️ 청킹 실행"):
        _reset_ref("ref_chunks", "ref_embeds", "ref_indexed")
        from cluster_screening.rag import chunking
        st.session_state["ref_chunks"] = chunking.chunk_pages(pages)

chunks = st.session_state.get("ref_chunks")
if chunks:
    arts = sorted({c["article"] for c in chunks if c["article"]})
    avg_tok = sum(c["token_count"] for c in chunks) // len(chunks)
    m1, m2, m3 = st.columns(3)
    m1.metric("청크", f"{len(chunks)}개")
    m2.metric("조항 종류", f"{len(arts)}종")
    m3.metric("평균 토큰", f"{avg_tok}")
    if arts:
        st.caption("조항: " + ", ".join(arts[:14]) + (" …" if len(arts) > 14 else ""))
    st.dataframe([{"chunk_id": c["chunk_id"], "조항": c["article"] or "(서문)",
                   "토큰": c["token_count"], "미리보기": (c["text"] or "")[:80].replace("\n", " ")}
                  for c in chunks[:20]], use_container_width=True, hide_index=True)

# ── 단계 3: 임베딩(Embedding) ──
if chunks:
    st.markdown("**3단계 · 임베딩(Embedding)** — 청크를 벡터로 변환합니다.")
    if config.RAG_EMBED_PROVIDER == "openai":
        model_label = f"OpenAI · {config.RAG_OPENAI_EMBED_MODEL}"
    else:
        model_label = f"오프라인 · {config.RAG_EMBED_MODEL}"
    st.info(f"임베딩 모델: **{model_label}**  (`.env`의 `RAG_EMBED_PROVIDER`로 변경)")
    no_key = config.RAG_EMBED_PROVIDER == "openai" and not config.OPENAI_API_KEY
    if no_key:
        st.warning("OpenAI 임베딩을 쓰려면 `.env`에 `OPENAI_API_KEY`를 넣으세요. "
                   "(키 없이 쓰려면 `.env`에 `RAG_EMBED_PROVIDER=offline`)")
    if st.button("🧮 임베딩 실행", disabled=no_key):
        _reset_ref("ref_embeds", "ref_indexed")
        try:
            from cluster_screening.rag import index as ragidx
            with st.spinner(f"임베딩 중… ({model_label})"):
                st.session_state["ref_embeds"] = ragidx.embed([c["text"] for c in chunks])
        except ModuleNotFoundError:
            st.error("RAG 미설치: `uv sync --extra rag` 필요.")
        except Exception as e:
            st.error(f"임베딩 실패: {e}")

embeds = st.session_state.get("ref_embeds")
if embeds:
    dim = len(embeds[0]) if embeds else 0
    m1, m2 = st.columns(2)
    m1.metric("벡터", f"{len(embeds)}개")
    m2.metric("차원", f"{dim}")

# ── 단계 4: 인덱싱(Vector DB) ──
if embeds:
    st.markdown("**4단계 · 인덱싱(Vector DB)** — 벡터를 로컬 Chroma에 저장해 검색을 준비합니다.")
    if st.button("🗄️ 인덱싱 실행", type="primary"):
        try:
            from cluster_screening.rag import index as ragidx
            with st.spinner("Chroma 인덱싱 중…"):
                col = ragidx.get_collection(reset=True)
                col.add(ids=[c["chunk_id"] for c in chunks],
                        documents=[c["text"] for c in chunks],
                        embeddings=embeds,
                        metadatas=[{k: c[k] for k in _META} for c in chunks])
            st.session_state["ref_indexed"] = {
                "chunks": len(chunks), "sources": sorted({c["source"] for c in chunks})}
        except Exception as e:
            st.error(f"인덱싱 실패: {e}")

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
            for h in retriever.search(q, top_k=5):
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
    st.caption("근거서류 제출 여부·건수는 자동, 연도별 금액·인원 정밀수치는 사람 확인")
    st.dataframe(j["performance"], use_container_width=True)
