from __future__ import annotations
import datetime
from fastapi import APIRouter, HTTPException, status

from backend.api.schemas import (
    UserCreateRequest,
    UserLoginRequest,
    UserResponse,
    UserSessionResponse, # Import new schema
    HistoryMessage,      # Import new schema
)
from backend.worker.agent_app.db_client import SessionLocal, get_conversation_history
from backend.worker.app_db_models import User, LanguageEnum

router = APIRouter(prefix="/v1", tags=["Users"])


def _serialize_user(user: User) -> UserResponse:
    language_value = getattr(user.language, "value", "ja")
    return UserResponse(user_name=user.user_name, language=language_value)  # type: ignore[arg-type]


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreateRequest) -> UserResponse:
    with SessionLocal() as db:
        existing = (
            db.query(User)
            .filter(User.user_name == payload.user_name)
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="user_name already exists.",
            )

        language_value = payload.language
        try:
            language_enum = LanguageEnum(language_value)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported language: {language_value}",
            ) from exc

        user = User(user_name=payload.user_name, language=language_enum)
        db.add(user)
        db.commit()
        db.refresh(user)
        return _serialize_user(user)


@router.post("/login", response_model=UserResponse, status_code=status.HTTP_200_OK)
def login_user(payload: UserLoginRequest) -> UserResponse:
    with SessionLocal() as db:
        user = (
            db.query(User)
            .filter(User.user_name == payload.user_name)
            .first()
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
        return _serialize_user(user)


@router.get("/users/{user_name}/session", response_model=UserSessionResponse, status_code=status.HTTP_200_OK)
def get_user_session(user_name: str) -> UserSessionResponse:
    """Fetches the latest session data (chat history and itinerary) for a user."""
    with SessionLocal() as db:
        user = (
            db.query(User)
            .filter(User.user_name == user_name)
            .first()
        )
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )
        
        # Fetch conversation history
        history_from_db = get_conversation_history(db, user.id, limit=50) # Get last 50 messages
        chat_history = [
            HistoryMessage(
                role=msg.role,
                content=msg.content,
                timestamp=msg.timestamp
            )
            for msg in reversed(history_from_db) # Reverse to get chronological order
        ]

        # Get itinerary
        itinerary = user.current_itinerary or []

        return UserSessionResponse(chat_history=chat_history, itinerary=itinerary)