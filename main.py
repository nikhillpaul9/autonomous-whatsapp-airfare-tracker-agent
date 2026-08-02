import sys
import asyncio

# Fix for Psycopg async on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import os
from app.api.routes import router as webhook_router

# Load environment variables
load_dotenv()

app = FastAPI(title="Flight Price Tracker Agent")

# Ensure the static directory exists locally
os.makedirs("static_images", exist_ok=True)

# CRITICAL: Mount the static directory so Twilio can publicly download the Gemini images
app.mount("/static", StaticFiles(directory="static_images"), name="static")

# Register routes
app.include_router(webhook_router, prefix="/api/v1")

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "flight_tracker_agent"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)