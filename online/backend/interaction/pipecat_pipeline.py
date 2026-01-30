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
from pipecat.frames.frames import TextFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frameworks.rtvi import RTVIObserver, RTVIProcessor
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.services.cartesia.tts import CartesiaTTSService
from pipecat.services.deepgram.stt import DeepgramSTTService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.daily.transport import DailyParams
from pipecat.turns.user_stop.turn_analyzer_user_turn_stop_strategy import (
    TurnAnalyzerUserTurnStopStrategy,
)
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.services.google.google_llm import GoogleLLMService

# Project imports
from online.backend.core.config import get_settings
from online.backend.interaction.mf_tools import MutualFundTools

load_dotenv(override=True)

async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info("Starting Mutual Fund Voice Bot")
    
    settings = get_settings()
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]

    # 1. Services
    stt = DeepgramSTTService(api_key=os.getenv("DEEPGRAM_API_KEY"))
    tts = CartesiaTTSService(
        api_key=os.getenv("CARTESIA_API_KEY"),
        voice_id="71a7ad14-091c-4e8e-a314-022ece01c121",
    )

    # 2. Logic & Context
    mf_tools = MutualFundTools(db)
    rtvi = RTVIProcessor()
    
    # Define System Prompt
    system_prompt = (
        "You are a professional Mutual Fund Assistant. Your goal is to help users find suitable mutual funds. "
        "1. You must collect the user's risk level (low, moderate, or high) and investment horizon (in years). "
        "2. If either is missing, ask the user for it politely. "
        "3. Once you have both, call 'get_recommendations' with the details. "
        "4. If the user provides specific categories (like Equity, Debt, Hybrid), include them. "
        "5. If the user asks to compare funds from the list (e.g., 'compare the first and second' or '1 and 3'), call 'compare_funds'. "
        "6. Always explain why the recommended funds are good based on their metrics (CAGR, Consistency, etc.). "
        "7. Keep your tone professional and helpful."
    )

    # Simple context to keep track of conversation
    context = LLMContext([{"role": "system", "content": system_prompt}])
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
        api_key=os.getenv("GEMINI_API_KEY")
    )

    # Register tools
    llm.register_function("get_recommendations", mf_tools.get_recommendations)
    llm.register_function("compare_funds", mf_tools.compare_funds)
    llm.register_function("get_snapshot_status", mf_tools.get_snapshot_status)

    # 4. Pipeline
    pipeline = Pipeline(
        [
            transport.input(),
            rtvi,
            stt,
            user_aggregator,  # Collects transcriptions
            llm,              # LLM handles intent and logic via tools
            tts,              # Voice output
            transport.output(),
            assistant_aggregator,
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            enable_metrics=True,
            enable_usage_metrics=True,
        ),
        observers=[RTVIObserver(rtvi)],
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("User connected!")
        greeting = "Hello! I'm your Mutual Fund Assistant. To help you find the best funds, could you tell me your risk preference and how long you plan to invest?"
        await task.queue_frame(TextFrame(greeting))

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("User disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=runner_args.handle_sigint)
    await runner.run(task)
    await client.close()

async def bot(runner_args: RunnerArguments):
    transport_params = {
        "daily": lambda: DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
        ),
        "webrtc": lambda: TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.2)),
        ),
    }

    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)

if __name__ == "__main__":
    from pipecat.runner.run import main
    main()