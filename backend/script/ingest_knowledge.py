# backend/script/ingest_knowledge.py
from __future__ import annotations
import os, re, json, time, hashlib
from pathlib import Path
from typing import List, Dict, Iterable, Tuple
import requests

CHROMA_URL = os.environ.get("CHROMA_URL", "http://chromadb:8000")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
KNOWLEDGE_DIR = os.environ.get("KNOWLEDGE_DIR", "/app/backend/worker/data/knowledge")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "mxbai-embed-large:latest")
COLL_PREFIX = os.environ.get("COLLECTION_PREFIX", "guidance_")
LANGS = os.environ.get("LANGS", "ja,en,zh").split(",")

# ---- REST helpers (Chroma) ----
def chroma_post(path: str, payload: Dict):
    r = requests.post(f"{CHROMA_URL}/api/v1{path}", json=payload, timeout=30)
    r.raise_for_status()
    return r.json()

def chroma_get(path: str):
    r = requests.get(f"{CHROMA_URL}/api/v1{path}", timeout=30)
    r.raise_for_status()
    return r.json()

def get_or_create_collection(name: str) -> str:
    # create will “get or create”
    data = chroma_post("/collections", {"name": name})
    return data["id"]

def get_collection_count(coll_id: str) -> int:
    # Chroma RESTにはcount専用がないので小さめクエリで件数概算 or get with include
    data = chroma_post(f"/collections/{coll_id}/get", {"limit": 1, "offset": 0})
    return int(data.get("total", 0))

def add_points(coll_id: str, ids: List[str], embeddings: List[List[float]], metadatas: List[Dict], documents: List[str]):
    payload = {
        "ids": ids,
        "embeddings": embeddings,
        "metadatas": metadatas,
        "documents": documents,
    }
    _ = chroma_post(f"/collections/{coll_id}/add", payload)

# ---- Embedding (Ollama REST) ----
def embed_texts(texts: List[str]) -> List[List[float]]:
    # バッチでなく1件ずつ（Ollama embeddingsは通常1件）
    embs = []
    for t in texts:
        r = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": t},
            timeout=60,
        )
        r.raise_for_status()
        embs.append(r.json()["embedding"])
    return embs

# ---- Chunking ----
def read_md(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")

def split_markdown(md: str, max_len: int = 800):
    # 大ざっぱ：見出し/空行で分割→長すぎる塊はmax_len毎に刻む
    parts = re.split(r"(?m)^\s*#.+$|\n\s*\n", md)
    chunks: List[str] = []
    for p in (x.strip() for x in parts if x and x.strip()):
        if len(p) <= max_len:
            chunks.append(p)
        else:
            for i in range(0, len(p), max_len):
                chunks.append(p[i:i+max_len])
    return [c for c in chunks if len(c) > 20]  # 短すぎる断片は捨てる

def iter_lang_files(lang: str) -> Iterable[Tuple[str, Path]]:
    base = Path(KNOWLEDGE_DIR) / lang
    for p in base.rglob("*.md"):
        rel = p.relative_to(base)
        yield (str(rel).replace("\\", "/"), p)

def make_doc_id(lang: str, relpath: str, idx: int, chunk: str) -> str:
    h = hashlib.sha1((relpath + str(idx) + str(len(chunk))).encode("utf-8")).hexdigest()[:10]
    return f"{lang}:{relpath}#{idx}:{h}"

def ingest_lang(lang: str):
    coll_name = f"{COLL_PREFIX}{lang}"
    coll_id = get_or_create_collection(coll_name)
    count = get_collection_count(coll_id)
    if count > 0:
        print(f"[ingest] skip {lang}: already has {count} docs")
        return

    print(f"[ingest] start {lang}")
    ids, docs, metas = [], [], []

    for rel, path in iter_lang_files(lang):
        md = read_md(path)
        if not md.strip():
            continue
        chunks = split_markdown(md)
        for i, ch in enumerate(chunks):
            ids.append(make_doc_id(lang, rel, i, ch))
            docs.append(ch)
            metas.append({"lang": lang, "source": rel})

            # メモリ節約で適宜フラッシュ（500件ごと）
            if len(ids) >= 500:
                embs = embed_texts(docs)
                add_points(coll_id, ids, embs, metas, docs)
                ids, docs, metas = [], [], []

    if ids:
        embs = embed_texts(docs)
        add_points(coll_id, ids, embs, metas, docs)

    print(f"[ingest] done {lang}")

def main():
    # ヘルスチェック待ち（chromadb/ollama）
    for _ in range(30):
        try:
            _ = chroma_get("/heartbeat")
            break
        except Exception:
            time.sleep(1)

    for lang in LANGS:
        ingest_lang(lang.strip())

if __name__ == "__main__":
    main()
