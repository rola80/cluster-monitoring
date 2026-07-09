"""Streamlit UI: ① 기준 문서(근거)를 RAG 단계별(적재→분할→임베딩→인덱싱)로 구축 →
② 회사 구비서류 업로드 → 적합 판정.
실행:  uv run cluster-app   (protobuf 충돌 회피 런처. `streamlit run`은 인덱싱 단계서 실패할 수 있음)
"""
import os
import shutil
import tempfile
import zipfile

import streamlit as st

from cluster_screening import PROJECT_ROOT, config, pipeline
from cluster_screening.pipeline import masking, report, rules_engine

st.set_page_config(page_title="녹색융합클러스터 입주기업 신청서류 적합성 검토 및 성과 정리 자동화",
                   layout="wide")

# 제목 옆 KEITI 로고(파일 있으면 표시). assets/keiti_logo.png 에 로고를 두세요(또는 LOGO_PATH 환경변수).
_logo = os.getenv("LOGO_PATH", os.path.join(PROJECT_ROOT, "assets", "keiti_logo.png"))
_lc1, _lc2 = st.columns([1, 7], vertical_alignment="center")
if os.path.exists(_logo):
    _lc1.image(_logo)
_lc2.title("녹색융합클러스터 입주기업 신청서류 적합성 검토 및 성과 정리 자동화")

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
st.caption("기업명·입주신청일은 제출 서류(입주신청서·사업자등록증)에서 자동으로 추출합니다.")

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

        # 입주신청일은 인자로 주지 않는다 → process_company가 입주신청서에서 자동 추출
        record, rules = pipeline.process_company(src, apply_date=None, pw=pw,
                                                 progress=prog, workdir=work)
        judgment = rules_engine.evaluate(record, rules)
        judgment = masking.mask_judgment(judgment, record)   # PII 마스킹(출력용)
        pii_audit = masking.get_audit()   # 외부 전송 전 + 출력 단계 마스킹 감사 기록(화면 표시용)
        bar.empty()
        logbox.empty()

        # 기업명: 추출된 상호에서 자동 설정(없으면 '기업'). 상호는 식별정보라 원본 유지
        name = next((d["fields"].get("상호") for d in record["docs"].values()
                     if d.get("fields", {}).get("상호")), None) or "기업"
        out_path = os.path.join(work, f"판정결과_{name}.xlsx")
        report.build_report(name, record, judgment, out_path)
        with open(out_path, "rb") as fp:
            report_bytes = fp.read()
        st.session_state["result"] = {
            "name": name, "judgment": judgment, "logs": logs,
            "doc_log": record["doc_log"], "report_bytes": report_bytes,
            "pii_audit": pii_audit,
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

    # 🔒 개인정보 마스킹 실시 결과 — 외부 AI 전송 전/결과 출력 단계 마스킹 완료 알림
    audit = res.get("pii_audit") or []
    total_masked = sum(a.get("마스킹건수", 0) for a in audit)
    residual = sum(a.get("잔여", 0) for a in audit)
    inactive = any(a.get("상태") == "비활성" for a in audit)
    if inactive:
        st.warning("🔓 개인정보 마스킹이 **비활성**(ENABLE_PII_MASKING=0)입니다 — 마스킹 없이 처리됨.")
    elif residual:
        st.error(f"🔒 개인정보 마스킹 후에도 **잔여 {residual}건** 감지 — 사람 확인 필요.")
    else:
        st.success(f"🔒 개인정보 마스킹 실시 완료 — 외부 AI 전송 전·결과 출력 단계에서 "
                   f"총 **{total_masked}건** 마스킹, 잔여 0건.")
    if audit:
        with st.expander("🔎 개인정보 마스킹 검증 상세(단계별)"):
            st.caption("외부 AI(OpenAI)로는 마스킹·검증을 통과한 텍스트만 전달됩니다. "
                       "이미지·스캔 문서는 전송하지 않고 사람이 직접 확인합니다.")
            st.dataframe(audit, use_container_width=True, hide_index=True)

    # 불러오기 상태 — 텍스트 추출 실패/미분류/직접확인 대상 파일을 사람이 확인하도록 알림
    # scan(외부전송 보류)은 실패가 아니라 정책상 보류이므로 fail에서 제외하고 '직접확인'으로 안내
    fail = [d["file"] for d in res["doc_log"]
            if d.get("불러옴") == "X" and d.get("추출방식") != "scan"]
    uncls = [d["file"] for d in res["doc_log"] if d["유형"] == "미분류"]
    review = [(d["file"], d["직접확인"]) for d in res["doc_log"] if d.get("직접확인")]
    if fail:
        st.error("⚠ 텍스트를 불러오지 못한 파일 — **사람이 직접 확인 필요**:\n\n- " + "\n- ".join(fail))
    if review:
        st.warning("🖼 **이미지 기반 문서는 개인정보 포함 가능성이 있어 외부 AI로 전송하지 않고 보류했습니다 "
                   "— 사람이 먼저 직접 확인 필요**"
                   "(마스킹이 어려운 이미지·스캔 문서는 자동 판독하지 않습니다):\n\n- "
                   + "\n- ".join(f"{f} · {why}" for f, why in review))
    if uncls:
        st.warning("❓ 유형이 분류되지 않은 파일(확인 권장):\n\n- " + "\n- ".join(uncls))
    if not fail and not uncls and not review:
        st.caption("✅ 업로드한 모든 파일을 텍스트 레이어로 불러와 분류했습니다.")
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
