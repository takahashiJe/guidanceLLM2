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


def _value_from_ref(ref: Any, key: str, default: Any = None) -> Any:
    if isinstance(ref, dict):
        return ref.get(key, default)
    return getattr(ref, key, default)


def _find_md_by_spot_id(lang: str, spot_id: str) -> List[Dict]:
    """
    knowledge/{lang}/faci_spot/{spot_id}.md を探索。
    """
    base = _knowledge_base() / lang / "faci_spot"
    if not base.exists():
        return []

    target_file = base / f"{spot_id}.md"
    matches: List[Dict] = []
    if target_file.is_file():
        try:
            txt = target_file.read_text(encoding="utf-8")
            matches.append({"text": txt, "source": str(target_file)})
        except Exception as e:
            _log.warning(f"Failed to read {target_file}: {e}")
    return matches


def _load_md_by_spot_id(spot_id: str, lang: str) -> Optional[Dict[str, str]]:
    if not spot_id:
        return None

    docs = _find_md_by_spot_id(lang, spot_id)
    if not docs:
        return None

    doc = docs[0]
    text = doc.get("text")
    if not text:
        return None

    source = doc.get("source")
    base = _knowledge_base()
    if source:
        try:
            rel = Path(source).resolve().relative_to(base)
            source = str(rel)
        except Exception:
            source = str(source)
    else:
        source = f"{lang}/faci_spot/{spot_id}.md"

    return {"text": text, "source": source}


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
    spot_id に紐づくMDがあればそれを使い、なければ description を使う。
    """
    ctx: list[dict] = []

    # 1) spot_id を最優先で追加
    spot_id = _value_from_ref(spot_ref, "spot_id")
    if spot_id:
        md_doc = _load_md_by_spot_id(spot_id, lang)
        if md_doc:
            ctx.append(md_doc)

    # spot_id でドキュメントが見つからなかった場合、description を使う
    if not ctx:
        desc = _value_from_ref(spot_ref, "description")
        if desc:
            if isinstance(desc, (dict, list)):
                try:
                    desc_text = json.dumps(desc, ensure_ascii=False)
                except Exception:
                    desc_text = str(desc)
            else:
                desc_text = str(desc)
            if desc_text:
                ctx.append({"text": desc_text, "source": "spot.description"})

    return ctx
