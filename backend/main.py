"""
Main FastAPI Application - AI Avatar Receptionist
=================================================

Entry point for the backend server.
Initializes all services and registers API routes.
"""

import asyncio
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import structlog

from config import settings
from database.database import init_db, close_db
from ai.bedrock import BedrockClient
from ai.conversation_manager import ConversationManager
from voice.text_to_speech import TextToSpeech
from voice.speech_to_text import SpeechToText
from voice.vad import VoiceActivityDetector
from vision.person_detection import PersonDetector
from vision.face_detection import FaceDetector
from vision.face_embedding import FaceEmbedder
from vision.face_matching import FaceMatcher
from vision.pipeline import VisionPipeline
from vision.camera import CameraService

from api.websocket import router as websocket_router

# Import optional routers (may fail if models don't match DB)
try:
    from api.visitor import router as visitor_router
    from api.conversation import router as conversation_router
    from api.employee import router as employee_router
    from api.dashboard import router as dashboard_router
    from api.face_api import router as face_router
except Exception as e:
    visitor_router = None
    conversation_router = None
    employee_router = None
    dashboard_router = None
    face_router = None
    print(f"⚠️ Some API routers failed to load: {e}")

# D-ID talking-avatar router (optional; safe if httpx or config missing)
try:
    from api.did_avatar import router as did_router
except Exception as e:
    did_router = None
    print(f"⚠️ D-ID router not loaded: {e}")

# Configure structured logging
structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer() if settings.app_env == "development"
        else structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(
        structlog.get_config().get("min_level", 0)
    ),
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Initializes all services on startup and cleans up on shutdown.
    """
    logger.info("🚀 Starting AI Avatar Receptionist Backend...")
    app.state.start_time = datetime.utcnow()

    # Initialize Database
    try:
        await init_db()
        logger.info("✅ Database connected")
    except Exception as e:
        logger.error("❌ Database connection failed (will retry)", error=str(e))

    # Initialize AWS Bedrock Client
    try:
        bedrock_client = BedrockClient()
        await bedrock_client.initialize()
        app.state.bedrock_client = bedrock_client
        logger.info("✅ AWS Bedrock client initialized")
    except Exception as e:
        logger.error("❌ Bedrock initialization failed (will retry on use)", error=str(e))
        app.state.bedrock_client = BedrockClient()

    # Initialize Conversation Manager
    conv_manager = ConversationManager(app.state.bedrock_client)
    app.state.conversation_manager = conv_manager
    logger.info("✅ Conversation manager initialized")

    # Initialize Text-to-Speech
    try:
        tts = TextToSpeech()
        await tts.initialize()
        app.state.tts = tts
        logger.info("✅ Text-to-Speech initialized")
    except Exception as e:
        logger.error("❌ TTS initialization failed (will retry on use)", error=str(e))
        app.state.tts = TextToSpeech()

    # Initialize Speech-to-Text
    try:
        stt = SpeechToText()
        await stt.initialize()
        app.state.stt = stt
        logger.info("✅ Speech-to-Text initialized")
    except Exception as e:
        logger.error("❌ STT initialization failed", error=str(e))
        app.state.stt = SpeechToText()

    # Initialize Voice Activity Detector
    try:
        vad = VoiceActivityDetector()
        await vad.initialize()
        app.state.vad = vad
        logger.info("✅ Voice Activity Detector initialized")
    except Exception as e:
        logger.error("❌ VAD initialization failed", error=str(e))
        app.state.vad = VoiceActivityDetector()

    # Initialize Vision Services
    try:
        person_detector = PersonDetector(
            confidence_threshold=0.5,
            device="cpu"
        )
        await person_detector.initialize()

        face_detector = FaceDetector(
            model_name=settings.face_embedding_model,
            det_threshold=0.5,
            max_faces=settings.max_faces_per_frame
        )
        await face_detector.initialize()

        face_embedder = FaceEmbedder(model_name=settings.face_embedding_model)
        await face_embedder.initialize()

        face_matcher = FaceMatcher(
            similarity_threshold=settings.face_similarity_threshold
        )

        # Create vision pipeline
        vision_pipeline = VisionPipeline(
            person_detector=person_detector,
            face_detector=face_detector,
            face_embedder=face_embedder,
            face_matcher=face_matcher
        )
        app.state.vision_pipeline = vision_pipeline
        app.state.person_detector = person_detector
        app.state.face_detector = face_detector
        app.state.face_embedder = face_embedder
        app.state.face_matcher = face_matcher

        logger.info("✅ Vision pipeline initialized")
    except Exception as e:
        logger.error("❌ Vision pipeline initialization failed", error=str(e))
        logger.info("   (This is expected if models are not downloaded yet)")

    # Initialize Camera Service (optional - may not have camera)
    try:
        camera = CameraService(
            camera_index=settings.camera_index,
            width=settings.camera_width,
            height=settings.camera_height,
            fps=settings.camera_fps
        )
        app.state.camera_service = camera
        logger.info("✅ Camera service created (not started - use /api/camera/start)")
    except Exception as e:
        logger.error("❌ Camera service creation failed", error=str(e))

    logger.info("=" * 60)
    logger.info("🎉 AI Avatar Receptionist Backend is READY!")
    logger.info(f"   📍 Running at http://{settings.app_host}:{settings.app_port}")
    logger.info(f"   📍 API Docs at http://localhost:{settings.app_port}/docs")
    logger.info("=" * 60)

    yield  # Application runs here

    # Shutdown
    logger.info("🛑 Shutting down AI Avatar Receptionist Backend...")
    if hasattr(app.state, 'camera_service') and app.state.camera_service.is_running:
        await app.state.camera_service.stop()
    await close_db()
    logger.info("👋 Shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="AI Avatar Receptionist",
    description="""
    Intelligent AI-powered office receptionist with:
    - Face detection & recognition
    - Voice conversation with Llama 3 70B
    - Realistic avatar with lip sync
    - Visitor management & registration
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
if visitor_router: app.include_router(visitor_router)
if conversation_router: app.include_router(conversation_router)
if employee_router: app.include_router(employee_router)
app.include_router(websocket_router)
if dashboard_router: app.include_router(dashboard_router)
if face_router: app.include_router(face_router)
if did_router: app.include_router(did_router)


# === Health & Status Endpoints ===

@app.get("/")
async def root():
    """Serve the main AI Receptionist UI."""
    import os
    from fastapi.responses import HTMLResponse
    
    # Try static/index.html first (main UI)
    static_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(static_path):
        with open(static_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    
    # Fallback
    return HTMLResponse(content="<h1>AI Receptionist - static/index.html not found</h1>")


@app.get("/static/{filepath:path}")
async def serve_static(filepath: str):
    """Serve static files."""
    import os
    from fastapi.responses import FileResponse
    file_path = os.path.join(os.path.dirname(__file__), "static", filepath)
    if os.path.exists(file_path):
        return FileResponse(file_path)
    from fastapi.responses import JSONResponse
    return JSONResponse(status_code=404, content={"error": "File not found"})


@app.get("/health")
async def health_check():
    """Health check + database test."""
    services = {}
    
    try:
        from database.database import AsyncSessionLocal
        if AsyncSessionLocal:
            from sqlalchemy import text
            async with AsyncSessionLocal() as session:
                result = await session.execute(text("SELECT 1"))
                services["mysql"] = "connected"
                result = await session.execute(text("SELECT COUNT(*) as cnt FROM visitor"))
                count = result.scalar()
                services["visitors_count"] = count
        else:
            services["mysql"] = "not configured"
    except Exception as e:
        services["mysql"] = f"error: {str(e)}"

    if hasattr(app.state, 'bedrock_client'):
        services["bedrock"] = "initialized" if app.state.bedrock_client._initialized else "not_initialized"
    if hasattr(app.state, 'tts'):
        services["tts"] = "initialized" if app.state.tts._initialized else "not_initialized"

    return {"status": "ok", "services": services}


@app.get("/api/check-visitor")
async def check_visitor():
    """Check if there are known visitors. Returns list for face matching."""
    try:
        from database.database import AsyncSessionLocal
        if not AsyncSessionLocal:
            return {"found": False}
        
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("""SELECT COUNT(*) as cnt FROM visitor 
                        WHERE consent_status='granted' 
                        AND name NOT LIKE 'TestVisitor%'
                        AND name != ''""")
            )
            count = result.mappings().first()['cnt']
            
            if count == 0:
                return {"found": False}
            
            # Without face recognition, cannot identify WHO
            return {"found": False, "has_registered_visitors": True, "count": count}
    except Exception as e:
        return {"found": False, "error": str(e)}


@app.get("/api/lookup-visitor/{name}")
async def lookup_visitor(name: str):
    """Look up a visitor by name. Called when user says their name."""
    try:
        from database.database import AsyncSessionLocal
        if not AsyncSessionLocal:
            return {"found": False}
        
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT id, name, visit_count, last_seen FROM visitor WHERE LOWER(name) = LOWER(:name) AND consent_status='granted' LIMIT 1"),
                {"name": name.strip()}
            )
            row = result.mappings().first()
            if row:
                await session.execute(
                    text("UPDATE visitor SET last_seen=NOW(), visit_count=visit_count+1 WHERE id=:id"),
                    {"id": row['id']}
                )
                await session.commit()
                return {"found": True, "name": row['name'], "visit_count": row['visit_count'] + 1}
            return {"found": False}
    except Exception as e:
        return {"found": False, "error": str(e)}


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.app_env == "development" else "An error occurred"
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
        log_level=settings.log_level.lower()
    )
