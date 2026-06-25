"""Streamlit 런처.

Streamlit과 chromadb가 모두 protobuf를 쓰는데, chromadb 번들 OpenTelemetry proto가
protobuf 5.x C++ 구현과 충돌한다. 회피하려면 **streamlit(=protobuf) import 전에**
순수-파이썬 구현을 강제해야 하므로 별도 런처를 둔다.
실행:  uv run cluster-app
"""
import os

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")


def main():
    import sys
    from pathlib import Path

    from streamlit.web import cli as stcli

    app_path = str(Path(__file__).with_name("app.py"))
    sys.argv = ["streamlit", "run", app_path, "--server.headless", "true"]
    raise SystemExit(stcli.main())
