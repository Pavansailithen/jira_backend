import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application configuration settings.
    Loads from environment variables or .env file.
    """
    PROJECT_NAME: str
    PROJECT_VERSION: str
    PORT: int = 8000
    
    DATABASE_URL: str
    
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    
    UPLOAD_DIR: str
    
    # Using str instead of EmailStr to support .local domains in development
    ADMIN_EMAIL: str
    ADMIN_PASSWORD: str
    ADMIN_USERNAME: str

    # Mail configurations
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    
    # Database and extra settings
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://kiet-jira.vercel.app",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    def __init__(self, **data):
        super().__init__(**data)
        # Make UPLOAD_DIR absolute
        if not os.path.isabs(self.UPLOAD_DIR):
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            self.UPLOAD_DIR = os.path.join(base_dir, self.UPLOAD_DIR)

settings = Settings()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
