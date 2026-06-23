"""(A) 근거 문서 RAG 브랜치.

공고·운영규정·관리지침 PDF를 인덱싱해 "이 판정의 근거 조항이 무엇인가"를 검색한다.
흐름: ingestion(적재) → chunking(청킹+metadata) → index(임베딩·Chroma) → retriever(근거 검색).
임베딩은 오프라인(sentence-transformers), 벡터스토어는 Chroma(로컬 영속).
"""
import os

# chromadb 번들 OpenTelemetry proto가 protobuf 5.x C++ 구현과 충돌 → 순수 파이썬 파서 사용.
# (텔레메트리는 어차피 끄므로 성능 영향 없음. chromadb import 전에 설정되어야 함.)
os.environ.setdefault("PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION", "python")
