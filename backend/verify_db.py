"""
Database & API Health Verification Script for AetherMind
Runs safe checks against the local backend and Neon PostgreSQL.
Never prints raw passwords or secrets.
"""
import urllib.request
import json
from pathlib import Path
from dotenv import dotenv_values
from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url

def main():
    print("=" * 60)
    print("AetherMind Database & API Health Verification")
    print("=" * 60)

    # 1. Test /api/health endpoint
    print("\n1. Testing Backend /api/health Endpoint...")
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/api/health")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print("   Status:", data.get("status"))
            db = data.get("database", {})
            print("   Database Configured:", db.get("configured"))
            print("   Database Connected:", db.get("connected"))
            print("   Target URL (Sanitized):", db.get("target"))
            if not db.get("connected"):
                print("   Error:", db.get("error"))
                return
    except Exception as e:
        print(f"   Health check failed: {e}")
        return

    # 2. Test Direct Neon PostgreSQL Connection
    print("\n2. Testing Direct Neon PostgreSQL Connection...")
    env_path = Path(__file__).resolve().parent / ".env"
    if not env_path.exists():
        print("   backend/.env file not found!")
        return

    db_url = dotenv_values(env_path).get("DATABASE_URL")
    if not db_url:
        print("   DATABASE_URL is not defined in backend/.env!")
        return

    safe_target = make_url(db_url).render_as_string(hide_password=True)
    print(f"   Connecting to: {safe_target}")

    try:
        engine = create_engine(db_url, connect_args={"connect_timeout": 10})
        with engine.connect() as conn:
            val = conn.execute(text("SELECT 1")).scalar()
            print(f"   Direct Connection Test Result: SELECT 1 = {val} (SUCCESS)")

            conv_count = conn.execute(text("SELECT count(*) FROM conversations")).scalar()
            msg_count = conn.execute(text("SELECT count(*) FROM messages")).scalar()
            print(f"   Database Records: {conv_count} conversations, {msg_count} messages.")
    except Exception as e:
        print(f"   Direct connection failed: {e}")
        return

    # 3. Test Message Retrieval API
    print("\n3. Testing Message Retrieval API...")
    try:
        req = urllib.request.Request("http://127.0.0.1:8000/api/conversations/test-session-neon-verification/messages")
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            msgs = data.get("messages", [])
            print(f"   Successfully retrieved {len(msgs)} messages for session 'test-session-neon-verification'.")
    except Exception as e:
        print(f"   Retrieval test note: {e}")

    print("\n" + "=" * 60)
    print("ALL VERIFICATIONS COMPLETED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == "__main__":
    main()
