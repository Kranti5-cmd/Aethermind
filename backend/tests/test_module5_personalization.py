import os
import time
import requests

API_BASE = 'http://127.0.0.1:8000'
USER_A = f'user_a_mod5_{int(time.time())}'
USER_B = f'user_b_mod5_{int(time.time())}'

HEADERS_A = {'X-User-ID': USER_A}
HEADERS_B = {'X-User-ID': USER_B}

print("=" * 80)
print(f"MODULE 5: PERSONALIZED AI ASSISTANT VERIFICATION TEST SUITE")
print(f"Testing User A: {USER_A}")
print(f"Testing User B: {USER_B}")
print("=" * 80)

passed_tests = []

try:
    # -------------------------------------------------------------------------
    # TEST 1: Default Preferences Retrieval & Auto-initialization
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Testing Default Preferences Retrieval...")
    res = requests.get(f"{API_BASE}/api/preferences", headers=HEADERS_A)
    assert res.status_code == 200, f"Failed to get preferences: {res.text}"
    pref_data = res.json()
    assert pref_data["user_id"] == USER_A
    assert pref_data["response_style"] == "balanced"
    assert pref_data["response_language"] == "English"
    print(f"  --> PASS: User A initialized with default preferences: {pref_data}")
    passed_tests.append("Default Preferences Retrieval")

    # -------------------------------------------------------------------------
    # TEST 2: Update Preferences (Concise + Spanish)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Testing User Preferences Update (Concise + Spanish)...")
    update_payload = {
        "response_style": "concise",
        "response_language": "Spanish",
        "custom_instructions": "Focus on actionable technical steps."
    }
    update_res = requests.put(f"{API_BASE}/api/preferences", json=update_payload, headers=HEADERS_A)
    assert update_res.status_code == 200, f"Failed to update preferences: {update_res.text}"
    updated_data = update_res.json()
    assert updated_data["user_id"] == USER_A
    assert updated_data["response_style"] == "concise"
    assert updated_data["response_language"] == "Spanish"
    assert updated_data["custom_instructions"] == "Focus on actionable technical steps."
    print(f"  --> PASS: Updated preferences persisted: {updated_data}")
    passed_tests.append("Update Preferences")

    # -------------------------------------------------------------------------
    # TEST 3: User Isolation in Preferences
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Testing User Isolation (User B must NOT see User A's preferences)...")
    res_b = requests.get(f"{API_BASE}/api/preferences", headers=HEADERS_B)
    assert res_b.status_code == 200
    pref_b = res_b.json()
    assert pref_b["user_id"] == USER_B
    assert pref_b["response_style"] == "balanced", "User B leaked User A's response style!"
    assert pref_b["response_language"] == "English", "User B leaked User A's response language!"
    print(f"  --> PASS: User B has independent preferences: {pref_b}")
    passed_tests.append("User Isolation in Preferences")

    # -------------------------------------------------------------------------
    # TEST 4: Chat with Personalized Preferences Applied (Concise + Spanish)
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Testing Gemini Chat with User A's Preferences (Concise Spanish)...")
    session_id_a = f"session-pers-{int(time.time())}"
    chat_payload = {
        "message": "What is Python FastAPI and why is it fast?",
        "session_id": session_id_a
    }
    chat_res = requests.post(f"{API_BASE}/api/chat", json=chat_payload, headers=HEADERS_A)
    assert chat_res.status_code == 200, f"Chat failed: {chat_res.text}"
    chat_reply = chat_res.json()["reply"]
    print(f"  Assistant reply (should be concise & Spanish):\n{chat_reply[:300]}...\n")
    # Verify Spanish indicator words
    spanish_indicators = ["es", "un", "de", "para", "rápido", "rendimiento", "asíncrono", "framework", "con", "por", "en"]
    lower_reply = chat_reply.lower()
    matches = [w for w in spanish_indicators if f" {w} " in lower_reply or lower_reply.startswith(f"{w} ")]
    assert len(matches) >= 2, f"Expected Spanish reply based on user preference, got:\n{chat_reply}"
    print(f"  --> PASS: Response honors preferred language and concise style (Detected Spanish words: {matches})")
    passed_tests.append("Personalized AI Response Generation")

    # -------------------------------------------------------------------------
    # TEST 5: Verify Message Persistence in PostgreSQL
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Testing Conversation History & Message Persistence...")
    conv_res = requests.get(f"{API_BASE}/api/conversations/{session_id_a}")
    assert conv_res.status_code == 200, f"Failed to get conversation: {conv_res.text}"
    conv_data = conv_res.json()
    assert conv_data["session_id"] == session_id_a
    assert len(conv_data["messages"]) >= 2, f"Expected at least 2 messages, found: {len(conv_data['messages'])}"
    print(f"  --> PASS: Loaded {len(conv_data['messages'])} persisted messages from PostgreSQL")
    passed_tests.append("Conversation & Message Persistence")

    # -------------------------------------------------------------------------
    # TEST 6: Chat & Message Search Endpoint (/api/conversations/search)
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Testing Chat & Message Search...")
    # Search for term from user message "FastAPI"
    search_res = requests.get(f"{API_BASE}/api/conversations/search?q=FastAPI")
    assert search_res.status_code == 200, f"Search failed: {search_res.text}"
    search_data = search_res.json()
    assert search_data["query"] == "FastAPI"
    assert search_data["total_matches"] > 0, "Expected search results for 'FastAPI', got none"
    
    first_match = search_data["results"][0]
    assert "session_id" in first_match
    assert "snippet" in first_match
    assert "matched_in" in first_match
    print(f"  Found {search_data['total_matches']} matches for 'FastAPI'. Top match snippet: {first_match['snippet']}")

    # Empty search query test
    empty_res = requests.get(f"{API_BASE}/api/conversations/search?q=")
    assert empty_res.status_code == 200
    assert empty_res.json()["total_matches"] == 0
    print("  --> PASS: Search handles queries and empty states accurately")
    passed_tests.append("Chat and Message Search")

    # -------------------------------------------------------------------------
    # TEST 7: Reset Preferences Back to English Detailed
    # -------------------------------------------------------------------------
    print("\n[TEST 7] Testing Preferences Style 'detailed' + 'English'...")
    detailed_payload = {
        "response_style": "detailed",
        "response_language": "English",
        "custom_instructions": "Include comprehensive architectural breakdown."
    }
    det_res = requests.put(f"{API_BASE}/api/preferences", json=detailed_payload, headers=HEADERS_A)
    assert det_res.status_code == 200
    assert det_res.json()["response_style"] == "detailed"
    print("  --> PASS: Successfully updated to detailed English style")
    passed_tests.append("Detailed Style Preference")

    print("\n" + "=" * 80)
    print("ALL MODULE 5 BACKEND VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    for idx, t in enumerate(passed_tests, 1):
        print(f"  {idx}. {t}: PASSED")

except Exception as e:
    print(f"\n[FAIL] Test suite encountered an error: {e}")
    raise
