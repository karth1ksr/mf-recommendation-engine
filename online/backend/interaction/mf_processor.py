from loguru import logger 
from pipecat.frames.frames import Frame, TextFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor 

from online.backend.engine.orchestrator import handle_user_input
from online.backend.engine.request_normalizer import RequestNormalizer
from online.backend.engine.recommender import RecommendationEngine
from online.backend.engine.user_snapshot import UserSnapshot

class MFProcessor(FrameProcessor):
    def __init__(self, db, sessions_store: dict = None, session_id: str = None): 
        super().__init__()
        self.db = db
        self.sessions_store = sessions_store
        self.session_id = session_id
        
        # Load existing snapshot if available, otherwise create new
        if sessions_store is not None and session_id in sessions_store:
            self.snapshot = sessions_store[session_id]
            logger.info(f"MFProcessor: Loaded existing session state for {session_id}")
        else:
            self.snapshot = UserSnapshot()
            if sessions_store is not None and session_id:
                sessions_store[session_id] = self.snapshot
            logger.info(f"MFProcessor: Initialized new session state for {session_id}")

        self.normalizer = RequestNormalizer()
        self.recommender = RecommendationEngine(db)
        self.history = [] 

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        # 1. Skip control frames but forward them
        if hasattr(frame, 'rtvi_type') or 'RTVI' in str(type(frame)):
            await self.push_frame(frame, direction)
            return

        # 2. Capture user input text from EITHER voice (TranscriptionFrame) OR text chat (TextFrame)
        user_text = None
        if isinstance(frame, TranscriptionFrame):
            user_text = frame.text.strip()
        elif isinstance(frame, TextFrame) and direction == FrameDirection.UPSTREAM:
            # Assume upstream TextFrames are from the user chat interface
            user_text = frame.text.strip()

        if user_text:
            logger.info(f"MFProcessor: Processing input: '{user_text}'")
            
            # 3. Core Logic Integration
            response = await handle_user_input(
                user_text, 
                self.snapshot, 
                self.normalizer, 
                self.recommender,
                history=self.history
            )
            
            self.history.append({"role": "user", "content": user_text})
            
            # 4. Handle Response Packaging
            res_type = response.get("type")
            voice_text = ""
            data_payload = response # Keep the full response for data channel

            if res_type in ["message", "explanation", "comparison_result", "question"]:
                voice_text = response.get("text", "")
            
            elif res_type == "recommendation":
                funds = response.get("data", [])
                msg = response.get("message", "")
                fund_names = [f["scheme_name"] for f in funds[:3]]
                voice_text = f"I suggest looking at {', '.join(fund_names)}. {msg}"

            # 5. Push Outputs
            if voice_text:
                logger.debug(f"MFProcessor: Outputting voice text: {voice_text}")
                self.history.append({"role": "assistant", "content": voice_text})
                # Send to TTS
                await self.push_frame(TextFrame(voice_text))
            
            # Always push the structured response "downstream" as well 
            # This allows the frontend to render UI (cards/tables) via the data channel
            # in addition to the voice/text response.
            # (In RTVI, you'd send this as a custom action or message)
            # await self.push_frame(DataFrame(data_payload)) # Example for data channel

        # Always forward the original frame 
        await self.push_frame(frame, direction)