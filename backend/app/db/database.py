import os
import re
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv, dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError, SQLAlchemyError, ArgumentError
from sqlalchemy.engine.url import make_url
from fastapi import HTTPException

# Locate backend/.env
BASE_DIR = Path(__file__).resolve().parent.parent.parent
env_path = BASE_DIR / ".env"


def reload_environment():
    """Force reload backend/.env with override=True to prevent stale variables."""
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=True)
    else:
        load_dotenv(override=True)


# Initial load
reload_environment()

Base = declarative_base()

_engine = None
_SessionLocal = None
_current_engine_url: Optional[str] = None


def get_database_url() -> str:
    """
    Retrieve and normalize DATABASE_URL from backend/.env or environment.
    Guarantees fresh reading from backend/.env if available.
    """
    # Always check backend/.env first to avoid stale OS variables
    file_vals = dotenv_values(env_path) if env_path.exists() else {}
    url = file_vals.get("DATABASE_URL") or os.getenv("DATABASE_URL", "")
    url = url.strip()

    # Strip accidental duplicate variable names if pasted from dashboard
    while url.startswith("DATABASE_URL="):
        url = url[len("DATABASE_URL=") :].strip()

    # Strip surrounding quotes
    if (url.startswith('"') and url.endswith('"')) or (
        url.startswith("'") and url.endswith("'")
    ):
        url = url[1:-1].strip()

    # Normalize legacy postgres:// to postgresql:// for SQLAlchemy
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)

    return url


def is_placeholder_url(url: str) -> bool:
    """Check if the URL is still a template placeholder or unconfigured."""
    if not url:
        return True
    lower = url.lower()
    placeholders = [
        "your_password_here",
        "<password>",
        "your_neon_password",
        "placeholder",
        "username:password@localhost",
    ]
    return any(p in lower for p in placeholders)


def get_sanitized_database_url() -> str:
    """Return DATABASE_URL with passwords hidden for safe error messages and logs."""
    url = get_database_url()
    if not url:
        return "Not configured"
    try:
        parsed = make_url(url)
        return parsed.render_as_string(hide_password=True)
    except Exception:
        # Fallback regex masking
        return re.sub(r":([^@/]+)@", ":***@", url)


def sanitize_error_message(error: Exception | str) -> str:
    """Mask any passwords or connection strings that might appear in exception text."""
    msg = str(error)
    url = get_database_url()
    if url:
        try:
            parsed = make_url(url)
            if parsed.password and parsed.password in msg:
                msg = msg.replace(parsed.password, "***")
        except Exception:
            pass
    # Mask any pattern that looks like user:password@host
    msg = re.sub(r":([^@/\s:]+)@([a-zA-Z0-9\.\-]+)", r":***@\2", msg)
    # Mask any Gemini API key pattern
    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    if gemini_key and gemini_key in msg:
        msg = msg.replace(gemini_key, "[REDACTED]")
    return msg


def get_engine():
    """
    Lazily initialize or refresh the SQLAlchemy engine.
    Disposes and re-creates the engine if the URL changed.
    Configures pool pre-ping, pool recycle, and connect timeouts suitable for Neon.
    """
    global _engine, _SessionLocal, _current_engine_url

    # Ensure fresh environment
    reload_environment()
    url = get_database_url()

    if not url or is_placeholder_url(url):
        return None

    # If the URL changed, dispose the existing engine to avoid stale cached credentials
    if _engine is not None and _current_engine_url != url:
        try:
            _engine.dispose()
        except Exception:
            pass
        _engine = None
        _SessionLocal = None

    if _engine is None:
        try:
            parsed = make_url(url)
            # Ensure SSL mode for Neon PostgreSQL if not explicitly defined
            query_params = dict(parsed.query)
            if "neon.tech" in (parsed.host or "") and "sslmode" not in query_params:
                query_params["sslmode"] = "require"
                parsed = parsed.set(query=query_params)
                url = parsed.render_as_string(hide_password=False)

            _engine = create_engine(
                url,
                pool_pre_ping=True,       # Detect disconnects before issuing queries
                pool_recycle=300,         # Recycle connections every 5 minutes (ideal for Neon pooler)
                pool_size=5,
                max_overflow=10,
                connect_args={"connect_timeout": 10},
            )
            _current_engine_url = url
        except Exception as e:
            safe_url = get_sanitized_database_url()
            raise HTTPException(
                status_code=500,
                detail=f"Invalid DATABASE_URL configuration ({safe_url}): {sanitize_error_message(e)}",
            )

    return _engine


def get_session_factory():
    """Lazily initialize and return the session factory."""
    global _SessionLocal
    engine = get_engine()
    if engine is None:
        return None
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return _SessionLocal


def init_db() -> bool:
    """
    Startup database connection check and schema verification.
    Only reports success if a live connection query ('SELECT 1') and table creation actually succeed.
    """
    url = get_database_url()
    if not url:
        print("[Database] Info: DATABASE_URL is not set in backend/.env. PostgreSQL storage is not active.")
        return False

    if is_placeholder_url(url):
        print(f"[Database] Warning: DATABASE_URL appears to contain placeholder credentials ({get_sanitized_database_url()}).")
        return False

    safe_url = get_sanitized_database_url()
    try:
        engine = get_engine()
        if engine is None:
            print(f"[Database] Error: Could not create engine for {safe_url}.")
            return False

        # 1. Live ping test
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))

        # 2. Import models and verify/create tables
        from app.models.conversation import Conversation  # noqa: F401
        from app.models.message import Message  # noqa: F401
        from app.models.document import Document  # noqa: F401
        from app.models.user_preference import UserPreference  # noqa: F401

        Base.metadata.create_all(bind=engine)
        print(f"[Database] Successfully connected to PostgreSQL ({safe_url}) and verified tables.")
        return True
    except OperationalError as oe:
        clean_err = sanitize_error_message(oe.orig if hasattr(oe, "orig") else oe)
        print(f"[Database] Connection failed at {safe_url}: {clean_err}")
        return False
    except Exception as e:
        clean_err = sanitize_error_message(e)
        print(f"[Database] Initialization error for {safe_url}: {clean_err}")
        return False


def get_db():
    """
    FastAPI dependency yielding a validated database session.
    Provides clear, sanitized HTTP 500/503 exceptions if PostgreSQL is unconfigured or unreachable.
    """
    url = get_database_url()
    if not url or is_placeholder_url(url):
        raise HTTPException(
            status_code=500,
            detail=(
                "DATABASE_URL is not configured in backend/.env. "
                "Please configure your Neon PostgreSQL connection string, e.g.: "
                "DATABASE_URL=postgresql://neondb_owner:YOUR_PASSWORD@ep-xxx.neon.tech/neondb?sslmode=require"
            ),
        )

    session_factory = get_session_factory()
    if not session_factory:
        safe_url = get_sanitized_database_url()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize database engine for {safe_url}. Please check backend/.env.",
        )

    db = session_factory()
    try:
        # Validate connection liveness before yielding
        db.execute(text("SELECT 1"))
        yield db
    except OperationalError as e:
        db.rollback()
        safe_url = get_sanitized_database_url()
        detail_msg = sanitize_error_message(str(e.orig) if hasattr(e, "orig") else str(e))
        raise HTTPException(
            status_code=503,
            detail=(
                f"PostgreSQL connection failed at {safe_url}. "
                "Please ensure the database server is running and credentials in backend/.env are valid. "
                f"Details: {detail_msg}"
            ),
        )
    except SQLAlchemyError as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Database error occurred: {sanitize_error_message(str(e))}",
        )
    finally:
        db.close()
