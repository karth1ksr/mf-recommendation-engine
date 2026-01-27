import modal
import os
import sys

# 1. Define the Cloud Image
image = (
    modal.Image.debian_slim(python_version="3.12")
    # STEP 1: Install heavy dependencies FIRST
    .pip_install(
        "pipecat-ai[webrtc,daily,silero,deepgram,google,cartesia,local-smart-turn-v3,runner]",
        "daily-python",
        "motor",
        "loguru",
        "google-genai",
        "fastapi",
        "uvicorn[standard]",
        "aiohttp",
        "pandas",
        "numpy",
        "pydantic-settings",
        "python-multipart"
    )
    # STEP 2: Add your local code LAST
    .add_local_dir(
        os.path.join(os.path.dirname(__file__), "online"), 
        remote_path="/root/online",
        copy=True
    )
)

app = modal.App("mf-voice-bot")

# 2. FastAPI API
@app.function(
    image=image, 
    secrets=[modal.Secret.from_name("MF_SECRETS")]
)
@modal.asgi_app()
def fastapi_api():
    import sys
    # Ensure /root is in path so 'online' package is visible
    if "/root" not in sys.path:
        sys.path.append("/root")

    from online.backend.main import app as fastapi_app  
    return fastapi_app

# 3. Pipecat Voice Bot
@app.function(
    image=image, 
    secrets=[modal.Secret.from_name("MF_SECRETS")], 
    timeout=7200
)
def voice_bot(user_id: str, room_url: str, token: str):
    import asyncio
    import sys
    if "/root" not in sys.path:
        sys.path.append("/root")

    from online.backend.interaction.pipecat_pipeline import main  
    asyncio.run(main(user_id=user_id, room_url=room_url, token=token))
