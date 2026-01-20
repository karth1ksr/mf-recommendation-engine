import os
import sys

# Solution 2: Add project root to sys.path at the absolute start
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if project_root not in sys.path:
    sys.path.append(project_root)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from online.backend.core.config import get_settings
from online.backend.api.routes import recommendations

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    description="Deterministic Mutual Fund Recommendation Engine with LLM Explanations"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy", "database": settings.DATABASE_NAME}

# Include routers
app.include_router(recommendations.router, prefix=settings.API_V1_STR, tags=["Recommendations"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
