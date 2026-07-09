"""CLI: 폴더/zip을 받아 판정하고 리포트를 저장.
사용법: python -m cluster_screening.cli <경로> [--name 기업명] [--apply YYYY-MM-DD] [--pw 비번] [--out 결과.xlsx]
"""
import argparse
from datetime import datetime

from . import pipeline
from .pipeline import masking, report, rules_engine


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--name", default="(미지정)")
    ap.add_argument("--apply", default=None)
    ap.add_argument("--pw", default="")
    ap.add_argument("--out", default="판정결과.xlsx")
    a = ap.parse_args()

    apply_d = datetime.strptime(a.apply, "%Y-%m-%d").date() if a.apply else None
    record, rules = pipeline.process_company(a.path, apply_date=apply_d, pw=a.pw,
                                             progress=lambda done, n, msg: print("  " + msg))
    try:
        judgment = rules_engine.evaluate(record, rules)
        judgment = masking.mask_judgment(judgment, record)   # PII 마스킹(출력용)
        audit = masking.get_audit()
        total_masked = sum(x.get("마스킹건수", 0) for x in audit)
        residual = sum(x.get("잔여", 0) for x in audit)
        print(f"\n[개인정보] 마스킹 실시 완료 — 총 {total_masked}건 마스킹, 잔여 {residual}건"
              + (" ⚠ 확인 필요" if residual else ""))

        print(f"\n=== {a.name} 종합판정: {judgment['overall']} "
              f"(가점 잠정 {judgment['bonus_total']}점) ===")
        for r in judgment["results"]:
            print(f"  [{r['status']:>4}] {r['id']} {r['name']}: {r['detail']}")
            if r["evidence"]:
                print(f"          근거: {r['evidence']}")
            if r.get("basis"):
                print(f"          근거조항: {r['basis']}")
        print("\n--- 성과 년도별 정리 (연도별 정밀수치는 사람 확인) ---")
        for p in judgment["performance"]:
            print(f"  [{p['상태']:>4}] {p['지표']}({p['단위']}): {p['집계값'] or '-'} · 근거={p['근거서류']}")
        review = [(d["file"], d["직접확인"]) for d in record["doc_log"] if d.get("직접확인")]
        if review:
            print("\n⚠ 이미지·스캔 문서는 외부 AI로 전송하지 않고 보류했습니다 — 사람이 직접 확인 필요:")
            for f, why in review:
                print(f"  - {f} · {why}")
        report.build_report(a.name, record, judgment, a.out)
        print(f"\n리포트 저장: {a.out}")
    finally:
        pipeline.cleanup(record)  # 추출된 구비서류 원문(PII) 임시폴더 삭제


if __name__ == "__main__":
    main()
