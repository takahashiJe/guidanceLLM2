from __future__ import annotations

import os
from pathlib import Path
import json
import logging
import requests
from typing import List, Dict, Any, Optional

# ChromaDB は任意
_CHROMA_AVAILABLE = True
try:
    import chromadb  # type: ignore
except Exception:
    _CHROMA_AVAILABLE = False

# === RAG(Chroma/Ollama) settings ===
CHROMA_URL = os.environ.get("CHROMA_URL", "http://chromadb:8000")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "mxbai-embed-large:latest")
COLLECTION_PREFIX = os.environ.get("COLLECTION_PREFIX", "guidance_")

_log = logging.getLogger(__name__)

def _embed_query(text: str) -> Optional[List[float]]:
    try:
        r = requests.post(
            f"{OLLAMA_URL}/api/embeddings",
            json={"model": EMBED_MODEL, "prompt": text},
            timeout=30,
        )
        r.raise_for_status()
        return r.json().get("embedding")
    except Exception as e:
        _log.warning("embed failed: %s", e)
        return None

def _chroma_get_collection_id(name: str) -> Optional[str]:
    try:
        r = requests.get(f"{CHROMA_URL}/api/v1/collections", timeout=10)
        r.raise_for_status()
        for c in r.json():
            if c.get("name") == name:
                return c.get("id")
    except Exception as e:
        _log.info("chroma collections not reachable: %s", e)
    return None

def _chroma_query(coll_id: str, embedding: List[float], k: int = 6) -> List[Dict[str, Any]]:
    """
    Chroma REST /query 互換: /collections/{id}/query
    include: ["documents","metadatas","distances"]
    """
    try:
        payload = {
            "query_embeddings": [embedding],
            "n_results": k,
            "include": ["documents", "metadatas", "distances"],
        }
        r = requests.post(f"{CHROMA_URL}/api/v1/collections/{coll_id}/query", json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        # 返却を ctx 形式に合うよう整形
        docs = (data.get("documents") or [[]])[0]
        metas = (data.get("metadatas") or [[]])[0]
        dists = (data.get("distances") or [[]])[0]
        out = []
        for doc, meta, dist in zip(docs, metas, dists):
            out.append({
                "text": doc,
                "source": (meta or {}).get("source", "chroma"),
                "score": float(1.0 / (1.0 + float(dist))) if dist is not None else None,
            })
        return out
    except Exception as e:
        _log.info("chroma query skipped: %s", e)
        return []

def _knowledge_base() -> Path:
    # 例: backend/worker/data/knowledge
    return Path(os.getenv("KNOWLEDGE_DIR", "backend/worker/data/knowledge")).resolve()


def _safe_slug(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    # ファイル名安全化
    s2 = "".join(ch for ch in s if ch.isalnum() or ch in ("-", "_"))
    return s2 or None


def _find_md_by_slug(lang: str, md_slug: str, max_files: int = 1) -> List[Dict]:
    """
    knowledge/{lang}/**/{md_slug}.md を最優先で探索（再帰）。
    """
    base = _knowledge_base() / lang
    if not base.exists():
        return []
    matches: List[Dict] = []
    for p in base.rglob(f"{md_slug}.md"):
        try:
            txt = p.read_text(encoding="utf-8")
        except Exception:
            continue
        matches.append({"text": txt, "source": str(p)})
        if len(matches) >= max_files:
            break
    return matches


def _chroma_search(q: str, lang: str, n: int = 4) -> List[Dict]:
    if not (_CHROMA_AVAILABLE and os.getenv("CHROMA_URL")):
        return []
    try:
        url = os.getenv("CHROMA_URL")
        host = url.split("://")[-1].split(":")[0]
        port = int(url.split(":")[-1])
        client = chromadb.HttpClient(host=host, port=port)
        coll = client.get_or_create_collection(f"knowledge_{lang}")
        res = coll.query(query_texts=[q], n_results=n)
        docs = res.get("documents") or [[]]
        metas = res.get("metadatas") or [[]]
        out: List[Dict] = []
        for i, doc in enumerate(docs[0]):
            meta = metas[0][i] if i < len(metas[0]) else {}
            out.append({"text": doc, "source": (meta.get("source") if isinstance(meta, dict) else str(meta))})
        return out
    except Exception:
        return []


def retrieve_context(spot_ref, lang: str) -> list[dict]:
    """
    md_slug と description をまず入れる。
    Chroma にインデックスがあれば、クエリに基づく関連チャンクを少量追加。
    """
    ctx: list[dict] = []

    # 1) md_slug を最優先で追加
    md_slug = getattr(spot_ref, "md_slug", None)
    if md_slug:
        md_text = _load_md_by_slug(md_slug, lang)
        if md_text:
            ctx.append({"text": md_text, "source": f"{lang}/spots/{md_slug}.md"})

    # 2) Spot.description も追加
    desc = getattr(spot_ref, "description", None)
    if desc:
        ctx.append({"text": desc, "source": "spot.description"})

    # 3) 追加RAG: Chroma が使える場合だけ関連章節を付与（安全に無視可）
    #    クエリは name+description を素朴に連結
    name = getattr(spot_ref, "name", "") or ""
    query = f"{name} {desc or ''}".strip()
    if query:
        coll_name = f"{COLLECTION_PREFIX}{lang}"
        coll_id = _chroma_get_collection_id(coll_name)
        if coll_id:
            emb = _embed_query(query)
            if emb:
                extras = _chroma_query(coll_id, emb, k=6)
                # 重複ソースを軽く抑制（同一sourceは最初だけ）
                seen = set(s.get("source") for s in ctx)
                for e in extras:
                    src = e.get("source")
                    if src in seen:
                        continue
                    seen.add(src)
                    ctx.append({"text": e.get("text", ""), "source": src})

    return ctx
