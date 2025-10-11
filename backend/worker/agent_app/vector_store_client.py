import os
import chromadb
from chromadb.utils import embedding_functions

# agent_app内のCeleryタスクをインポート
from .llm_tasks import generate_embedding

# ChromaDBクライアントの初期化
# Dockerコンテナから見たChromaDBのURLを環境変数から取得
CHROMA_HOST = os.getenv("CHROMA_URL", "http://chromadb:8000").split("://")[1].split(":")[0]
CHROMA_PORT = os.getenv("CHROMA_URL", "http://chromadb:8000").split(":")[-1]

chroma_client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)


class NoopEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """ChromaDBに渡すためのダミー埋め込み関数。実際の埋め込みはCelery側で生成する。"""

    def __call__(self, texts):
        print("[Vector Store] NO-OP embedder called, but vector generation is handled by Celery.")
        if isinstance(texts, str):
            texts = [texts]
        return [[0.0] * 384 for _ in texts]


noop_embedding_function = NoopEmbeddingFunction()

# 会話履歴を保存するためのコレクション（テーブルのようなもの）を取得または作成
collection = chroma_client.get_or_create_collection(
    name="conversation_history",
    embedding_function=noop_embedding_function # ダミーの関数を渡す
)

def add_conversation(conversation_id: str, text: str):
    """
    会話のテキストをベクトル化し、ベクトルストアに保存する。

    Args:
        conversation_id (str): 保存する会話の一意なID。
        text (str): 会話のテキスト内容。
    """
    print(f"[Vector Store] Adding conversation {conversation_id}...")
    # 1. Celeryタスクを呼び出してテキストをベクトル化
    #    これにより、エンべディング処理は'embedding'キューに送られる
    task = generate_embedding.delay(text)
    embedding_vector = task.get(timeout=120) # タイムアウトを設定

    if embedding_vector is None:
        print(f"[ERROR] Failed to generate embedding for conversation {conversation_id}. Skipping add.")
        return

    # 2. ベクトル、ID、メタデータ（元のテキスト）をChromaDBに保存
    try:
        collection.add(
            ids=[conversation_id],
            embeddings=[embedding_vector],
            documents=[text] # 元のテキストも保存しておく
        )
        print(f"[Vector Store] Successfully added conversation {conversation_id}.")
    except Exception as e:
        # ChromaDBへの追加に失敗した場合（例：ユニークIDの重複など）
        print(f"[ERROR] Failed to add conversation {conversation_id} to ChromaDB: {e}")

def search_similar_conversations(query_text: str, n_results: int = 2) -> list:
    """
    クエリテキストに類似した過去の会話を検索する。

    Args:
        query_text (str): 類似検索のクエリとなる現在のユーザー発話。
        n_results (int): 取得する結果の数。

    Returns:
        list: 類似した会話のテキストのリスト。
    """
    print(f"[Vector Store] Searching for conversations similar to: '{query_text[:30]}...'")
    # 1. クエリテキストをベクトル化
    task = generate_embedding.delay(query_text)
    query_vector = task.get(timeout=60)

    if query_vector is None:
        print("[ERROR] Failed to generate embedding for query. Returning empty list.")
        return []

    # 2. ChromaDBにクエリを投げて類似ベクトルを検索
    results = collection.query(
        query_embeddings=[query_vector],
        n_results=n_results
    )
    
    # 検索結果からドキュメント（元のテキスト）を抽出して返す
    similar_docs = results.get('documents', [[]])[0]
    print(f"[Vector Store] Found {len(similar_docs)} similar conversations.")
    return similar_docs
