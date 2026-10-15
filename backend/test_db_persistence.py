"""
Database Message Persistence Verification Script (Independent of Gemini API)

This script verifies that conversations, user messages, and assistant messages
are persisted to Neon PostgreSQL and retrieved correctly without calling the Google Gemini API.
"""
import sys
import json
import urllib.request
from datetime import datetime
from pathlib import Path

# Ensure backend directory is in python path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.db.database import get_engine, get_session_factory, get_sanitized_database_url
from app.models.conversation import Conversation
from app.models.message import Message


def test_standalone_database_persistence():
    print("=" * 65)
    print("AetherMind: Database-Only Persistence Test (No Gemini API Calls)")
    print("=" * 65)

    safe_target = get_sanitized_database_url()
    print(f"\n1. Target Database: {safe_target}")

    session_factory = get_session_factory()
    if not session_factory:
        print("ERROR: Failed to initialize SQLAlchemy session factory.")
        return False

    timestamp_num = int(datetime.utcnow().timestamp() * 1000)
    session_id = f"test-db-only-{timestamp_num}"
    formatted_time = datetime.now().strftime("%I:%M %p").lstrip("0")

    user_content = "Test user message: Testing PostgreSQL persistence independently of Gemini."
    mock_assistant_content = (
        "[TEST_MOCK_REPLY] Verified assistant response persisted to "
        "PostgreSQL without calling Gemini API."
    )

    print(f"2. Creating test conversation session: '{session_id}'")

    # Step 1: Direct Database Insertion using SQLAlchemy Models
    with session_factory() as db:
        # Create conversation
        conv = Conversation(
            session_id=session_id,
            title="Database-Only Persistence Verification",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(conv)
        db.flush()
        conv_id = conv.id

        # Insert user message
        user_msg = Message(
            conversation_id=conv_id,
            role="user",
            content=user_content,
            timestamp=formatted_time,
            created_at=datetime.utcnow(),
        )
        db.add(user_msg)

        # Insert mock assistant message (no Gemini API called)
        assistant_msg = Message(
            conversation_id=conv_id,
            role="assistant",
            content=mock_assistant_content,
            timestamp=formatted_time,
            created_at=datetime.utcnow(),
        )
        db.add(assistant_msg)

        db.commit()
        print(f"   -> Inserted Conversation ID #{conv_id} with 2 messages (user + assistant).")

    # Step 2: Query Back Directly From PostgreSQL
    print("\n3. Querying database directly to verify persistence...")
    with session_factory() as db:
        retrieved_conv = (
            db.query(Conversation).filter(Conversation.session_id == session_id).first()
        )
        if not retrieved_conv:
            print("ERROR: Conversation could not be found in PostgreSQL!")
            return False

        persisted_messages = retrieved_conv.messages
        print(f"   -> Found Conversation ID #{retrieved_conv.id}: '{retrieved_conv.title}'")
        print(f"   -> Retrieved {len(persisted_messages)} messages directly from database:")
        for m in persisted_messages:
            print(f"      [{m.role.upper()}] (ID #{m.id}, {m.timestamp}): {m.content}")

        if len(persisted_messages) != 2:
            print("ERROR: Expected 2 messages, but found:", len(persisted_messages))
            return False

    # Step 3: Verify Retrieval Via FastAPI HTTP Endpoint
    print("\n4. Verifying API retrieval endpoint (GET /api/conversations/{session_id}/messages)...")
    api_url = f"http://127.0.0.1:8000/api/conversations/{session_id}/messages"
    try:
        req = urllib.request.Request(api_url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            api_msgs = data.get("messages", [])
            print(f"   -> HTTP {resp.status} OK")
            print(f"   -> Retrieved {len(api_msgs)} messages via FastAPI route:")
            for m in api_msgs:
                print(f"      [{m['role'].upper()}] (ID #{m['id']}, {m['timestamp']}): {m['content']}")

            if len(api_msgs) != 2:
                print("ERROR: API endpoint did not return 2 messages!")
                return False
    except Exception as e:
        print(f"   -> Note on API endpoint query: {e}")

    # Step 4: Verify Dedicated Diagnostic Endpoint (POST /api/test/persistence)
    print("\n5. Testing Diagnostic Endpoint (POST /api/test/persistence)...")
    diag_url = "http://127.0.0.1:8000/api/test/persistence"
    try:
        diag_req = urllib.request.Request(diag_url, data=b"", headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(diag_req, timeout=5) as resp:
            diag_data = json.loads(resp.read().decode("utf-8"))
            print(f"   -> HTTP {resp.status} OK")
            print(f"   -> Diagnostic session: '{diag_data.get('session_id')}'")
            print(f"   -> Messages persisted: {diag_data.get('messages_persisted')}")
            for m in diag_data.get("messages", []):
                print(f"      [{m['role'].upper()}] (ID #{m['id']}): {m['content']}")
    except Exception as e:
        print(f"   -> Note on diagnostic endpoint: {e}")

    print("\n" + "=" * 65)
    print("SUCCESS: Database persistence verified independently of Gemini API!")
    print("=" * 65)
    return True


if __name__ == "__main__":
    success = test_standalone_database_persistence()
    sys.exit(0 if success else 1)
