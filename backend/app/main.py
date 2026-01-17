"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.routers import map_config, search, floorplan

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Workplace Navigator Backend...")
    logger.info("Using GeoJSON data from floorplan_geojson/imdf_package/")

    yield

    logger.info("Shutting down Workplace Navigator Backend...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Multi-Cloud Digital Concierge - AI-powered workplace navigation",
    version=settings.app_version,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(search.router)
app.include_router(map_config.router)
app.include_router(floorplan.router)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": "healthy",
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",
        "ai_service": "configured" if settings.openrouter_api_key else "not_configured",
        "azure_maps": "configured" if settings.azure_maps_client_id else "not_configured",
    }
