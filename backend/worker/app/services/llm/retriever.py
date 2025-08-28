from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List, Optional

# ChromaDB は任意
_CHROMA_AVAILABLE = True
try:
    import chromadb  # type: ignore
except Exception:
    _CHROMA_AVAILABLE = False


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


def retrieve_context(spot_ref: Dict, lang: str, k: int = 4) -> List[Dict]:
    """
    優先順位:
      1) md_slug があれば knowledge/{lang}/**/{md_slug}.md を最優先
      2) （任意）Chroma → md_slug / spot_id / name の順でクエリ
      3) 見つからなければ []（＝ description のみで生成）
    """
    md_slug = _safe_slug(spot_ref.get("md_slug"))
    if md_slug:
        docs = _find_md_by_slug(lang, md_slug, max_files=k)
        if docs:
            return docs

    # Chroma フォールバック（任意）
    for q in [md_slug, spot_ref.get("spot_id"), spot_ref.get("name")]:
        if q:
            docs = _chroma_search(str(q), lang, n=k)
            if docs:
                return docs

    return []
