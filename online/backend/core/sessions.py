from typing import Dict
from loguru import logger
from online.backend.interaction.pipecat_pipeline import MutualFundBot
from motor.motor_asyncio import AsyncIOMotorClient
from online.backend.core.config import get_settings

class SessionManager:
    """
    Manages active bot sessions for multiple users.
    Each session has its own Pipecat pipeline and state.
    """
    def __init__(self):
        self.sessions: Dict[str, MutualFundBot] = {}
        self.settings = get_settings()
        self.client = AsyncIOMotorClient(self.settings.MONGODB_URL)
        self.db = self.client[self.settings.DATABASE_NAME]

    async def get_or_create_session(self, session_id: str) -> MutualFundBot:
        if session_id not in self.sessions:
            logger.info(f"Creating new bot session for: {session_id}")
            # Note: In a real production app, you might want to cleanup old sessions
            self.sessions[session_id] = MutualFundBot(session_id, self.db)
        return self.sessions[session_id]

    async def remove_session(self, session_id: str):
        if session_id in self.sessions:
            # Cleanup pipeline task if running
            session = self.sessions[session_id]
            if session.task:
                await session.task.cancel()
            del self.sessions[session_id]
            logger.info(f"Removed session: {session_id}")

# Global manager instance
manager = SessionManager()
