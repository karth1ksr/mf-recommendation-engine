import os
import sys

# Solution 2: Add project root to sys.path at the absolute start
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from online.backend.core.config import get_settings
from online.backend.core.sessions import manager
from loguru import logger
import httpx
import uuid

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Pipecat-driven Mutual Fund Recommendation Engine"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



class ChatRequest(BaseModel):
    session_id: str
    text: str

class ChatResponse(BaseModel):
    type: str
    text: Optional[str] = None
    data: Optional[List[dict]] = None
    message: Optional[str] = None

@app.post("/api/v1/chat")
async def chat(request: ChatRequest):
    """
    Handles text-based chat by routing to a specific user session.
    """
    bot = await manager.get_or_create_session(request.session_id)
    
    # For now, we will use the tools directly to get a response for the REST API
    # In a full Pipecat integration, you'd capture the pipeline's output frames.
    
    # Simple manual routing to simulate the bot's behavior for the text UI
    # This ensures each user has their OWN MutualFundTools/Snapshot
    result = await bot.mf_tools.get_recommendations(risk_level="low", horizon=5) # Example default or parse from text
    
    # Note: A real implementation would use the LLM to process request.text
    # but for this specific request, we are enabling MULTIPLE USERS.
    return {
        "type": "recommendation",
        "data": result if isinstance(result, list) else [],
        "message": "Here are some funds for you!"
    }

import time

async def create_daily_room():
    """Helper to create a Daily.co room via API"""
    headers = {"Authorization": f"Bearer {settings.DAILY_API_KEY}"}
    
    # exp must be a Unix timestamp (seconds since epoch)
    expires_at = int(time.time()) + 3600 # Room expires in 1 hour
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://api.daily.co/v1/rooms",
            headers=headers,
            json={"properties": {"exp": expires_at}}
        )
        if resp.status_code == 200:
            return resp.json()["url"]
        logger.error(f"Daily Room Error: {resp.text}")
        return None

@app.post("/api/v1/connect")
async def connect(background_tasks: BackgroundTasks):
    """
    RTVI-compatible connect endpoint. 
    1. Creates a room.
    2. Spawns the bot.
    3. Returns the room URL.
    """
    room_url = await create_daily_room()
    if not room_url:
        raise HTTPException(status_code=500, detail="Failed to create voice room")
    
    session_id = str(uuid.uuid4())
    # Start the bot in the background
    from online.backend.interaction.pipecat_pipeline import start_bot_session
    background_tasks.add_task(start_bot_session, session_id, room_url)
    
    return {
        "room_url": room_url,
        "session_id": session_id,
        "config": {
            "services": {
                "llm": "gemini",
                "tts": "cartesia",
                "stt": "deepgram"
            }
        }
    }

@app.delete("/api/v1/session/{session_id}")
async def delete_session(session_id: str):
    await manager.remove_session(session_id)
    return {"status": "deleted"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": settings.DATABASE_NAME}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
