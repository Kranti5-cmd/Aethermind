import os
import requests

API_BASE = 'http://127.0.0.1:8000'

print('=== 1. Testing Document Extraction API for All Supported Formats ===')
samples_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'samples'))

for fname in ['sample_student_marks.csv', 'sample_notes.txt', 'sample_document.docx', 'sample_report.pdf']:
    fpath = os.path.join(samples_dir, fname)
    if not os.path.exists(fpath):
        print(f'Warning: {fpath} not found')
        continue
    with open(fpath, 'rb') as f:
        res = requests.post(f'{API_BASE}/api/documents/upload', files={'file': (fname, f.read())})
    text_len = len(res.json().get('extracted_text', ''))
    print(f'{fname}: HTTP {res.status_code} - Text Length: {text_len} chars')

print('\n=== 2. Testing Invalid / Unsupported File Types ===')
res_invalid = requests.post(f'{API_BASE}/api/documents/upload', files={'file': ('bad_file.exe', b'fake binary')})
print(f'bad_file.exe -> Status: {res_invalid.status_code}, Detail: {res_invalid.json().get("detail")}')

print('\n=== 3. Testing Empty File Upload ===')
res_empty = requests.post(f'{API_BASE}/api/documents/upload', files={'file': ('empty.txt', b'')})
print(f'empty.txt -> Status: {res_empty.status_code}, Detail: {res_empty.json().get("detail")}')

print('\n=== 4. Testing Chat Q&A with Attached Document ===')
chat_payload = {
    'message': 'Summarize the highest grade student from this document in one sentence.',
    'session_id': 'test-doc-summary-1',
    'documents': [
        {
            'name': 'sample_student_marks.csv',
            'type': 'csv',
            'extracted_text': 'StudentID,Name,Subject,Score,Grade\n101,Alice Johnson,Mathematics,94,A\n104,Diana Prince,Mathematics,98,A+',
            'size': 95
        }
    ]
}
chat_res = requests.post(f'{API_BASE}/api/chat', json=chat_payload)
print(f'Chat Status: {chat_res.status_code}')
if chat_res.status_code == 200:
    print('Reply:', chat_res.json()['reply'])
else:
    print('Error:', chat_res.text)

print('\n=== 5. Verifying Message Persistence in PostgreSQL ===')
msg_res = requests.get(f'{API_BASE}/api/conversations/test-doc-summary-1/messages')
print(f'Retrieve Messages Status: {msg_res.status_code}')
if msg_res.status_code == 200:
    msgs = msg_res.json().get('messages', [])
    print(f'Persisted messages count: {len(msgs)}')
    for m in msgs:
        print(f'  [{m["role"]}]: {m["content"][:100]}...')
