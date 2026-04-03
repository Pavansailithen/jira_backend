from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging

from app.endpoints.router import api_router
from app.database.session import engine
from app.database.base import Base
from app.config.settings import settings
from app.utils.db_utils import create_default_admin
from app.exceptions import BaseAPIException, base_api_exception_handler

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.PROJECT_VERSION
)

app.add_exception_handler(BaseAPIException, base_api_exception_handler)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # ✅ Allow all origins for now, restrict after testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Uploads directory
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

# Include API Router
app.include_router(api_router)

@app.on_event("startup")
def startup_event():
    """
    Execute startup tasks.
    Creates tables and default admin user if not present.
    """
    try:
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise e

    try:
        logger.info("Creating default admin user...")
        create_default_admin()
        logger.info("Default admin user created successfully.")
    except Exception as e:
        logger.error(f"Error creating default admin: {e}")

@app.get("/")
def root():
    """
    Root endpoint for health check.
    """
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)