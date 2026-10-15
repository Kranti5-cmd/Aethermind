import json
import urllib.request
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
samples_dir = BASE_DIR.parent / "samples"

boundary = "----AetherMindBoundaryTest987654"

def test_file(file_path: Path):
    with open(file_path, "rb") as f:
        file_bytes = f.read()

    body = bytearray()
    body.extend(f"--{boundary}\r\n".encode("utf-8"))
    body.extend(f'Content-Disposition: form-data; name="file"; filename="{file_path.name}"\r\n'.encode("utf-8"))
    body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
    body.extend(file_bytes)
    body.extend(b"\r\n")
    body.extend(f"--{boundary}--\r\n".encode("utf-8"))

    req = urllib.request.Request(
        "http://127.0.0.1:8000/api/documents/upload",
        data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST"
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"\n[OK] Tested '{file_path.name}' -> HTTP {resp.status}")
        print(f"     Format: {data.get('file_type')}, Size: {data.get('file_size')} bytes")
        meta = data.get("metadata", {})
        print(f"     Engine: {meta.get('engine')}, Words: {meta.get('word_count')}, Chars: {meta.get('char_count')}")
        if data.get("file_type") == "csv":
            print(f"     Columns: {meta.get('columns')}")
            print(f"     Rows ({len(meta.get('rows', []))} items): {meta.get('rows')}")

for f in ["sample_student_marks.csv", "sample_notes.txt", "sample_document.docx", "sample_report.pdf"]:
    test_file(samples_dir / f)

print("\nALL SAMPLES TESTED SUCCESSFULLY!")
