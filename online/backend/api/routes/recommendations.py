from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from online.backend.core.config import get_settings
from online.backend.engine.user_snapshot import UserSnapshot
from online.backend.engine.request_normalizer import RequestNormalizer
from online.backend.engine.recommender import RecommendationEngine
from online.backend.engine.orchestrator import handle_user_input

router = APIRouter()
settings = get_settings()

from online.backend.core.sessions import sessions

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

class VoiceSessionResponse(BaseModel):
    room_url: str
    token: str
    session_id: str

# --- Dependencies ---
async def get_db() -> AsyncIOMotorDatabase:
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    return client[settings.DATABASE_NAME]

def get_normalizer() -> RequestNormalizer:
    return RequestNormalizer()

# --- Endpoints ---
@router.post("/chat")
async def chat():
    """
    Unified Architecture: Chat is now handled exclusively through the Pipecat 
    Data Channel. Please connect via /voice/join to start a session.
    """
    raise HTTPException(
        status_code=400, 
        detail="The /chat endpoint is deprecated. Use the unified /voice/join connection."
    )

@router.post("/voice/join", response_model=VoiceSessionResponse)
async def join_voice_session(session_id: str):
    """
    Creates a Daily room for a voice session and returns connection details.
    """
    import os
    import aiohttp
    from pipecat.transports.services.helpers.daily_rest import (
        DailyRESTHelper, 
        DailyRoomParams, 
        DailyRoomProperties
    )
    
    daily_api_key = settings.DAILY_API_KEY
    if not daily_api_key:
        raise HTTPException(status_code=500, detail="DAILY_API_KEY not configured")

    async with aiohttp.ClientSession() as session:
        daily_helper = DailyRESTHelper(api_key=daily_api_key)
        try:
            room = await daily_helper.create_room(
                DailyRoomParams(
                    name=f"mf-{session_id}",
                    privacy="private",
                    properties=DailyRoomProperties(max_participants=2)
                )
            )
            token = await daily_helper.get_token(room.url)
            
            # Ensure the session snapshot exists
            if session_id not in sessions:
                sessions[session_id] = UserSnapshot()
                
            # Trigger the Local Voice Bot in the background (Non-Modal)
            try:
                import subprocess
                import sys
                
                # Get path to the pipeline script
                current_dir = os.path.dirname(os.path.abspath(__file__))
                pipeline_script = os.path.abspath(os.path.join(current_dir, "..", "..", "interaction", "pipecat_pipeline.py"))
                
                # Ensure we use the correct python interpreter
                subprocess.Popen([
                    sys.executable, 
                    pipeline_script, 
                    session_id, 
                    room.url, 
                    token
                ])
                print(f"Started local voice bot for session: {session_id}")
            except Exception as e:
                print(f"Failed to start local voice bot: {e}")

            return {
                "room_url": room.url,
                "token": token,
                "session_id": session_id
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to create voice room: {str(e)}")

        

@router.delete("/session/{session_id}")
async def reset_session(session_id: str):
    if session_id in sessions:
        del sessions[session_id]
    return {"status": "session reset"}
