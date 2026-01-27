import os
import aiohttp
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from loguru import logger

logger.info("Starting MF Pipeline...")
logger.info("Loading Local Smart Turn Analyzer V3...")
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3

logger.info("Local Smart Turn Analyzer V3 loaded")
logger.info("Loading Silero VAD model...")

from pipecat.audio.vad.silero import SileroVADAnalyzer

logger.info("Silero VAD model loaded")
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    LLMRunFrame, LLMTextFrame, TranscriptionFrame,
    Frame, TextFrame, StartFrame
)

from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.frameworks.rtvi import RTVIConfig, RTVIObserver, RTVIProcessor
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.services.google.llm import GoogleLLMService

from pipecat.transports.services.helpers.daily_rest import (
    DailyRESTHelper, 
    DailyRoomParams, 
    DailyRoomProperties
)
from pipecat.transports.daily.transport import DailyParams, DailyTransport

from online.backend.core.config import get_settings
from online.backend.core.sessions import sessions
from online.backend.interaction.mf_processor import MFProcessor

async def main(user_id: str, room_url: str = None, token: str = None):
    logger.info("Smart Text/Voice Bot Starting!")
    async with aiohttp.ClientSession() as session:
        
        if not room_url:
            daily_helper = DailyRESTHelper(api_key=settings.DAILY_API_KEY)
            room = await daily_helper.create_room(
                DailyRoomParams(
                    name=f"mf-{user_id}",
                    privacy="private",
                    properties=DailyRoomProperties(max_participants=2)
                )
            )
            room_url, token = room.url, await daily_helper.get_token(room.url)

        # Load settings
        settings = get_settings()

        # Initialize MongoDB
        client = AsyncIOMotorClient(settings.MONGODB_URL)
        db = client[settings.DATABASE_NAME]

        logger.info(f"Connected to the DB {settings.DATABASE_NAME}")


        # 1. Initialize transport
        transport = DailyTransport(
            room_url,
            token,
            "Respond bot",
            DailyParams(
                audio_in_enabled=True,
                audio_out_enabled=True,
                transcription_enabled=True,
                vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.15)),
            ),
        )

        # 2. Initialize Services
        stt = DeepgramSTTService(api_key=settings.DEEPGRAM_API_KEY)
        tts = CartesiaTTSService(
            api_key=settings.CARTESIA_API_KEY,
            voice_id="71a7ad14-091c-4e8e-a314-022ece01c121",
        )

        # 3. Initialize Processors
        rtvi = RTVIProcessor(config=RTVIConfig(config=[]))
        mf_processor = MFProcessor(db, sessions_store=sessions, session_id=user_id)

        # 4. Pipeline
        pipeline = Pipeline(
         [
            transport.input(),
            rtvi,
            stt,
            mf_processor,
            tts,
            transport.output(),
         ]
        )

        # 5. Task
        task = PipelineTask(
            pipeline,
            params=PipelineParams(
                audio_in_sample_rate=16000,      
                audio_out_sample_rate=24000,   
                audio_out_10ms_chunks=2,  
                enable_metrics=True,
                enable_usage_metrics=True,
            ),
            observers=[RTVIObserver(rtvi)],
        )

        # 6. Actions on user connect and disconnect

        @transport.event_handler("on_first_participant_joined")
        async def on_first_participant_joined(participant):
            await transport.capture_participant_audio(participant["id"])

            # Greet the user and start the pipeline
            greeting = "Hello! I'm your Mutual Fund Assistant. To help you find the best funds, could you tell me your risk preference and how long you plan to invest?"
            
            # task.queue_frame to inject it into the flow
            await task.queue_frame(TextFrame(greeting), FrameDirection.DOWNSTREAM)
        
        @transport.event_handler("on_participant_left")
        async def on_participant_left(participant):
            await task.cancel()

        @transport.event_handler("on_app_message")
        async def on_app_message(transport, payload, participant_id):
            logger.info(f"Received app message: {payload}")
            if isinstance(payload, dict) and "text" in payload:
                # Inject text from data channel into the pipeline as an UPSTREAM TextFrame
                await task.queue_frame(TextFrame(payload["text"]), FrameDirection.UPSTREAM)
          
        # 7. Run
        runner = PipelineRunner()
        try:
            await runner.run(task)
        except Exception as e:
            logger.error(f"Error running pipeline: {e}")
        finally:
            client.close()

if __name__ == "__main__":
    import sys
    # Use user_id from command line if provided, else default to "test-user"
    user_id = sys.argv[1] if len(sys.argv) > 1 else "test-user"
    asyncio.run(main(user_id=user_id))