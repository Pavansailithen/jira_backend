from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import logging
import threading
 
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
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
 
# Uploads directory
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")
 
# Include API Router
app.include_router(api_router)
 
def init_db():
    """
    Run DB table creation and admin seeding in a background thread.
    This lets uvicorn bind the port immediately so Render doesn't
    kill the process while waiting for the DB connection.
    """
    try:
        logger.info("Creating database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully.")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        # Do NOT re-raise — server should still start even if DB is slow
        return
 
    try:
        logger.info("Creating default admin user...")
        create_default_admin()
        logger.info("Default admin user created successfully.")
    except Exception as e:
        logger.error(f"Error creating default admin: {e}")
 
 
@app.on_event("startup")
def startup_event():
    """
    Start DB init in a background thread so uvicorn binds the port
    immediately. Render requires the port to be open within ~60 seconds.
    """
    thread = threading.Thread(target=init_db, daemon=True)
    thread.start()
    logger.info("Server started. DB initialization running in background.")
 
@app.get("/")
def root():
    """
    Root endpoint for health check.
    """
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}
 
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=int(os.getenv("PORT", 8000)), reload=True)