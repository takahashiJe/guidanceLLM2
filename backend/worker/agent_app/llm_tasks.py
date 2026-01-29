import os
from backend.worker.celery_app import celery_app
import ollama

# Ollamaクライアントの初期化
# URLは環境変数から取得
# 注: このクライアントは各ワーカでインスタンス化されるため、
# ワーカ毎に異なるOLLAMA_URL環境変数を設定することで、接続先を振り分け可能
ollama_client = ollama.Client(
    host=os.getenv("OLLAMA_URL", "http://ollama:11434")
)

# 各タスクで使用するモデル名を環境変数から取得
GENERATION_MODEL = os.getenv("OLLAMA_GENERATION_MODEL")
EMBEDDING_MODEL = os.getenv("OLLAMA_EMBEDDING_MODEL", "embeddinggemma:300m")

# --- テキスト生成タスク ---
@celery_app.task(name="llm_tasks.generate_text", queue="generation")
def generate_text(
    system_prompt: str,
    user_prompt: str,
    history: list = None,
    options: dict | None = None,
    response_format: str = "",
):
    """
    Ollamaにリクエストを送り、応答テキストを生成するCeleryタスク。
    'generation'キューにルーティングされる。
    """
    print("[DEBUG] generate_text called")
    if system_prompt:
        print(f"[DEBUG] system_prompt preview: {system_prompt[:200]}...")
    if history:
        print(f"[DEBUG] history length: {len(history)}")
    else:
        print("[DEBUG] history length: 0")
    if user_prompt:
        print(f"[DEBUG] user_prompt preview: {user_prompt[:200]}...")

    messages = []
    if system_prompt:
        messages.append({'role': 'system', 'content': system_prompt})
    
    if history:
        messages.extend(history)
    
    if user_prompt:
        messages.append({'role': 'user', 'content': user_prompt})

    try:
        print(f"Sending chat request to Ollama with model: {GENERATION_MODEL}")
        if options:
            print(f"[DEBUG] chat options: {options}")
        if response_format:
            print(f"[DEBUG] chat response_format: {response_format}")
        response = ollama_client.chat(
            model=GENERATION_MODEL,
            messages=messages,
            options=options,
            format=response_format or "",
        )
        return response['message']['content']
    except Exception as e:
        print(f"[ERROR] Ollama chat request failed: {e}")
        return "申し訳ありません、現在AIアシスタントでエラーが発生しています。"

# --- エンべディング生成タスク ---
@celery_app.task(name="llm_tasks.generate_embedding", queue="embedding")
def generate_embedding(text_to_embed: str):
    """
    Ollamaにリクエストを送り、テキストのエンべディング（ベクトル）を生成するCeleryタスク。
    'embedding'キューにルーティングされる。
    """
    try:
        print(f"Sending embedding request to Ollama with model: {EMBEDDING_MODEL}")
        result = ollama_client.embeddings(
            model=EMBEDDING_MODEL,
            prompt=text_to_embed
        )
        return result["embedding"]
    except Exception as e:
        print(f"[ERROR] Ollama embedding request failed: {e}")
        # エラー発生時はNoneを返すか、固定のベクトルを返すなどの対応が必要
        return None
