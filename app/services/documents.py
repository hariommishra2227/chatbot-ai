import hashlib
import io
import re
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt"}
ALLOWED_CONTENT_TYPES = {
    ".pdf": {"application/pdf"},
    ".docx": {"application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
    ".txt": {"text/plain", "application/octet-stream"},
}


def validate_upload(filename: str, content_type: str | None, data: bytes, max_bytes: int) -> str:
    safe_name = Path(filename or "").name
    suffix = Path(safe_name).suffix.lower()
    if not safe_name or suffix not in ALLOWED_EXTENSIONS:
        raise ValueError("Only PDF, DOCX and TXT files are supported")
    if content_type not in ALLOWED_CONTENT_TYPES[suffix]:
        raise ValueError("The uploaded file type does not match its extension")
    if not data:
        raise ValueError("The uploaded file is empty")
    if len(data) > max_bytes:
        raise ValueError(f"File exceeds the {max_bytes // (1024 * 1024)} MB upload limit")
    if suffix == ".pdf" and not data.startswith(b"%PDF"):
        raise ValueError("Invalid PDF file")
    if suffix == ".docx" and not data.startswith(b"PK"):
        raise ValueError("Invalid DOCX file")
    return safe_name


def extract_text(filename: str, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    try:
        if suffix == ".pdf":
            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
        elif suffix == ".docx":
            doc = DocxDocument(io.BytesIO(data))
            text = "\n".join(paragraph.text for paragraph in doc.paragraphs)
        else:
            text = data.decode("utf-8-sig")
    except Exception as exc:
        raise ValueError("The document could not be read") from exc
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(text) < 10:
        raise ValueError("The document contains no extractable text")
    return text


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 180) -> list[str]:
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
            if boundary > start + chunk_size // 2:
                end = boundary + 1
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

