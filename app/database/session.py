from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config.settings import settings

# Fix for SQLAlchemy - use psycopg2cffi compatible URL for Python 3.14
db_url = settings.DATABASE_URL
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql+psycopg2://", 1)
elif db_url and db_url.startswith("postgresql://"):
    db_url = db_url.replace("postgresql://", "postgresql+psycopg2://", 1)

engine = create_engine(
    db_url,
    # ── Fail fast instead of hanging forever ──
    connect_args={
        "connect_timeout": 10,                    # TCP connection timeout (seconds)
        "options": "-c statement_timeout=30000"   # 30s max per SQL statement
    },
    # ── Pool settings ──
    pool_size=5,           # persistent connections to keep open
    max_overflow=10,       # extra connections allowed under load
    pool_timeout=30,       # seconds to wait for a free pool connection
    pool_recycle=1800,     # recycle connections every 30 min (avoids stale SSL errors)
    pool_pre_ping=True,    # test connection health before using (avoids "connection closed" errors)
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

def get_db():
    """
    Database session dependency.
    Yields a database session and ensures it is closed after request.
    Implements request-scoped transactions:
    - Commits on success
    - Rolls back on exception
    """
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()