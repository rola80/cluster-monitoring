"""pipeline: 임시 작업 디렉터리(PII) 정리."""
import os
import tempfile
from cluster_screening import pipeline


def test_cleanup_removes_workdir():
    d = tempfile.mkdtemp(prefix="cluster_test_")
    assert os.path.isdir(d)
    pipeline.cleanup({"_workdir": d})
    assert not os.path.isdir(d)


def test_cleanup_safe_when_missing():
    pipeline.cleanup({})        # _workdir 없음 → 무동작
    pipeline.cleanup(None)      # None → 무동작
    pipeline.cleanup({"_workdir": "C:/nonexistent/xyz123"})  # 없는 경로 → 무동작
