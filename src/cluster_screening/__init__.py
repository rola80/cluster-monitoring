"""창업·벤처 녹색융합클러스터 입주 신청서류 적합 검토기 패키지.

src 레이아웃이므로 코드는 src/cluster_screening/ 아래에 있고,
비밀·런타임 파일(.env, users.json)은 **프로젝트 루트**에 둔다(PROJECT_ROOT).
"""
from pathlib import Path


def _find_project_root(start: Path) -> Path:
    """start에서 위로 올라가며 pyproject.toml(없으면 .git)이 있는 폴더를 프로젝트 루트로 본다."""
    for p in (start, *start.parents):
        if (p / "pyproject.toml").exists() or (p / ".git").exists():
            return p
    return start.parent  # 최후 폴백


# .../src/cluster_screening/__init__.py → 루트(pyproject.toml 위치)
PROJECT_ROOT = _find_project_root(Path(__file__).resolve())
