import os
from sqlalchemy import text, inspect
from sqlalchemy.orm import Session
from app.database.session import SessionLocal, engine
from app.models import User
from app.auth.auth_utils import hash_password
from app.config.settings import settings
from app.utils.logger import get_logger
from app.enums import UserRole

logger = get_logger(__name__)

def create_default_admin():
    """
    Checks for existing ADMIN user and creates a default one if missing.
    Uses credentials from settings.
    """
    db: Session = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == settings.ADMIN_EMAIL).first()
        if not admin:
            logger.info("Creating default ADMIN account...")
            admin_user = User(
                username=settings.ADMIN_USERNAME,
                email=settings.ADMIN_EMAIL,
                hashed_password=hash_password(settings.ADMIN_PASSWORD[:72]),
                role=UserRole.MASTER_ADMIN.value
            )
            db.add(admin_user)
            db.commit()
            logger.info("Default MASTER_ADMIN user created")
        else:
            logger.info("MASTER_ADMIN user already exists")
    finally:
        db.close()

def log_table_schema(table_name: str):
    """
    Logs the schema (columns and nullability) of a specified table.
    Replaces standalone check_schema.py script.
    """
    inspector = inspect(engine)
    try:
        columns = inspector.get_columns(table_name)
        if not columns:
            logger.warning(f"Table '{table_name}' not found or has no columns.")
            return

        logger.info(f"Schema for table: {table_name}")
        for column in columns:
            logger.info(f"Column: {column['name']} | Nullable: {column['nullable']}")
    except Exception as e:
        logger.error(f"Error inspecting table '{table_name}': {e}")

def apply_schema_updates():
    """
    Applies necessary schema updates to the database.
    Replaces standalone update_db.py script.
    """
    with engine.connect() as connection:
        try:
            # Example update: Make project_name nullable in user_story table
            # Note: In production, consider using Alembic for migrations.
            connection.execute(text("ALTER TABLE user_story ALTER COLUMN project_name TYPE VARCHAR(255), ALTER COLUMN project_name DROP NOT NULL;"))
            connection.commit()
            logger.info("Column project_name in table 'user_story' made nullable successfully.")
        except Exception as e:
            logger.error(f"Error applying schema updates: {e}")
            connection.rollback()
