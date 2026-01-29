from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Literal

# agent.pyで定義したLangGraphアプリケーションをインポート
from .agent import app as agent_app

# FastAPIアプリケーションをインスタンス化
app = FastAPI(
    title="AI Agent Service",
    description="Handles conversational AI logic using a LangGraph agent.",
)

# APIの入力データモデルを定義
class ChatRequest(BaseModel):
    user_name: str
    user_input: str
    thread_id: str

class ChatResponse(BaseModel):
    response_text: str
    itinerary: List[str] = Field(default_factory=list)
    thread_id: str
    language: Literal["ja", "en", "zh"]

@app.post("/invoke", response_model=ChatResponse)
def invoke_agent(request: ChatRequest) -> ChatResponse:
    """
    AIエージェントのLangGraphを呼び出し、最終的な応答を返すエンドポイント。
    """
    print(f"Invoking agent for thread_id: {request.thread_id}")

    # LangGraphに渡す初期状態と設定を構築
    initial_state = {
        "user_name": request.user_name,
        "user_input": request.user_input,
    }
    config = {"configurable": {"thread_id": request.thread_id}}

    # LangGraphの処理を同期的に実行し、最終結果を取得
    # .stream()は非同期のストリーミング用、.invoke()は最終結果の同期取得用
    final_state = agent_app.invoke(initial_state, config)

    # フロントエンドに必要な情報を抽出して返す
    language = final_state.get("language")
    response: Dict[str, Any] = {
        "response_text": final_state.get("response_text"),
        "itinerary": final_state.get("itinerary", []),
        "thread_id": request.thread_id,
        "language": language
    }
    
    return ChatResponse(**response)
