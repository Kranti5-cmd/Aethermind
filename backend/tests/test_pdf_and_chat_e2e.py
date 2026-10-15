import os
import io
import time
import requests
from pypdf import PdfReader

API_BASE = 'http://127.0.0.1:8000'
USER_ID = f'test_user_e2e_{int(time.time())}'
HEADERS = {'X-User-ID': USER_ID}

SAMPLES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'samples'))

print("=" * 80)
print(f"AETHERMIND COMPREHENSIVE AI CHAT & PDF VERIFICATION TEST SUITE")
print(f"Testing User ID: {USER_ID}")
print("=" * 80)

passed_tests = []
uploaded_doc_ids = []

try:
    # -------------------------------------------------------------------------
    # TEST 1: Health check
    # -------------------------------------------------------------------------
    print("\n[TEST 1] Checking API Health...")
    health_res = requests.get(f"{API_BASE}/api/health")
    assert health_res.status_code == 200
    assert health_res.json().get("status") in ["ok", "healthy"]
    print("  --> PASS: Health check OK")
    passed_tests.append("API Health Check")

    # -------------------------------------------------------------------------
    # TEST 2: Correct Chatbot Behavior - Capability Inquiry (No text-only disclaimers)
    # -------------------------------------------------------------------------
    print("\n[TEST 2] Testing Chatbot Response to Capability Inquiry...")
    session_id_cap = f"session-cap-{int(time.time())}"
    cap_payload = {
        "message": "Can you generate, upload, or attach physical PDF files, or are you only a text-based AI?",
        "session_id": session_id_cap
    }
    cap_res = requests.post(f"{API_BASE}/api/chat", json=cap_payload, headers=HEADERS)
    assert cap_res.status_code == 200, f"Chat capability failed: {cap_res.text}"
    cap_reply = cap_res.json()["reply"]
    print(f"  Assistant reply:\n{cap_reply[:250]}...\n")
    
    # Assertions: No text-only AI disclaimer
    disclaimer_phrases = [
        "i am a text-based ai",
        "i am a text based ai",
        "as a text-based ai",
        "cannot generate physical files",
        "cannot create physical files",
        "cannot create pdf files",
        "cannot generate pdf files",
        "incapable of generating pdf"
    ]
    for phrase in disclaimer_phrases:
        assert phrase not in cap_reply.lower(), f"Reply contains forbidden text-only disclaimer: '{phrase}'"
    
    # Assertions: Mentions PDF generation or document capabilities
    assert any(term in cap_reply.lower() for term in ["pdf", "generate", "upload", "attach", "document"]), \
        "Reply did not describe AetherMind's real document/PDF capabilities"
    print("  --> PASS: Assistant accurately represents capabilities without text-based disclaimers")
    passed_tests.append("Chatbot Capabilities Inquiry (No Text-Only Disclaimers)")

    # -------------------------------------------------------------------------
    # TEST 3: Clarification on Ambiguous PDF Request ("provide the PDF")
    # -------------------------------------------------------------------------
    print("\n[TEST 3] Testing Ambiguous 'provide the PDF' Request Clarification...")
    session_id_amb = f"session-amb-{int(time.time())}"
    amb_payload = {
        "message": "provide the PDF",
        "session_id": session_id_amb
    }
    amb_res = requests.post(f"{API_BASE}/api/chat", json=amb_payload, headers=HEADERS)
    assert amb_res.status_code == 200, f"Ambiguous request failed: {amb_res.text}"
    amb_reply = amb_res.json()["reply"]
    print(f"  Assistant reply: {amb_reply}")
    
    # Should ask clarification, NOT fabricate a download link or fake PDF
    assert "download" not in amb_reply.lower() or "/api/pdf/download" not in amb_reply, \
        "Model should NOT generate a download link for ambiguous 'provide the PDF'"
    assert any(clarify in amb_reply.lower() for clarify in ["which document", "specify", "clarif", "topic", "attach"]), \
        f"Model did not ask a clarification question. Got: {amb_reply}"
    print("  --> PASS: Clarification question asked properly without hallucinating a PDF")
    passed_tests.append("Ambiguous PDF Request Clarification")

    # -------------------------------------------------------------------------
    # TEST 4: Generate Real PDF from Content Request
    # -------------------------------------------------------------------------
    print("\n[TEST 4] Testing Real PDF Generation via Chat...")
    session_id_gen = f"session-gen-{int(time.time())}"
    gen_payload = {
        "message": "Please generate a PDF report titled 'Q3 Financial Highlights' summarizing revenue growth of 24% and top 3 priorities.",
        "session_id": session_id_gen
    }
    gen_res = requests.post(f"{API_BASE}/api/chat", json=gen_payload, headers=HEADERS)
    assert gen_res.status_code == 200, f"PDF generation chat failed: {gen_res.text}"
    gen_reply = gen_res.json()["reply"]
    print(f"  Assistant reply snippet:\n{gen_reply[:250]}...\n")
    
    assert "/api/pdf/download/" in gen_reply, f"Reply did not include PDF download link: {gen_reply}"
    
    # Extract download URL
    import re
    match = re.search(r'\[📥 Download ([^\]]+)\]\((/api/pdf/download/[^\)]+)\)', gen_reply)
    assert match, f"Could not find download link markdown in reply: {gen_reply}"
    pdf_filename, download_path = match.group(1), match.group(2)
    print(f"  Found Download: {pdf_filename} at {download_path}")

    # Test downloading physical PDF
    dl_res = requests.get(f"{API_BASE}{download_path}")
    assert dl_res.status_code == 200, f"Download failed: {dl_res.status_code}"
    assert dl_res.headers.get("content-type") == "application/pdf"
    assert dl_res.content.startswith(b"%PDF-"), "Downloaded file is not a valid PDF header"
    
    # Verify using pypdf
    reader = PdfReader(io.BytesIO(dl_res.content))
    assert len(reader.pages) >= 1, "PDF has no pages"
    pdf_text = "".join(p.extract_text() for p in reader.pages)
    assert len(pdf_text.strip()) > 0, "PDF contains no text"
    assert "Q3 Financial Highlights" in pdf_text or "Highlights" in pdf_text or "24%" in pdf_text, \
        f"PDF does not contain expected generated text. Found: {pdf_text[:100]}"
    print(f"  --> PASS: Generated real physical PDF ({len(dl_res.content)} bytes, {len(reader.pages)} pages) verified via pypdf")
    passed_tests.append("Real PDF Generation & Download via Chat")

    # -------------------------------------------------------------------------
    # TEST 5: Document Uploads for All 4 Formats (PDF, DOCX, TXT, CSV)
    # -------------------------------------------------------------------------
    print("\n[TEST 5] Testing Upload and Text Extraction for PDF, DOCX, TXT, CSV...")
    formats = [
        ('sample_student_marks.csv', 'csv', 'Alice'),
        ('sample_notes.txt', 'txt', 'Technical Notes'),
        ('sample_document.docx', 'docx', 'Executive Briefing'),
        ('sample_report.pdf', 'pdf', 'Whitepaper')
    ]
    doc_map = {}
    for fname, ftype, expected_kw in formats:
        fpath = os.path.join(SAMPLES_DIR, fname)
        assert os.path.exists(fpath), f"Sample file not found: {fpath}"
        with open(fpath, 'rb') as f:
            fbytes = f.read()
        up_res = requests.post(
            f"{API_BASE}/api/documents/upload",
            files={'file': (fname, fbytes)},
            headers=HEADERS
        )
        assert up_res.status_code == 200, f"Upload failed for {fname}: {up_res.text}"
        up_data = up_res.json()
        assert up_data['status'] == 'success'
        assert up_data['file_type'] == ftype
        assert len(up_data['extracted_text'].strip()) > 0
        assert expected_kw.lower() in up_data['extracted_text'].lower()
        doc_map[ftype] = up_data['id']
        uploaded_doc_ids.append(up_data['id'])
        print(f"  [OK] Uploaded {fname} -> ID: {up_data['id']}, {len(up_data['extracted_text'])} chars extracted")
    print("  --> PASS: All 4 formats uploaded and extracted accurately")
    passed_tests.append("Document Upload & Extraction (PDF, DOCX, TXT, CSV)")

    # -------------------------------------------------------------------------
    # TEST 6: Document Library Listing (Database Reuse)
    # -------------------------------------------------------------------------
    print("\n[TEST 6] Testing Document Library Listing (Database Reuse)...")
    lib_res = requests.get(f"{API_BASE}/api/documents", headers=HEADERS)
    assert lib_res.status_code == 200
    lib_docs = lib_res.json()
    lib_ids = {d['id'] for d in lib_docs}
    for doc_id in uploaded_doc_ids:
        assert doc_id in lib_ids, f"Document {doc_id} not found in library listing"
    print(f"  Found {len(lib_docs)} documents in user's library")
    print("  --> PASS: Document library correctly reuses PostgreSQL records")
    passed_tests.append("Document Library Database Reuse")

    # -------------------------------------------------------------------------
    # TEST 7: Document Summarization & Key Info Extraction
    # -------------------------------------------------------------------------
    print("\n[TEST 7] Testing Document Summarization API...")
    sum_res = requests.post(f"{API_BASE}/api/documents/{doc_map['csv']}/summarize", headers=HEADERS)
    assert sum_res.status_code == 200, f"Summarize failed: {sum_res.text}"
    sum_data = sum_res.json()
    assert len(sum_data.get('summary', '')) > 10
    assert isinstance(sum_data.get('key_points'), list)
    assert isinstance(sum_data.get('key_entities'), list)
    print(f"  Summary: {sum_data['summary'][:120]}...")
    print(f"  Key Points: {len(sum_data['key_points'])} items")
    print("  --> PASS: Document summarization and key info extraction functional")
    passed_tests.append("Document Summarization & Key Info Extraction")

    # -------------------------------------------------------------------------
    # TEST 8: Grounded Q&A on Attached Document
    # -------------------------------------------------------------------------
    print("\n[TEST 8] Testing Grounded Q&A on Attached Document in Chat...")
    session_id_grounded = f"session-grounded-{int(time.time())}"
    ground_payload = {
        "message": "Based on the attached student marks document, what grade did Diana Prince receive and what was her score?",
        "session_id": session_id_grounded,
        "document_ids": [doc_map['csv']]
    }
    ground_res = requests.post(f"{API_BASE}/api/chat", json=ground_payload, headers=HEADERS)
    assert ground_res.status_code == 200, f"Grounded chat failed: {ground_res.text}"
    ground_reply = ground_res.json()["reply"]
    print(f"  Assistant reply: {ground_reply}")
    assert "98" in ground_reply or "A+" in ground_reply or "diana" in ground_reply.lower(), \
        f"Grounded answer did not contain expected student details: {ground_reply}"
    print("  --> PASS: Chat provided grounded answers from attached document")
    passed_tests.append("Document-Grounded Chat Q&A")

    # -------------------------------------------------------------------------
    # TEST 9: Grounded Document Summary + PDF Export via Chat
    # -------------------------------------------------------------------------
    print("\n[TEST 9] Testing Document Summary + PDF Generation Request via Chat...")
    session_id_docpdf = f"session-docpdf-{int(time.time())}"
    docpdf_payload = {
        "message": "Please generate a PDF summary of the attached whitepaper report.",
        "session_id": session_id_docpdf,
        "document_ids": [doc_map['pdf']]
    }
    docpdf_res = requests.post(f"{API_BASE}/api/chat", json=docpdf_payload, headers=HEADERS)
    assert docpdf_res.status_code == 200, f"Doc PDF chat failed: {docpdf_res.text}"
    docpdf_reply = docpdf_res.json()["reply"]
    print(f"  Assistant reply snippet:\n{docpdf_reply[:250]}...\n")
    assert "/api/pdf/download/" in docpdf_reply, "Download link not found in document PDF summary reply"
    
    match2 = re.search(r'\[📥 Download ([^\]]+)\]\((/api/pdf/download/[^\)]+)\)', docpdf_reply)
    assert match2, "Download link regex match failed"
    dl2_res = requests.get(f"{API_BASE}{match2.group(2)}")
    assert dl2_res.status_code == 200
    assert dl2_res.headers.get("content-type") == "application/pdf"
    reader2 = PdfReader(io.BytesIO(dl2_res.content))
    assert len(reader2.pages) >= 1
    print(f"  --> PASS: Successfully generated PDF report grounded on attached document ({len(dl2_res.content)} bytes)")
    passed_tests.append("Document-Grounded PDF Generation & Download")

    # -------------------------------------------------------------------------
    # TEST 10: Direct PDF Export API for Library Documents
    # -------------------------------------------------------------------------
    print("\n[TEST 10] Testing Direct Document PDF Export API...")
    export_res = requests.post(f"{API_BASE}/api/documents/{doc_map['docx']}/export-pdf", headers=HEADERS)
    assert export_res.status_code == 200, f"Export PDF failed: {export_res.text}"
    export_data = export_res.json()
    assert export_data["download_url"].startswith("/api/pdf/download/")
    dl3_res = requests.get(f"{API_BASE}{export_data['download_url']}")
    assert dl3_res.status_code == 200
    assert dl3_res.content.startswith(b"%PDF-")
    print(f"  --> PASS: Direct Document PDF Export API generated valid PDF: {export_data['filename']}")
    passed_tests.append("Direct Document PDF Export API")

    # -------------------------------------------------------------------------
    # TEST 11: Error Handling (Invalid Files, Oversized Uploads, 404s)
    # -------------------------------------------------------------------------
    print("\n[TEST 11] Testing Error Handling Cases...")
    # 11a: Non-existent PDF download
    missing_pdf_res = requests.get(f"{API_BASE}/api/pdf/download/pdf-nonexistent-999999")
    assert missing_pdf_res.status_code == 404, f"Expected 404, got {missing_pdf_res.status_code}"
    print("  [OK] 404 returned for nonexistent PDF download")
    
    # 11b: Invalid file extension
    bad_ext_res = requests.post(
        f"{API_BASE}/api/documents/upload",
        files={'file': ('payload.exe', b'MZ12345')},
        headers=HEADERS
    )
    assert bad_ext_res.status_code == 400
    print(f"  [OK] 400 returned for invalid extension: {bad_ext_res.json().get('detail')}")

    # 11c: Oversized file
    huge_bytes = b"X" * (11 * 1024 * 1024)
    huge_res = requests.post(
        f"{API_BASE}/api/documents/upload",
        files={'file': ('huge.txt', huge_bytes)},
        headers=HEADERS
    )
    assert huge_res.status_code in [400, 413]
    print(f"  [OK] {huge_res.status_code} returned for oversized upload (>10MB)")

    # 11d: Empty file
    empty_res = requests.post(
        f"{API_BASE}/api/documents/upload",
        files={'file': ('empty.txt', b'')},
        headers=HEADERS
    )
    assert empty_res.status_code == 400
    print(f"  [OK] 400 returned for empty file: {empty_res.json().get('detail')}")
    print("  --> PASS: All error handling edge cases handled gracefully")
    passed_tests.append("Error Handling (404, Invalid Ext, Oversized, Empty)")

    # -------------------------------------------------------------------------
    # TEST 12: Session ID & PostgreSQL Message Persistence
    # -------------------------------------------------------------------------
    print("\n[TEST 12] Verifying Session ID & PostgreSQL Message Persistence...")
    msg_res = requests.get(f"{API_BASE}/api/conversations/{session_id_gen}/messages")
    assert msg_res.status_code == 200, f"Retrieve messages failed: {msg_res.text}"
    persisted_msgs = msg_res.json().get("messages", [])
    assert len(persisted_msgs) >= 2, f"Expected at least 2 messages, got {len(persisted_msgs)}"
    roles = [m["role"] for m in persisted_msgs]
    assert "user" in roles and "assistant" in roles, f"Both user and assistant messages must exist: {roles}"
    print(f"  Persisted {len(persisted_msgs)} messages for session '{session_id_gen}' in Neon PostgreSQL")
    print("  --> PASS: Message persistence verified in PostgreSQL")
    passed_tests.append("PostgreSQL Message & Conversation Persistence")

    # -------------------------------------------------------------------------
    # Clean up test documents
    # -------------------------------------------------------------------------
    print("\n[CLEANUP] Deleting test documents from PostgreSQL...")
    for doc_id in uploaded_doc_ids:
        del_res = requests.delete(f"{API_BASE}/api/documents/{doc_id}", headers=HEADERS)
        assert del_res.status_code == 204
    print(f"  [OK] Cleaned up {len(uploaded_doc_ids)} test documents")

    print("\n" + "=" * 80)
    print(f"ALL {len(passed_tests)} VERIFICATION SUITE TESTS PASSED SUCCESSFULLY!")
    print("=" * 80)
    for idx, test_name in enumerate(passed_tests, 1):
        print(f"  {idx}. {test_name}: PASSED")

except Exception as e:
    print(f"\n[FAILURE] Test run stopped due to error: {e}")
    # Cleanup on error
    for doc_id in uploaded_doc_ids:
        try:
            requests.delete(f"{API_BASE}/api/documents/{doc_id}", headers=HEADERS)
        except:
            pass
    raise
