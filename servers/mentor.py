#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Multiturn Mentor RAG (no API server)
- mentors.yaml / mentor_router.py는 그대로 사용
- 대화형 콘솔 앱: 멘토 라우팅 -> 선택 -> Pinecone RAG로 멀티턴 답변
- Ollama(OpenAI 호환) /v1/embeddings, /v1/chat/completions 사용

명령:
  /mentor       : 멘토 다시 선택
  /quit         : 종료
"""

import os
import json
import readline  # noqa: F401  # 터미널 편의
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from openai import OpenAI
from pinecone import Pinecone
from sentence_transformers import SentenceTransformer

# ====== 환경설정 (필요한 값들) ======
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
LLM_API_KEY  = os.getenv("LLM_API_KEY", "ollama")
LLM_MODEL    = os.getenv("LLM_MODEL", "midm-2.0:base")
EMBED_MODEL  = os.getenv("EMBED_MODEL", "./models/multilingual-e5-small")
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS  = int(os.getenv("LLM_MAX_TOKENS", "2048"))


MENTOR_CFG_PATH = os.getenv("MENTOR_CFG", "config/mentors.yaml")

PINECONE_API_KEY     = os.getenv("PINECONE_API_KEY","pcsk_2MPBco_Nrhgf4NYgTHWCGEFZCVoD1vHxQEjnT16WNpQkJ2M4ZJiKbaDM1Ax58YpGtfnRkz")
PINECONE_INDEX_NAME  = os.getenv("PINECONE_INDEX_NAME","pdf-embeddings")
PINECONE_NAMESPACE   = os.getenv("PINECONE_NAMESPACE", "mainv2") or None
PINECONE_TOP_K       = int(os.getenv("PINECONE_TOP_K", "5"))

if not PINECONE_API_KEY or not PINECONE_INDEX_NAME:
    raise RuntimeError("환경변수 PINECONE_API_KEY / PINECONE_INDEX_NAME를 설정하세요.")

import unicodedata
import re

def norm_korean(s: str) -> str:
    # 1) 유니코드 NFC(완성형)로 정규화  ← 핵심!
    s = unicodedata.normalize("NFC", s or "")
    # 2) 구두점 통일 (가운뎃점/옛가운뎃점 -> 마침표)
    s = s.replace("·", ".").replace("ㆍ", ".")
    # 3) 공백 제거 (원하면 유지)
    s = re.sub(r"\s+", "", s)
    return s

# ====== mentor_router.py 그대로 사용 ======
from mentor_router import load_mentors, MentorRouter  # 변경 금지

# ====== 의존 객체 ======
oai = OpenAI(base_url=LLM_BASE_URL, api_key=LLM_API_KEY)
pc = Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

# ====== 멘토 로딩 및 라우터 준비 ======
MENTORS = load_mentors(MENTOR_CFG_PATH)
MENTOR_BY_NAME = {m.name: m for m in MENTORS}
ROUTER = MentorRouter(MENTORS)  # mentor_router.py 내부 임베딩 로직 그대로 활용

# ====== 유틸 함수 ======
_local_embedder = SentenceTransformer(EMBED_MODEL)

def embed(text: str) -> list[float]:
    """로컬 e5-small 모델 임베딩"""
    vec = _local_embedder.encode(["query: " + text], normalize_embeddings=True)
    return vec[0].astype("float32").tolist()

def pinecone_query(question: str, mentor_name: str, top_k: int) -> List[Dict[str, Any]]:
    v = embed(question)
    res = index.query(
        vector=v,
        top_k=top_k,
        include_metadata=True,
        namespace=PINECONE_NAMESPACE,
    )
    matches = getattr(res, "matches", []) or res.get("matches", [])
    out: List[Dict[str, Any]] = []
    mentor_prefix = mentor_name[:2]
    filtered = []
    for m in matches:
        md = getattr(m, "metadata", None) or m.get("metadata", {}) or {}
        folder_val = (md.get("folder") or md.get("subdir") or "").strip()
       
        if norm_korean(folder_val)[:2] == norm_korean(mentor_prefix):
            filtered.append({
                "id": getattr(m, "id", None) or m.get("id"),
                "score": float(getattr(m, "score", 0.0) or m.get("score", 0.0)),
                "text": md.get("text") or md.get("content") or md.get("preview") or "",
                "metadata": md,
            })
    filtered.sort(key=lambda x: x["score"], reverse=True)
    return filtered[:top_k]
"""
def format_contexts(ctxs: List[Dict[str, Any]], max_chars: int = 4500) -> str:
    parts, total = [], 0
    for i, c in enumerate(ctxs, 1):
        body = (c.get("text") or "").strip()
        if not body:
            continue
        src = (c.get("metadata") or {}).get("source")
        head = f"[{i}] score={c['score']:.3f}" + (f" source={src}" if src else "")
        block = (head + "\n" + body).strip()
        if total + len(block) > max_chars:
            break
        parts.append(block)
        total += len(block)
    return "\n\n".join(parts) if parts else "(검색 결과 없음)"
"""

def format_contexts(ctxs: List[Dict[str, Any]], max_chars: int = 4500) -> str:
    parts, total = [], 0
    for i, c in enumerate(ctxs, 1):
        md = c.get("metadata") or {}
        # preview만 사용, 어떤 타입이든 안전하게 str 변환
        body = str(md.get("preview", "")).strip()
        if not body:
            continue

        # 출처 표시는 file_path(없으면 source)
        src = md.get("file_path") or md.get("source")
        head = f"[{i}] score={float(c.get('score', 0.0)):.3f}" + (f" source={src}" if src else "")

        block = (head + "\n" + body).strip()
        if total + len(block) > max_chars:
            remain = max_chars - total
            if remain <= 0:
                break
            block = block[:remain]

        parts.append(block)
        total += len(block)

    return "\n\n".join(parts) if parts else "(검색 결과 없음)"

def chat_complete(system_prompt: str, user_prompt: str, history_msgs: List[Dict[str, str]]) -> str:
    """대화형: 기존 히스토리와 함께 생성 호출 (간단 버전)"""
    messages = [{"role": "system", "content": system_prompt}]
    messages += history_msgs  # 과거 user/assistant 교대로 저장된 형식이라고 가정
    messages.append({"role": "user", "content": user_prompt})
    resp = oai.chat.completions.create(
        model=LLM_MODEL,
        temperature=LLM_TEMPERATURE,
        max_tokens=LLM_MAX_TOKENS,
        messages=messages,
    )
    return resp.choices[0].message.content

# ====== 세션 ======
@dataclass
class Session:
    mentor_name: Optional[str] = None
    history: List[Dict[str, str]] = field(default_factory=list)

    def pick_mentor(self, first_question: str) -> str:
        """mentor_router로 top-3 추천 후 선택"""
        print("\n[멘토 추천] 질문을 바탕으로 적합한 멘토 Top-3를 찾는 중...\n")
        ranked = ROUTER.rank(first_question, top_k=3)
        for i, r in enumerate(ranked, 1):
            print(f"{i}. {r['name']}  (score {r['score']:.3f})  — {r['reason']}")
        while True:
            sel = input("\n번호를 선택하세요 (1-3): ").strip()
            if sel in {"1", "2", "3"}:
                idx = int(sel) - 1
                name = ranked[idx]["name"]
                if name not in MENTOR_BY_NAME:
                    print("알 수 없는 멘토명입니다. 다시 선택하세요.")
                    continue
                self.mentor_name = name
                print(f"선택된 멘토: {self.mentor_name}")
                return self.mentor_name
            else:
                print("1~3 중 선택해주세요.")

    def turn(self, user_text: str, top_k: int = PINECONE_TOP_K) -> str:
        
        assert self.mentor_name, "멘토가 선택되지 않았습니다."
        mentor = MENTOR_BY_NAME[self.mentor_name]
        # 1) 검색
        ctxs = pinecone_query(user_text, self.mentor_name, top_k=top_k)
        ctx_str = format_contexts(ctxs)

        # 2) 프롬프트 구성
        sys_prompt = (
            f"{mentor.system_prompt}\n\n"
            "아래 '검색 컨텍스트'를 우선적으로 참고해 답하세요.\n"
            "- 근거가 되는 항목 번호[ ]를 인라인로 표시 (예: [1], [2])\n"
            "- 컨텍스트에 없는 내용은 추측하지 말고 모른다고 답하거나 추가 정보 요청\n"
        )
        user_prompt = (
            f"질문:\n{user_text}\n\n"
            f"--- 검색 컨텍스트 (subject_type={self.mentor_name}) ---\n{ctx_str}\n"
        )

        # 3) 생성
        answer = chat_complete(sys_prompt, user_prompt, self.history)

        # 4) 히스토리
        self.history.append({"role": "user", "content": f"[{self.mentor_name}] {user_text}"})
        self.history.append({"role": "assistant", "content": answer})

        # 5) 화면 표시
        print("\n-----[답변]-----")
        print(answer)
        print("----------------\n")
        return answer

# ====== 메인 루프 ======
def main():
    print("=== Multiturn Mentor RAG (mentors.yaml & mentor_router.py 그대로 사용) ===")
    print("명령: /mentor (멘토 재선택), /quit (종료)\n")

    sess = Session()

    # 첫 질문 → 멘토 라우팅/선택
    first = input("첫 질문을 입력하세요: ").strip()
    while not first:
        first = input("첫 질문을 입력하세요: ").strip()

    sess.pick_mentor(first)
    sess.turn(first)

    # 멀티턴 루프
    while True:
        txt = input("> ").strip()
        if not txt:
            continue
        if txt.lower() in ("/quit", "quit", "exit"):
            print("종료합니다.")
            break
        if txt.lower().startswith("/mentor"):
            # 멘토 재선택: 최근 사용자 메시지를 힌트로 사용하거나 새 입력 유도
            seed = input("멘토 추천을 위한 질문(빈칸이면 직전 질문 사용): ").strip()
            seed = seed or first
            sess.pick_mentor(seed)
            continue

        sess.turn(txt)

if __name__ == "__main__":
    main()
