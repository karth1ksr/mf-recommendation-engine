import os
import sys
import asyncio
from dotenv import load_dotenv
from loguru import logger
from motor.motor_asyncio import AsyncIOMotorClient

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

# Import Pipecat components
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import Frame, TextFrame, LLMRunFrame, OutputTransportMessageFrame, TranscriptionFrame
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.aggregators.user_transcript_aggregator import UserTranscriptAggregator
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.processors.frameworks.rtvi import RTVIObserver, RTVIProcessor
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams, DailyTransport
from pipecat.turns.user_stop.turn_analyzer_user_turn_stop_strategy import (
    TurnAnalyzerUserTurnStopStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.services.google.llm import GoogleLLMService
from pipecat.services.llm_service import FunctionCallParams

# Project imports
from online.backend.core.config import get_settings
from online.backend.interaction.mf_tools import MutualFundTools

load_dotenv(override=True)

from typing import Dict, Any, Optional
import uuid


class MutualFundBot:
    """
    Encapsulates a Pipecat pipeline and its state for a single user session.
    Allows for multiple users to interact with the bot independently.
    """
    def __init__(self, session_id: str, db: AsyncIOMotorClient):
        self.session_id = session_id
        self.db = db
        self.settings = get_settings()
        self.task: Optional[PipelineTask] = None
        self.pipeline: Optional[Pipeline] = None
        self.mf_tools = MutualFundTools(db, session_id)
        
    async def _setup_pipeline(self, transport: BaseTransport):
        # 1. Services
        stt = DeepgramSTTService(api_key=self.settings.DEEPGRAM_API_KEY)
        tts = CartesiaTTSService(
            api_key=self.settings.CARTESIA_API_KEY,
            voice_id="71a7ad14-091c-4e8e-a314-022ece01c121", # Baritone Fast
            sample_rate=24000
        )

        # 2. Logic & Context
        rtvi = RTVIProcessor()
        
        get_recommendations_tool = FunctionSchema(
            name="get_recommendations",
            description="Fetches a ranked list of mutual funds based on the user's risk profile and investment horizon.",
            properties={
                "risk_level": {"type": "string", "enum": ["low", "moderate", "high"]},
                "horizon": {"type": "integer"},
                "preferred_categories": {"type": "array", "items": {"type": "string"}}
            },
            required=["risk_level", "horizon"]
        )

        compare_funds_tool = FunctionSchema(
            name="compare_funds",
            description="Compares two specific funds side-by-side using their 1-based indices from the recommended list (e.g., 1 and 2).",
            properties={
                "index1": {"type": "integer", "description": "The rank/index of the first fund (e.g., 1)"},
                "index2": {"type": "integer", "description": "The rank/index of the second fund (e.g., 2)"}
            },
            required=["index1", "index2"]
        )

        get_explanation_tool = FunctionSchema(
            name="get_explanation",
            description="Provides detailed metrics and rationale for the recommendations.",
            properties={},
            required=[]
        )

        tools = ToolsSchema(standard_tools=[
            get_recommendations_tool,
            compare_funds_tool,
            get_explanation_tool
        ])

        system_prompt = (
            "You are a professional Mutual Fund Assistant. "
            "IDENTITY RULES: "
            "- Ask the user for their risk level and horizon to get started. "
            "- When you call 'get_recommendations', say: 'Here are the best funds I found based on your profile.' "
            "- When you call 'compare_funds', say: 'I have opened the side-by-side comparison for those funds below.' "
            "- Only provide one response at a time. Do not repeat instructions or internal logic. "
            "- No symbols, markdown, lists, or BOLDING."
        )

        context = LLMContext(
            messages=[{"role": "system", "content": system_prompt}],
            tools=tools
        )
        
        user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
            context,
            user_params=LLMUserAggregatorParams(
                user_turn_strategies=UserTurnStrategies(
                    stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=LocalSmartTurnAnalyzerV3())]
                ),
            ),
        )
        user_transcript_aggregator = UserTranscriptAggregator()
        # 3. LLM Service
        llm = GoogleLLMService(
            model="gemini-2.5-flash-lite",
            api_key=self.settings.GEMINI_API_KEY
        )

        # Handlers
        async def get_reco_handler(params: FunctionCallParams):
            res = await self.mf_tools.get_recommendations(**params.arguments)
            msg = "Here are the recommended funds for your preference!"
            # Push structured data directly (Standard format for our frontend)
            await self.task.queue_frames([
                OutputTransportMessageFrame(message={
                    "type": "recommendation",
                    "data": res
                })
            ])
            await params.result_callback(res)

        async def compare_handler(params: FunctionCallParams):
            res = await self.mf_tools.compare_funds(**params.arguments)
            if isinstance(res, str):
                await params.result_callback(res)
                return

            msg = "I've prepared the comparison for you below."
            # Push comparison data
            await self.task.queue_frames([
                OutputTransportMessageFrame(message={
                    "type": "comparison_result",
                    "funds": [res["fund_a"], res["fund_b"]],
                    "horizon": res["analysis_context"]["horizon"]
                })
            ])
            await params.result_callback(res)

        async def explain_handler(params: FunctionCallParams):
            res = await self.mf_tools.get_explanation()
            # Push explanation context if needed
            await self.task.queue_frames([OutputTransportMessageFrame(message={
                "type": "explanation",
                "data": res
            })])
            await params.result_callback(res)

        # handlers ... (rest of configuration)
        llm.register_function("get_recommendations", get_reco_handler)
        llm.register_function("compare_funds", compare_handler)
        llm.register_function("get_explanation", explain_handler)

        # 4. Pipeline
        # Standard flow: Input -> Logic/State -> Output
        self.pipeline = Pipeline([
            transport.input(),
            rtvi,
            stt,
            user_transcript_aggregator,
            user_aggregator,
            llm,
            tts,
            assistant_aggregator,
            transport.output(),
        ])

        self.task = PipelineTask(
            self.pipeline,
            params=PipelineParams(enable_metrics=True),
        )
        rtvi_observer = RTVIObserver(rtvi=rtvi)
        self.task.add_observer(rtvi_observer)

        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info(f"Session {self.session_id}: User connected. Waiting for transport stabilization...")
            
            # 1. Stabilization wait to ensure data channel is 100% ready
            await asyncio.sleep(2)
    
            # 2. Sync state
            await self.mf_tools.load_snapshot()
    
            # 3. Update LLM context with system status (no manual greeting)
            if self.mf_tools.snapshot.risk_level:
                status = f"User profile loaded: risk={self.mf_tools.snapshot.risk_level}, horizon={self.mf_tools.snapshot.horizon}"
                context.add_message({"role": "system", "content": status})
    
   
            # 4. Trigger LLM to generate greeting automatically
            await self.task.queue_frames([LLMRunFrame()])
    
            logger.info(f"Session {self.session_id}: LLM greeting triggered.")
        
    async def push_text(self, text: str):
        """
        Allows pushing text directy into the pipeline (for text-based chat).
        """
        if self.task:
            logger.debug(f"Pushing text to pipeline {self.session_id}: {text}")
            await self.task.queue_frames([TextFrame(text)])
        else:
            logger.error(f"Cannot push text: Task not started for {self.session_id}")

    async def run(self, transport: BaseTransport):
        await self._setup_pipeline(transport)
        runner = PipelineRunner(handle_sigint=False) # Runner doesn't exit on sigint here
        await runner.run(self.task)

async def start_bot_session(session_id: str, room_url: str):
    """
    Spawns a bot instance and joins a specific Daily room.
    """
    settings = get_settings()
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]
    bot = MutualFundBot(session_id, db)
    
    transport = DailyTransport(
        room_url=room_url,
        token=None,
        bot_name="MF Advisor",
        params=DailyParams(
            audio_out_enabled=True,
            audio_out_sample_rate=24000,
            transcription_enabled=True,
            vad_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.3)),
        )
    )

    logger.info(f"Bot session {session_id} joining room: {room_url}")
    try:
        await bot.run(transport)
    finally:
        client.close()

if __name__ == "__main__":
    # For local testing
    import asyncio
    # Note: Requires a valid DAILY_API_KEY to be set in config/env
    print("Please use the /api/v1/connect endpoint to start sessions.")
