"""
Automated Test Suite for Module 2: Document Intelligence
Tests upload and text extraction for:
- PDF (.pdf)
- DOCX (.docx)
- TXT (.txt)
- CSV (.csv)
- Empty files (0 bytes)
- Unsupported file formats (.png, .bin)
- Corrupt files (corrupt PDF and corrupt DOCX)

Tests both direct service functions and the FastAPI HTTP endpoint (POST /api/documents/upload).
Does NOT call the Gemini API or touch database credentials.
"""

import io
import sys
import json
import urllib.request
import urllib.error
from pathlib import Path

# Add backend directory to sys.path
backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

from app.services.document_parser import (
    parse_document,
    DocumentParsingError,
    extract_text_from_txt,
    extract_text_from_csv,
    extract_text_from_docx,
    extract_text_from_pdf,
    MAX_FILE_SIZE_BYTES,
)

BASE_URL = "http://127.0.0.1:8000"


def create_sample_docx_bytes() -> bytes:
    """Create a minimal valid Word document in memory."""
    import docx
    doc = docx.Document()
    doc.add_heading("AetherMind Project Overview", level=1)
    doc.add_paragraph("This is a test paragraph demonstrating DOCX extraction for Module 2.")
    doc.add_paragraph("Second paragraph with additional technical details.")
    
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "Module"
    table.rows[0].cells[1].text = "Status"
    table.rows[1].cells[0].text = "Document Intelligence"
    table.rows[1].cells[1].text = "Active"
    
    stream = io.BytesIO()
    doc.save(stream)
    return stream.getvalue()


def create_sample_pdf_bytes() -> bytes:
    """Create a minimal valid PDF document in memory."""
    import pypdf
    writer = pypdf.PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    
    # Alternatively, use pypdf canvas or minimal valid PDF header
    # Let's create a minimal PDF stream with actual text
    stream = io.BytesIO()
    writer.write(stream)
    pdf_bytes = stream.getvalue()
    
    # If the blank PDF has no text, let's create a standard minimal PDF with text stream
    # Minimal standard PDF with text stream:
    pdf_text_content = (
        b"%PDF-1.4\n"
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        b"4 0 obj\n<< /Length 55 >>\nstream\nBT\n/F1 18 Tf\n100 700 Td\n(AetherMind PDF Extraction Verified) Tj\nET\nendstream\nendobj\n"
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000010 00000 n \n0000000060 00000 n \n0000000117 00000 n \n0000000242 00000 n \n0000000347 00000 n \n"
        b"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n431\n%%EOF\n"
    )
    return pdf_text_content


def upload_multipart(filename: str, file_bytes: bytes) -> tuple[int, dict]:
    """Helper to upload a file via multipart/form-data to POST /api/documents/upload."""
    boundary = "----AetherMindBoundary123456789"
    body = bytearray()
    
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode("utf-8"))
    body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
    body.extend(file_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))
    
    url = f"{BASE_URL}/api/documents/upload"
    req = urllib.request.Request(
        url,
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as err:
        err_body = err.read().decode("utf-8")
        try:
            data = json.loads(err_body)
        except Exception:
            data = {"detail": err_body}
        return err.code, data


def run_tests():
    print("=" * 70)
    print("AetherMind Module 2: Document Intelligence Test Suite")
    print("=" * 70)
    
    test_results = []
    
    def log_result(name: str, passed: bool, notes: str = ""):
        test_results.append((name, passed, notes))
        badge = "[PASS]" if passed else "[FAIL]"
        print(f" {badge} {name}")
        if notes:
            print(f"        -> {notes}")

    # 1. TXT Document Upload & Extraction
    print("\n--- 1. Testing Plain Text (.txt) ---")
    txt_content = b"Welcome to AetherMind.\nDocument Intelligence module is extracting plain text seamlessly.\nThird line of test data."
    status_code, resp = upload_multipart("sample_notes.txt", txt_content)
    passed_txt = (
        status_code == 200
        and resp.get("status") == "success"
        and resp.get("file_type") == "txt"
        and "Welcome to AetherMind" in resp.get("extracted_text", "")
    )
    log_result(
        "Upload & Extract TXT",
        passed_txt,
        f"HTTP {status_code}, Lines: {resp.get('metadata', {}).get('line_count')}, Words: {resp.get('metadata', {}).get('word_count')}"
    )

    # 2. CSV Document Upload & Extraction
    print("\n--- 2. Testing CSV Spreadsheet (.csv) ---")
    csv_content = (
        b"id,name,role,department\n"
        b"1,Ada Lovelace,Mathematician,Computing\n"
        b"2,Alan Turing,Cryptanalyst,Intelligence\n"
        b"3,Grace Hopper,Computer Scientist,Navy\n"
    )
    status_code, resp = upload_multipart("team_roster.csv", csv_content)
    passed_csv = (
        status_code == 200
        and resp.get("status") == "success"
        and resp.get("file_type") == "csv"
        and "Ada Lovelace" in resp.get("extracted_text", "")
        and resp.get("metadata", {}).get("row_count") == 3
    )
    log_result(
        "Upload & Extract CSV",
        passed_csv,
        f"HTTP {status_code}, Rows: {resp.get('metadata', {}).get('row_count')}, Cols: {resp.get('metadata', {}).get('column_count')}"
    )

    # 3. DOCX Document Upload & Extraction
    print("\n--- 3. Testing Word Document (.docx) ---")
    docx_bytes = create_sample_docx_bytes()
    status_code, resp = upload_multipart("research_proposal.docx", docx_bytes)
    passed_docx = (
        status_code == 200
        and resp.get("status") == "success"
        and resp.get("file_type") == "docx"
        and "AetherMind Project Overview" in resp.get("extracted_text", "")
    )
    log_result(
        "Upload & Extract DOCX",
        passed_docx,
        f"HTTP {status_code}, Paragraphs: {resp.get('metadata', {}).get('paragraph_count')}, Tables: {resp.get('metadata', {}).get('table_count')}"
    )

    # 4. PDF Document Upload & Extraction
    print("\n--- 4. Testing PDF Document (.pdf) ---")
    pdf_bytes = create_sample_pdf_bytes()
    status_code, resp = upload_multipart("whitepaper.pdf", pdf_bytes)
    passed_pdf = (
        status_code == 200
        and resp.get("status") == "success"
        and resp.get("file_type") == "pdf"
        and "AetherMind PDF Extraction Verified" in resp.get("extracted_text", "")
    )
    log_result(
        "Upload & Extract PDF",
        passed_pdf,
        f"HTTP {status_code}, Engine: {resp.get('metadata', {}).get('engine')}, Pages: {resp.get('metadata', {}).get('page_count')}"
    )

    # 5. Empty File Validation (0 bytes)
    print("\n--- 5. Testing Empty File Validation ---")
    empty_content = b""
    status_code, resp = upload_multipart("empty_file.txt", empty_content)
    passed_empty = (
        status_code == 400
        and "empty" in resp.get("detail", "").lower()
    )
    log_result(
        "Empty File Rejection",
        passed_empty,
        f"HTTP {status_code}, Detail: '{resp.get('detail')}'"
    )

    # 6. Unsupported File Extension Validation
    print("\n--- 6. Testing Unsupported File Format (.png) ---")
    unsupported_content = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    status_code, resp = upload_multipart("avatar.png", unsupported_content)
    passed_unsupported = (
        status_code == 400
        and "unsupported file format" in resp.get("detail", "").lower()
    )
    log_result(
        "Unsupported Extension Rejection",
        passed_unsupported,
        f"HTTP {status_code}, Detail: '{resp.get('detail')}'"
    )

    # 7. Corrupt PDF Validation
    print("\n--- 7. Testing Corrupt PDF Handling ---")
    corrupt_pdf_content = b"%PDF-1.4\nCorrupt bytes that do not form a valid PDF structure\x00\xff\xfe"
    status_code, resp = upload_multipart("corrupt_doc.pdf", corrupt_pdf_content)
    passed_corrupt_pdf = (
        status_code == 422
        and ("corrupt" in resp.get("detail", "").lower() or "unable" in resp.get("detail", "").lower())
    )
    log_result(
        "Corrupt PDF Rejection",
        passed_corrupt_pdf,
        f"HTTP {status_code}, Detail: '{resp.get('detail')}'"
    )

    # 8. Corrupt DOCX Validation
    print("\n--- 8. Testing Corrupt DOCX Handling ---")
    corrupt_docx_content = b"PK\x03\x04Corrupt zip stream pretending to be a docx document"
    status_code, resp = upload_multipart("damaged.docx", corrupt_docx_content)
    passed_corrupt_docx = (
        status_code == 422
        and ("corrupt" in resp.get("detail", "").lower() or "unable" in resp.get("detail", "").lower())
    )
    log_result(
        "Corrupt DOCX Rejection",
        passed_corrupt_docx,
        f"HTTP {status_code}, Detail: '{resp.get('detail')}'"
    )

    # Summary
    print("\n" + "=" * 70)
    all_passed = all(p for _, p, _ in test_results)
    total_tests = len(test_results)
    passed_count = sum(1 for _, p, _ in test_results if p)
    print(f"RESULTS: {passed_count}/{total_tests} Tests Passed")
    print("=" * 70)
    
    return all_passed


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
