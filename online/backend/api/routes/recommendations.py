from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from online.backend.core.config import get_settings
from online.backend.engine.user_snapshot import UserSnapshot
from online.backend.engine.request_normalizer import RequestNormalizer
from online.backend.engine.recommender import RecommendationEngine
from online.backend.engine.orchestrator import handle_user_input

router = APIRouter()
settings = get_settings()

# --- In-memory Session Store (For Demo) ---
# In production, use Redis as defined in Settings
sessions = {}

# --- Pydantic Models ---
class UserInput(BaseModel):
    session_id: str
    text: str
    history: Optional[List[dict]] = None

class RecommendationResponse(BaseModel):
    type: str # 'question', 'recommendation', 'comparison_result', etc.
    text: Optional[str] = None
    question_intent: Optional[str] = None
    data: Optional[List[dict]] = None
    explanation: Optional[str] = None
    funds: Optional[List[dict]] = None
    message: Optional[str] = None
    horizon: Optional[int] = None

# --- Dependencies ---
async def get_db() -> AsyncIOMotorDatabase:
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    return client[settings.DATABASE_NAME]

def get_normalizer() -> RequestNormalizer:
    return RequestNormalizer()

# --- Endpoints ---
@router.post("/chat", response_model=RecommendationResponse)
async def chat(
    user_input: UserInput,
    db: AsyncIOMotorDatabase = Depends(get_db),
    normalizer: RequestNormalizer = Depends(get_normalizer)
):
    """
    Stateful endpoint for recommendation interaction.
    """
    session_id = user_input.session_id
    
    # Get or create snapshot for this session
    if session_id not in sessions:
        sessions[session_id] = UserSnapshot()
    
    snapshot = sessions[session_id]
    recommender = RecommendationEngine(db)
    
    try:
        response = await handle_user_input(
            text=user_input.text,
            snapshot=snapshot,
            normalizer=normalizer,
            recommender=recommender,
            history=user_input.history
        )
        
        # If recommendation complete, you might want to clear session or keep it for follow-ups
        # For now, we keep it so the user can ask for comparisons.
        
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/session/{session_id}")
async def reset_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
    return {"status": "session reset"}
