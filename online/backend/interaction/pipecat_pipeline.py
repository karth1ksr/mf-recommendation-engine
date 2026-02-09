import os
import sys
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
from pipecat.frames.frames import TextFrame, LLMRunFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
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
        self.mf_tools = MutualFundTools(db)
        
    async def _setup_pipeline(self, transport: BaseTransport):
        # 1. Services
        stt = DeepgramSTTService(api_key=self.settings.DEEPGRAM_API_KEY)
        tts = CartesiaTTSService(
            api_key=self.settings.CARTESIA_API_KEY,
            voice_id="71a7ad14-091c-4e8e-a314-022ece01c121",
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
            description="Compares two funds side-by-side using their indices.",
            properties={
                "index1": {"type": "integer"},
                "index2": {"type": "integer"}
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
            "STRICT IDENTITY: You are a professional Mutual Fund Assistant. "
            "YOUR CORE WORKFLOW: Identify risk level and horizon, then call 'get_recommendations'. "
            "ONLY recommend funds returned by tools. Use 'get_explanation' only if asked 'Why?'."
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

        # 3. LLM Service
        llm = GoogleLLMService(
            model="gemini-2.5-flash-lite",
            api_key=self.settings.GEMINI_API_KEY
        )

        # Handlers
        async def get_reco_handler(params: FunctionCallParams):
            res = await self.mf_tools.get_recommendations(**params.arguments)
            await params.result_callback(res)

        async def compare_handler(params: FunctionCallParams):
            res = await self.mf_tools.compare_funds(**params.arguments)
            await params.result_callback(res)

        async def explain_handler(params: FunctionCallParams):
            res = await self.mf_tools.get_explanation()
            await params.result_callback(res)

        llm.register_function("get_recommendations", get_reco_handler)
        llm.register_function("compare_funds", compare_handler)
        llm.register_function("get_explanation", explain_handler)

        # 4. Pipeline
        self.pipeline = Pipeline([
            transport.input(),
            rtvi,
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ])

        self.task = PipelineTask(
            self.pipeline,
            params=PipelineParams(enable_metrics=True),
            observers=[RTVIObserver(rtvi)],
        )

        @transport.event_handler("on_client_connected")
        async def on_client_connected(transport, client):
            logger.info(f"Session {self.session_id}: User connected")
            greeting = "Hello! I'm your Mutual Fund Assistant. How can I help you today?"
            context.add_message({"role": "assistant", "content": greeting})
            await self.task.queue_frames([TextFrame(greeting)])

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

async def start_bot_session(session_id: str, transport_type: str = "daily"):
    """
    Entry point to start a new bot session for a user.
    """
    settings = get_settings()
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]
    
    bot = MutualFundBot(session_id, db)
    
    # Transport Setup (Daily as example)
    if transport_type == "daily":
        transport = DailyTransport(
            room_url=f"https://daily.co/{session_id}",
            token=None,
            bot_name="MF Advisor",
            params=DailyTransport.Params(
                audio_in_enabled=True,
                audio_out_enabled=True,
                vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
            )
        )
    else:
        # Fallback or other transports
        return None

    logger.info(f"Starting pipeline for session: {session_id}")
    await bot.run(transport)
    await client.close()

if __name__ == "__main__":
    # For local testing of a single session
    import asyncio
    asyncio.run(start_bot_session(str(uuid.uuid4()), "daily"))
