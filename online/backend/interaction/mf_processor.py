from loguru import logger
from pipecat.frames.frames import Frame, TextFrame, TranscriptionFrame, StartFrame, StopFrame
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
        self._activated = False

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # 1. Lifecycle Tracking
        if isinstance(frame, StartFrame):
            self._activated = True
            logger.info("MFProcessor activated")
            await self.push_frame(frame, direction)
            return

        if isinstance(frame, StopFrame):
            self._activated = False
            logger.info("MFProcessor deactivated")
            await self.push_frame(frame, direction)
            return

        # 2. Safety Gate: Ignore processing if not activated
        if not self._activated:
            await self.push_frame(frame, direction)
            return

        # 3. Control Frame Bypass
        if hasattr(frame, "rtvi_type") or "RTVI" in frame.__class__.__name__:
            await self.push_frame(frame, direction)
            return

        # 4. Filter Audio Frames (Performance & Logic Guard)
        if frame.__class__.__name__.startswith("InputAudio"):
            await self.push_frame(frame, direction)
            return

        # 5. Logical Turn Management (Transcription Only)
        if isinstance(frame, TranscriptionFrame):
            user_text = frame.text.strip()
            
            # Guard: Ignore noise or very short inputs
            if not user_text or len(user_text) < 2:
                await self.push_frame(frame, direction)
                return

            logger.info(f"Processing turn: {user_text}")
            
            # Pass to recommendation engine
            response = await handle_user_input(
                user_text, 
                self.snapshot, 
                self.normalizer, 
                self.recommender,
                history=self.history
            )
            
            self.history.append({"role": "user", "content": user_text})
            
            # Convert response to speech
            bot_text = ""
            res_type = response.get("type")
            
            if res_type in {"message", "explanation", "comparison_result", "question"}:
                bot_text = response.get("text", "")
            
            elif res_type == "recommendation":
                funds = response.get("data", [])
                msg = response.get("message", "")
                fund_names = [f["scheme_name"] for f in funds[:3]]
                bot_text = f"I suggest looking at {', '.join(fund_names)}. {msg}"

            if bot_text:
                logger.info(f"Assistant: {bot_text}")
                self.history.append({"role": "assistant", "content": bot_text})
                await self.push_frame(TextFrame(bot_text))

            # Forward transcription frame
            await self.push_frame(frame, direction)
            return

        # 6. Default: Forward all other frames
        await self.push_frame(frame, direction)
