"""
BELLA - FastAPI Application
Main application factory with lifespan management.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request

from bella.core.config import config
from bella.core.llm import llm
from bella.api.chat import router as chat_router
from bella.api.voice import router as voice_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle."""
    # Startup
    print(f"\n{'='*50}")
    print(f"  BELLA - Personal AI Assistant")
    print(f"  Model: {config.OLLAMA_MODEL}")
    print(f"  Ollama: {config.OLLAMA_BASE_URL}")
    print(f"{'='*50}\n")

    health = await llm.check_health()
    if health:
        print("[BELLA] OK - Ollama connected, model ready.")
    else:
        print("[BELLA] WARNING: Ollama/model not available. Chat will fail until resolved.")

    yield

    # Shutdown
    await llm.close()
    print("[BELLA] Shutdown complete.")


app = FastAPI(
    title="BELLA",
    description="Personal Local AI Assistant",
    version="0.1.0",
    lifespan=lifespan,
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory=str(config.STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(config.TEMPLATES_DIR))

# Register API routes
app.include_router(chat_router)
app.include_router(voice_router)


@app.get("/")
async def index(request: Request):
    """Serve the main chat UI."""
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"model_name": config.OLLAMA_MODEL},
    )
