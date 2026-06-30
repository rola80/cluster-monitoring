"""인터프리터 시작 시 site 모듈이 자동 import(=모든 import보다 먼저 실행).

chromadb 번들 OpenTelemetry proto가 protobuf 5.x C++ 구현과 충돌하므로, protobuf가
로드되기 전에 순수-파이썬 구현을 강제한다. 이렇게 하면 `streamlit run`·`cluster-app`·
`pytest` 등 어떤 방식으로 띄워도 인덱싱(Chroma)이 protobuf 오류 없이 동작한다.
(src가 sys.path에 있어 이 파일이 sitecustomize로 인식됨)
"""
import os

os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
