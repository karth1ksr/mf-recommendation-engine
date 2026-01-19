from fastapi import FastAPI
from online.core.config import get_settings
from online.api.routes import recommendations

settings = get_settings()

app = FastAPI(title=settings.APP_NAME)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Include routers
# app.include_router(recommendations.router, prefix=settings.API_V1_STR)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
