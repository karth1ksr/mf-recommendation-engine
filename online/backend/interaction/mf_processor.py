from loguru import logger 
from pipecat.frames.frames import Frame, TextFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor 

from online.backend.engine.orchestrator import handle_user_input
from online.backend.engine.request_normalizer import RequestNormalizer
from online.backend.engine.recommender import RecommendationEngine
from online.backend.engine.user_snapshot import UserSnapshot

class MFProcessor(FrameProcessor):
    def __init__(self, db): 
        super().__init__()
        self.snapshot = UserSnapshot()
        self.normalizer = RequestNormalizer()
        self.recommender = RecommendationEngine(db)
        self.history = [] 

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        
        # Skip RTVI Control frames
        if hasattr(frame, 'rtvi_type') or 'RTVI' in str(type(frame)):
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, TranscriptionFrame):
            user_text = frame.text.strip()
            if not user_text:
                return

            logger.info(f"User said: {user_text}") # LOGGING
            
            # Process input
            response = await handle_user_input(
                user_text, 
                self.snapshot, 
                self.normalizer, 
                self.recommender,
                history=self.history
            )
            
            self.history.append({"role": "user", "content": user_text})
            
            # Handle ALL response types
            bot_text = ""
            res_type = response["type"]
            
            if res_type in ["message", "explanation", "comparison_result", "question"]:
                bot_text = response.get("text", "")
            
            elif res_type == "recommendation":
                # Convert the list of funds into a spoken sentence
                funds = response.get("data", [])
                msg = response.get("message", "")
                fund_names = [f["scheme_name"] for f in funds[:3]]
                bot_text = f"I suggest looking at {', '.join(fund_names)}. {msg}"

            if bot_text:
                logger.info(f"Bot response: {bot_text}") # LOGGING
                self.history.append({"role": "assistant", "content": bot_text})
                await self.push_frame(TextFrame(bot_text))
        
        # Always forward the original frame so other processors see it
        await self.push_frame(frame, direction)