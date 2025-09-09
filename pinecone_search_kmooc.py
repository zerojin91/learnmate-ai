#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import uvicorn
from typing import Any, Dict, List, Optional, Union

from fastapi import FastAPI, Query, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

import numpy as np
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone

# ========= 환경 변수 =========
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX   = os.getenv("PINECONE_INDEX", "kmooc-e5-384")
DEFAULT_NS       = os.getenv("DEFAULT_NAMESPACE", "engineering_structure")
DEVICE           = os.getenv("DEVICE", "cpu")

# (선택) Reranker 활성화: 1로 설정하면 사용
USE_RERANKER     = os.getenv("USE_RERANKER", "0") == "1"
RERANKER_MODEL   = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")
RERANK_CANDIDATES= int(os.getenv("RERANK_CANDIDATES", "50"))

if not PINECONE_API_KEY:
    raise RuntimeError("환경변수 PINECONE_API_KEY가 필요합니다.")

# ========= 모델 로드 =========
E5_MODEL_NAME = "intfloat/multilingual-e5-small"
_embedder = SentenceTransformer(E5_MODEL_NAME, device=DEVICE)

_reranker = None
if USE_RERANKER:
    try:
        from sentence_transformers import CrossEncoder
        _reranker = CrossEncoder(RERANKER_MODEL, device=DEVICE)  # 다국어 지원
    except Exception as e:
        print(f"[경고] Reranker 로드 실패: {e}. USE_RERANKER=0으로 계속 진행합니다.")
        _reranker = None
        USE_RERANKER = False

# ========= Pinecone =========
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX)

# ========= FastAPI =========
app = FastAPI(title="Semantic Search API (Pinecone + e5)",
              version="1.0.0",
              description="multilingual-e5-small로 쿼리 임베딩 후 Pinecone에서 검색")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 필요 시 좁혀주세요
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ========= 스키마 =========
class SearchRequest(BaseModel):
    query: str = Field(..., description="사용자 쿼리(자연어)")
    top_k: int = Field(10, ge=1, le=100, description="검색 결과 수")
    namespace: Optional[str] = Field(None, description="Pinecone 네임스페이스")
    filter: Optional[Dict[str, Any]] = Field(
        None,
        description="Pinecone metadata filter (예: {'subject_area': {'$eq':'Architecture'}})"
    )
    include_metadata: bool = Field(True, description="메타데이터 포함")
    include_values: bool = Field(False, description="벡터 값 포함 여부(디버그 용)")
    rerank: bool = Field(False, description="Reranker 사용 여부(USE_RERANKER=1일 때만 동작)")
    rerank_candidates: int = Field(None, description="Rerank 후보 개수(기본 env RERANK_CANDIDATES)")

class SearchResponseItem(BaseModel):
    id: str
    score: float
    metadata: Optional[Dict[str, Any]] = None

class SearchResponse(BaseModel):
    namespace: str
    count: int
    results: List[SearchResponseItem]

# ========= 유틸 =========
def sanitize_namespace(ns: Optional[str]) -> str:
    ns = ns or DEFAULT_NS or "default"
    return (
        ns.replace("/", "_")
          .replace("·", "_")
          .replace(" ", "_")
          .replace("(", "")
          .replace(")", "")
    )

def encode_query(text: str) -> np.ndarray:
    # e5 규칙: "query: " 접두
    vec = _embedder.encode(["query: " + text], normalize_embeddings=True)
    return vec[0].astype("float32")

def do_rerank(query: str, matches: List[Dict[str, Any]], top_k: int, candidates: int) -> List[Dict[str, Any]]:
    # CrossEncoder 점수로 재정렬 (텍스트는 요약 필드 우선, 없으면 title/url/원문 일부)
    if not _reranker:
        return matches

    pairs = []
    texts = []
    for m in matches[:candidates]:
        md = m.get("metadata", {}) or {}
        summary = md.get("summary_800t") or md.get("summary") or ""
        fallback = (md.get("title") or md.get("url") or "")
        content = summary if summary else fallback
        # content가 빈 경우 메타 전체를 문자열로
        if not content:
            content = " ".join(f"{k}:{v}" for k, v in md.items() if isinstance(v, str))[:500]
        pairs.append([query, content])
        texts.append(content)

    scores = _reranker.predict(pairs).tolist()
    rescored = []
    for m, s in zip(matches[:candidates], scores):
        mm = dict(m)
        mm["rerank_score"] = float(s)
        rescored.append(mm)
    rescored.sort(key=lambda x: x["rerank_score"], reverse=True)
    return rescored[:top_k]

# ========= 엔드포인트 =========
@app.get("/health")
def health():
    return {"status": "ok", "index": PINECONE_INDEX, "namespace_default": DEFAULT_NS, "reranker": bool(_reranker)}

@app.post("/search", response_model=SearchResponse)
def search(req: SearchRequest = Body(...)):
    if not req.query or not req.query.strip():
        raise HTTPException(status_code=400, detail="query가 비어있습니다.")

    ns = sanitize_namespace(req.namespace)
    vec = encode_query(req.query)

    # Pinecone query
    try:
        q = index.query(
            vector=vec.tolist(),
            top_k=max(req.top_k, RERANK_CANDIDATES if (req.rerank and _reranker) else req.top_k),
            namespace=ns,
            include_metadata=req.include_metadata,
            include_values=req.include_values,
            filter=req.filter,  # 예: {"subject_area": {"$eq": "Architecture"}}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pinecone query 실패: {type(e).__name__}: {e}")

    matches = q.get("matches", []) or []

    # (선택) Rerank
    if req.rerank and _reranker:
        candidates = req.rerank_candidates or RERANK_CANDIDATES
        matches = do_rerank(req.query, matches, req.top_k, candidates)
    else:
        # Pinecone 점수 기준 상위 top_k
        matches = matches[:req.top_k]

    results: List[SearchResponseItem] = []
    for m in matches:
        results.append(SearchResponseItem(
            id=m.get("id"),
            score=float(m.get("score", 0.0)),
            metadata=m.get("metadata") if req.include_metadata else None
        ))

    return SearchResponse(namespace=ns, count=len(results), results=results)

if __name__ == "__main__":
    # uvicorn 실행 (개발용)
    uvicorn.run("pinecone_search_kmooc:app", host="0.0.0.0", port=8099, reload=False)
