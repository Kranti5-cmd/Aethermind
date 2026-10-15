import os
import requests

API_BASE = 'http://127.0.0.1:8000'
USER_ID = 'test_user_alpha'
HEADERS = {'X-User-ID': USER_ID}

print('=== 1. Uploading Document via Document Intelligence ===')
samples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'samples'))
csv_path = os.path.join(samples_dir, 'sample_student_marks.csv')

with open(csv_path, 'rb') as f:
    upload_res = requests.post(
        f'{API_BASE}/api/documents/upload',
        files={'file': ('sample_student_marks.csv', f.read())},
        headers=HEADERS,
    )

print(f'Upload Status: {upload_res.status_code}')
upload_data = upload_res.json()
doc_id = upload_data.get('id')
print(f'Document ID: {doc_id}')
print(f'Extracted Text Length: {len(upload_data.get("extracted_text", ""))} chars')

print('\n=== 2. Verifying Document Listing in PostgreSQL ===')
list_res = requests.get(f'{API_BASE}/api/documents', headers=HEADERS)
print(f'List Status: {list_res.status_code}')
docs = list_res.json()
print(f'Found {len(docs)} documents for user {USER_ID}')
matching = [d for d in docs if d['id'] == doc_id]
assert len(matching) > 0, "Uploaded document not found in listing"
print(f'Document in DB verified: {matching[0]["filename"]} ({matching[0]["file_type"]})')

print('\n=== 3. Retrieving Single Document Details ===')
get_res = requests.get(f'{API_BASE}/api/documents/{doc_id}', headers=HEADERS)
print(f'Get Document Status: {get_res.status_code}')
assert get_res.status_code == 200
print(f'Metadata columns: {get_res.json().get("metadata", {}).get("columns")}')

print('\n=== 4. Testing Chat with Attached Document ID (Grounded Q&A) ===')
session_id = f'sess-test-{os.urandom(4).hex()}'
chat_payload = {
    'message': 'Who has the lowest mark and what is their score?',
    'session_id': session_id,
    'document_ids': [doc_id]
}
chat_res = requests.post(f'{API_BASE}/api/chat', json=chat_payload, headers=HEADERS)
print(f'Chat Status: {chat_res.status_code}')
if chat_res.status_code == 200:
    reply = chat_res.json()['reply']
    print(f'AetherMind Reply:\n{reply}\n')
else:
    print('Chat Error:', chat_res.text)

print('\n=== 5. Testing Question NOT in Document (Hallucination Prevention) ===')
chat_payload_missing = {
    'message': 'What is the capital of France and what is the school bus schedule?',
    'session_id': session_id,
    'document_ids': [doc_id]
}
missing_res = requests.post(f'{API_BASE}/api/chat', json=chat_payload_missing, headers=HEADERS)
print(f'Missing Query Status: {missing_res.status_code}')
if missing_res.status_code == 200:
    reply_missing = missing_res.json()['reply']
    print(f'Grounded Refusal Reply:\n{reply_missing}\n')
    assert "could not find" in reply_missing.lower() or "not found" in reply_missing.lower()
else:
    print('Error:', missing_res.text)

print('\n=== 6. Testing User Isolation (Unauthorized Access Prevention) ===')
unauth_headers = {'X-User-ID': 'unauthorized_attacker'}
unauth_res = requests.get(f'{API_BASE}/api/documents/{doc_id}', headers=unauth_headers)
print(f'Unauthorized GET Status: {unauth_res.status_code} (Expected 404)')
assert unauth_res.status_code == 404

print('\n=== 7. Verifying PostgreSQL Conversation & Message Persistence ===')
conv_res = requests.get(f'{API_BASE}/api/conversations/{session_id}/messages')
print(f'Conversation Retrieval Status: {conv_res.status_code}')
if conv_res.status_code == 200:
    messages = conv_res.json().get('messages', [])
    print(f'Persisted Messages Count: {len(messages)}')
    for m in messages:
        print(f'  [{m["role"]}]: {m["content"][:90]}...')

print('\n=== 8. Testing Document Deletion ===')
del_res = requests.delete(f'{API_BASE}/api/documents/{doc_id}', headers=HEADERS)
print(f'Delete Status: {del_res.status_code} (Expected 204)')
assert del_res.status_code == 204

post_del_get = requests.get(f'{API_BASE}/api/documents/{doc_id}', headers=HEADERS)
print(f'Post-Delete Status: {post_del_get.status_code} (Expected 404)')
assert post_del_get.status_code == 404

print('\n>>> ALL 8 INTEGRATION TESTS PASSED SUCCESSFULLY! <<<')
