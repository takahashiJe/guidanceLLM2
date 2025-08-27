from __future__ import annotations

import os
from pathlib import Path
from typing import List, Dict

# ChromaDB が使える場合に備える（無ければファイル走査のみ）
_CHROMA_AVAILABLE = True
try:
    import chromadb  # type: ignore
except Exception:
    _CHROMA_AVAILABLE = False


def _knowledge_dir() -> Path:
    # 例: /app/backend/worker/data/knowledge/ja
    return Path(os.getenv("KNOWLEDGE_DIR", "/app/backend/worker/data/knowledge"))


def _slug_candidates(spot_id: str) -> list[str]:
    s = (spot_id or "").strip().lower()
    cands = [s]
    if not s.startswith("spot_"):
        cands.append(f"spot_{s}")
    return cands


def _read_if_exists(p: Path) -> str | None:
    try:
        if p.exists() and p.is_file():
            return p.read_text(encoding="utf-8")
    except Exception:
        return None
    return None


def _fs_search(spot_id: str, lang: str, k: int = 4) -> List[Dict]:
    """
    簡易ファイルベース RAG：knowledge/{lang}/ 以下を走査。
    1) spots/spot_{spot_id}.md があれば最優先
    2) 他カテゴリも将来拡張可
    """
    base = _knowledge_dir() / lang
    out: List[Dict] = []

    # まずスポット個別
    spots = base / "spots"
    if spots.exists():
        for slug in _slug_candidates(spot_id):
            cand = spots / f"{slug}.md"
            txt = _read_if_exists(cand)
            if txt:
                out.append({"text": txt, "source": str(cand)})
                if len(out) >= k:
                    return out

    # 追加で一般カテゴリ（歴史・自然・マナー等）からも少し拾う（ライトに）
    for sub in ["history-and-culture", "nature", "rules-and-manners", "safety-and-preparation"]:
        d = base / sub
        if not d.exists():
            continue
        for md in d.glob("*.md"):
            txt = _read_if_exists(md)
            if txt:
                out.append({"text": txt, "source": str(md)})
                if len(out) >= k:
                    return out

    return out


def _chroma_search(spot_id: str, lang: str, k: int = 4) -> List[Dict]:
    """
    ChromaDB を利用した検索（collection 名は 'knowledge_{lang}' 想定）。
    無ければ空を返す。簡易に spot_id をクエリとして使う。
    """
    if not _CHROMA_AVAILABLE:
        return []

    url = os.getenv("CHROMA_URL")
    if not url:
        return []

    try:
        client = chromadb.HttpClient(host=url.split("://")[-1].split(":")[0],
                                     port=int(url.split(":")[-1]))
        coll_name = f"knowledge_{lang}"
        coll = client.get_or_create_collection(coll_name)
        res = coll.query(query_texts=[spot_id], n_results=k)
        docs = res.get("documents") or [[]]
        sources = res.get("metadatas") or [[]]
        out: List[Dict] = []
        for i, doc in enumerate(docs[0]):
            src = sources[0][i] if i < len(sources[0]) else {}
            out.append({"text": doc, "source": src.get("source") if isinstance(src, dict) else str(src)})
        return out
    except Exception:
        return []


def retrieve_context(spot_id: str, lang: str, k: int = 4) -> List[Dict]:
    """
    優先順位：
      1) ChromaDB（利用可能なら）
      2) ファイルシステム（knowledge/{lang}/...）
    """
    docs = _chroma_search(spot_id, lang, k=k)
    if docs:
        return docs
    return _fs_search(spot_id, lang, k=k)
