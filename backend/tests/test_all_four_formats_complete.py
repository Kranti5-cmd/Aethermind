import os
import requests
import json
import time

API_BASE = 'http://127.0.0.1:8000'
USER_ID = f'test_user_{int(time.time())}'
HEADERS = {'X-User-ID': USER_ID}

SAMPLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'samples'))

FILES_TO_TEST = [
    {
        'filename': 'sample_student_marks.csv',
        'type': 'csv',
        'expected_keyword': 'Alice',
        'question': 'What score did Alice get in Math according to the document?',
    },
    {
        'filename': 'sample_notes.txt',
        'type': 'txt',
        'expected_keyword': 'Technical Notes',
        'question': 'What are the main topics discussed in these technical notes?',
    },
    {
        'filename': 'sample_document.docx',
        'type': 'docx',
        'expected_keyword': 'Executive Briefing',
        'question': 'What does this document describe?',
    },
    {
        'filename': 'sample_report.pdf',
        'type': 'pdf',
        'expected_keyword': 'Whitepaper',
        'question': 'What is the topic of this whitepaper?',
    },
]

print("=" * 70)
print(f"AETHERMIND MODULE 2 COMPLETE VERIFICATION SUITE")
print(f"Testing User: {USER_ID}")
print("=" * 70)

uploaded_doc_ids = []

try:
    # -------------------------------------------------------------
    # 1. Test PDF, DOCX, TXT, CSV Upload & Text Extraction
    # -------------------------------------------------------------
    print("\n[STEP 1] Testing Upload and Text Extraction for all 4 Formats...")
    for item in FILES_TO_TEST:
        file_path = os.path.join(SAMPLES_DIR, item['filename'])
        assert os.path.exists(file_path), f"Sample file not found: {file_path}"

        with open(file_path, 'rb') as f:
            file_bytes = f.read()

        upload_res = requests.post(
            f"{API_BASE}/api/documents/upload",
            files={'file': (item['filename'], file_bytes)},
            headers=HEADERS,
        )

        assert upload_res.status_code == 200, f"Upload failed for {item['filename']}: {upload_res.text}"
        data = upload_res.json()

        assert data['status'] == 'success'
        assert data['id'] and data['id'].startswith('doc-')
        assert data['file_type'] == item['type']
        assert data['file_size'] == len(file_bytes)
        assert len(data['extracted_text'].strip()) > 0, f"Extracted text was empty for {item['filename']}"
        assert item['expected_keyword'].lower() in data['extracted_text'].lower(), \
            f"Expected keyword '{item['expected_keyword']}' missing in {item['filename']}"

        item['doc_id'] = data['id']
        uploaded_doc_ids.append(data['id'])
        print(f"  [OK] {item['filename']} ({item['type'].upper()}): ID={data['id']}, Size={data['file_size']}B, Extracted {len(data['extracted_text'])} chars")

    # -------------------------------------------------------------
    # 2. Test Document Library Listing
    # -------------------------------------------------------------
    print("\n[STEP 2] Verifying Document Library Listing for User...")
    list_res = requests.get(f"{API_BASE}/api/documents", headers=HEADERS)
    assert list_res.status_code == 200
    docs = list_res.json()
    assert len(docs) >= 4
    listed_ids = {d['id'] for d in docs}
    for doc_id in uploaded_doc_ids:
        assert doc_id in listed_ids, f"Uploaded doc {doc_id} not in library listing"
    print(f"  [OK] Found {len(docs)} documents in PostgreSQL library for user")

    # -------------------------------------------------------------
    # 3. Test Document Summarization & Key Info Extraction (Req 7)
    # -------------------------------------------------------------
    print("\n[STEP 3] Testing Document Summarization & Key Info Extraction (Req 7)...")
    csv_doc_id = uploaded_doc_ids[0]
    sum_res = requests.post(f"{API_BASE}/api/documents/{csv_doc_id}/summarize", headers=HEADERS)
    assert sum_res.status_code == 200, f"Summarize failed: {sum_res.text}"
    sum_data = sum_res.json()
    assert sum_data['document_id'] == csv_doc_id
    assert len(sum_data['summary']) > 10, "Summary should be non-trivial"
    assert isinstance(sum_data['key_points'], list)
    assert isinstance(sum_data['key_entities'], list)
    assert isinstance(sum_data['metrics'], list)
    print(f"  [OK] Document Summary: {sum_data['summary'][:120]}...")
    print(f"  [OK] Key Points Extracted: {len(sum_data['key_points'])} items")
    print(f"  [OK] Key Entities Extracted: {sum_data['key_entities']}")
    print(f"  [OK] Metrics Extracted: {sum_data['metrics']}")

    # -------------------------------------------------------------
    # 4. Test Grounded Q&A via Chat with Attached Document ID
    # -------------------------------------------------------------
    print("\n[STEP 4] Testing Chat Grounded Q&A with Attached Document ID...")
    session_id = f"session-suite-{int(time.time())}"
    chat_payload = {
        "message": "Who scored the highest marks in Math according to the student marks document?",
        "session_id": session_id,
        "document_ids": [csv_doc_id],
    }
    chat_res = requests.post(f"{API_BASE}/api/chat", json=chat_payload, headers=HEADERS)
    assert chat_res.status_code == 200, f"Chat failed: {chat_res.text}"
    chat_data = chat_res.json()
    reply = chat_data['reply']
    assert "alice" in reply.lower(), f"Expected 'Alice' in response, got: {reply}"
    print(f"  [OK] Grounded Answer: {reply.strip()[:140]}...")

    # -------------------------------------------------------------
    # 5. Test Refusal on Information NOT in Document (Strict Grounding)
    # -------------------------------------------------------------
    print("\n[STEP 5] Testing Refusal on Non-Existent Information (Hallucination Prevention)...")
    unrelated_payload = {
        "message": "What is the capital city of Australia and what is the school bus schedule?",
        "session_id": session_id,
        "document_ids": [csv_doc_id],
    }
    unrelated_res = requests.post(f"{API_BASE}/api/chat", json=unrelated_payload, headers=HEADERS)
    assert unrelated_res.status_code == 200
    unrelated_reply = unrelated_res.json()['reply']
    assert ("could not find" in unrelated_reply.lower() or 
            "not find" in unrelated_reply.lower() or 
            "not mentioned" in unrelated_reply.lower() or 
            "provided document" in unrelated_reply.lower()), \
        f"Model did not refuse hallucination: {unrelated_reply}"
    print(f"  [OK] Refusal confirmed: {unrelated_reply.strip()[:140]}...")

    # -------------------------------------------------------------
    # 6. Test PostgreSQL Session & Message Persistence
    # -------------------------------------------------------------
    print("\n[STEP 6] Testing PostgreSQL Session and Message Persistence...")
    conv_res = requests.get(f"{API_BASE}/api/conversations/{session_id}/messages")
    assert conv_res.status_code == 200
    conv_data = conv_res.json()
    messages = conv_data.get('messages', [])
    assert len(messages) >= 4, f"Expected at least 4 messages (2 user + 2 assistant), got {len(messages)}"
    print(f"  [OK] Persisted {len(messages)} messages under session ID '{session_id}' in PostgreSQL")

    # -------------------------------------------------------------
    # 7. Test Validation: Invalid File Extensions
    # -------------------------------------------------------------
    print("\n[STEP 7] Testing Invalid File Extension Handling...")
    bad_ext_res = requests.post(
        f"{API_BASE}/api/documents/upload",
        files={'file': ('danger.exe', b"MZ\x90\x00\x03\x00\x00\x00")},
        headers=HEADERS,
    )
    assert bad_ext_res.status_code == 400
    print(f"  [OK] Successfully rejected invalid extension (HTTP 400: {bad_ext_res.json()['detail']})")

    # -------------------------------------------------------------
    # 8. Test Validation: Oversized File Upload (>10MB)
    # -------------------------------------------------------------
    print("\n[STEP 8] Testing Oversized File Upload Handling (>10MB)...")
    oversized_bytes = b"A" * (10 * 1024 * 1024 + 1024)
    oversized_res = requests.post(
        f"{API_BASE}/api/documents/upload",
        files={'file': ('huge_document.txt', oversized_bytes)},
        headers=HEADERS,
    )
    assert oversized_res.status_code == 413 or oversized_res.status_code == 400
    print(f"  [OK] Successfully rejected oversized file (HTTP {oversized_res.status_code}: {oversized_res.json()['detail']})")

    # -------------------------------------------------------------
    # 9. Test Validation: Empty File Upload
    # -------------------------------------------------------------
    print("\n[STEP 9] Testing Empty File Handling...")
    empty_res = requests.post(
        f"{API_BASE}/api/documents/upload",
        files={'file': ('empty.txt', b"")},
        headers=HEADERS,
    )
    assert empty_res.status_code == 400
    print(f"  [OK] Successfully rejected empty file (HTTP 400: {empty_res.json()['detail']})")

    # -------------------------------------------------------------
    # 10. Clean Up Test Documents & Verify Deletion
    # -------------------------------------------------------------
    print("\n[STEP 10] Cleaning up uploaded test documents...")
    for doc_id in uploaded_doc_ids:
        del_res = requests.delete(f"{API_BASE}/api/documents/{doc_id}", headers=HEADERS)
        assert del_res.status_code == 204
    print(f"  [OK] Cleaned up {len(uploaded_doc_ids)} test documents from PostgreSQL")

    print("\n" + "=" * 70)
    print(">>> ALL 10 TESTS PASSED SUCCESSFULLY! FULL WORKFLOW VERIFIED <<<")
    print("=" * 70)

except Exception as e:
    print(f"\n[ERROR] Test failed with exception: {e}")
    # Cleanup on error
    for doc_id in uploaded_doc_ids:
        try:
            requests.delete(f"{API_BASE}/api/documents/{doc_id}", headers=HEADERS)
        except:
            pass
    raise
