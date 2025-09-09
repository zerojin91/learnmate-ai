from __future__ import annotations
import os
import yaml
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any
from openai import OpenAI

# ---- 환경변수 (Ollama OpenAI 호환) ----
BASE_URL = os.getenv("LLM_BASE_URL", "http://localhost:11434/v1")
API_KEY  = os.getenv("LLM_API_KEY", "ollama")
EMBED_MODEL = os.getenv("EMBED_MODEL", "midm-2.0:base")  # `ollama pull nomic-embed-text` 필요

client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

@dataclass
class Mentor:
    name: str
    description: str
    keywords: List[str]
    system_prompt: str

def load_mentors(yaml_path: str) -> List[Mentor]:
    with open(yaml_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    ms = []
    for m in cfg["mentors"]:
        ms.append(Mentor(
            name=m["name"],
            description=m["description"],
            keywords=m.get("keywords", []),
            system_prompt=m.get("system_prompt", "")
        ))
    return ms

def _embed(texts: List[str]) -> np.ndarray:
    # OpenAI 호환 /v1/embeddings
    vecs = []
    for t in texts:
        r = client.embeddings.create(model=EMBED_MODEL, input=t)
        v = np.array(r.data[0].embedding, dtype=np.float32)
        # 정규화(코사인 유사도 계산 용이)
        v = v / (np.linalg.norm(v) + 1e-9)
        vecs.append(v)
    return np.vstack(vecs)

class MentorRouter:
    def __init__(self, mentors: List[Mentor]):
        self.mentors = mentors
        profiles = [
            f"{m.description}\nkeywords: {', '.join(m.keywords)}"
            for m in mentors
        ]
        self.M = _embed(profiles)  # (N, d)

    def rank(self, question: str, top_k: int = 3) -> List[Dict[str, Any]]:
        q = _embed([question])  # (1, d)
        sims = (q @ self.M.T).ravel()  # 코사인(정규화 가정)
        order = np.argsort(-sims)[:top_k]
        out = []
        for i in order:
            m = self.mentors[i]
            out.append({
                "name": m.name,
                "score": float(sims[i]),
                "system_prompt": m.system_prompt,
                "reason": f"질문과 '{m.name}' 프로필의 의미 유사도 {sims[i]:.3f}"
            })
        return out

if __name__ == "__main__":
    import json, argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--mentors", default="config/mentors.yaml")
    ap.add_argument("--q", required=True)
    ap.add_argument("--k", type=int, default=3)
    args = ap.parse_args()

    ms = load_mentors(args.mentors)
    router = MentorRouter(ms)
    print(json.dumps(router.rank(args.q, args.k), ensure_ascii=False, indent=2))
