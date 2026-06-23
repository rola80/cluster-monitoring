"""CLI: 폴더/zip을 받아 판정하고 리포트를 저장.
사용법: python -m cluster_screening.cli <경로> [--name 기업명] [--apply YYYY-MM-DD] [--pw 비번] [--out 결과.xlsx]
"""
import argparse, os
from datetime import datetime
from . import pipeline
from .pipeline import rules_engine, report


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
                                             progress=lambda i, n, f: print(f"  [{i+1}/{n}] {f}"))
    judgment = rules_engine.evaluate(record, rules)

    print(f"\n=== {a.name} 종합판정: {judgment['overall']} "
          f"(가점 잠정 {judgment['bonus_total']}점) ===")
    for r in judgment["results"]:
        print(f"  [{r['status']:>4}] {r['id']} {r['name']}: {r['detail']}")
        if r["evidence"]:
            print(f"          근거: {r['evidence']}")
    report.build_report(a.name, record, judgment, a.out)
    print(f"\n리포트 저장: {a.out}")


if __name__ == "__main__":
    main()
