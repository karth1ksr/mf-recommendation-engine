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
from pipecat.transports.daily.transport import DailyParams
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

async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    logger.info("Starting Mutual Fund Voice Bot")
    
    settings = get_settings()
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]

    # 1. Services
    stt = DeepgramSTTService(api_key=settings.DEEPGRAM_API_KEY)
    tts = CartesiaTTSService(
        api_key=settings.CARTESIA_API_KEY,
        voice_id="71a7ad14-091c-4e8e-a314-022ece01c121",
    )

    # 2. Logic & Context
    mf_tools = MutualFundTools(db)
    rtvi = RTVIProcessor()
    
    # Tool definitions (using FunctionSchema and ToolsSchema)
    get_recommendations_tool = FunctionSchema(
        name="get_recommendations",
        description="Fetches a ranked list of mutual funds based on the user's risk profile and investment horizon. Call this ONLY when you have both risk level and horizon.",
        properties={
            "risk_level": {
                "type": "string",
                "description": "The user's risk tolerance (low, moderate, or high).",
                "enum": ["low", "moderate", "high"]
            },
            "horizon": {
                "type": "integer",
                "description": "The investment period in years."
            },
            "preferred_categories": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional specific categories to filter (e.g., Equity, Debt)."
            }
        },
        required=["risk_level", "horizon"]
    )

    compare_funds_tool = FunctionSchema(
        name="compare_funds",
        description="Compares two funds from the recently suggested list side-by-side using their 1-based indices.",
        properties={
            "index1": {
                "type": "integer",
                "description": "The 1-based index of the first fund (e.g., 1 for the first one)."
            },
            "index2": {
                "type": "integer",
                "description": "The 1-based index of the second fund (e.g., 2 for the second one)."
            }
        },
        required=["index1", "index2"]
    )

    get_explanation_tool = FunctionSchema(
        name="get_explanation",
        description="Provides detailed metrics and rationale for the current recommendations when the user asks 'Why?' or 'Explain'.",
        properties={},
        required=[]
    )

    get_snapshot_status_tool = FunctionSchema(
        name="get_snapshot_status",
        description="Returns the current state of collected user preferences (risk level and horizon).",
        properties={},
        required=[]
    )

    tools = ToolsSchema(standard_tools=[
        get_recommendations_tool,
        compare_funds_tool,
        get_explanation_tool,
        get_snapshot_status_tool
    ])

    system_prompt = (
        "STRICT IDENTITY: You are a professional Mutual Fund Assistant. You MUST strictly use the tools provided to fetch data. "
        "YOUR CORE WORKFLOW: "
        "1. Identify the user's risk level (low, moderate, high) and investment horizon (years). "
        "2. As soon as you have BOTH values, IMMEDIATELY call 'get_recommendations'. Do NOT ask 'is this correct?' or for permission. "
        "3. If the user confirms previously mentioned values (e.g., says 'yes', 'exactly'), call 'get_recommendations' using those values immediately. "
        "DATA SOURCE RULE: You are ONLY allowed to recommend mutual funds returned by the 'get_recommendations' tool. "
        "EXPLANATION POLICY: "
        "- When providing results, give a brief list of the funds first. "
        "- ONLY provide detailed rationale if the user asks 'Why?' or 'Explain'. Use the 'get_explanation' tool for this. "
        "CONVERSATION RULES: "
        "1. Use plain text only. No markdown symbols like asterisks (*) or hash signs (#). "
        "2. Do NOT mention tool or function names to the user. "
        "3. Keep your tone professional and natural for voice."
    )

    # Simple context to keep track of conversation, now including tools
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
        api_key=settings.GEMINI_API_KEY
    )

    # Register tools using new FunctionCallParams pattern to fix DeprecationWarning
    async def get_recommendations_handler(params: FunctionCallParams):
        result = await mf_tools.get_recommendations(**params.arguments)
        await params.result_callback(result)

    async def compare_funds_handler(params: FunctionCallParams):
        result = await mf_tools.compare_funds(**params.arguments)
        await params.result_callback(result)

    async def get_explanation_handler(params: FunctionCallParams):
        result = await mf_tools.get_explanation()
        await params.result_callback(result)

    async def get_snapshot_status_handler(params: FunctionCallParams):
        result = await mf_tools.get_snapshot_status()
        await params.result_callback(result)

    llm.register_function("get_recommendations", get_recommendations_handler)
    llm.register_function("compare_funds", compare_funds_handler)
    llm.register_function("get_explanation", get_explanation_handler)
    llm.register_function("get_snapshot_status", get_snapshot_status_handler)

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
        # Add greeting to context so the LLM remembers it
        context.add_message({"role": "assistant", "content": greeting})
        # Queue TextFrame to speak the greeting. Avoid LLMRunFrame here to prevent Gemini 400 error.
        await task.queue_frames([TextFrame(greeting)])

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