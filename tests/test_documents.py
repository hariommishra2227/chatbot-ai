import pytest

from app.services.documents import chunk_text, extract_text, sha256, validate_upload


def test_txt_validation_extraction_and_hash():
    data = b"Company support is available Monday through Friday."
    assert validate_upload("faq.txt", "text/plain", data, 1024) == "faq.txt"
    assert "Monday" in extract_text("faq.txt", data)
    assert len(sha256(data)) == 64


@pytest.mark.parametrize("name,mime,data", [
    ("bad.exe", "application/octet-stream", b"abc"),
    ("fake.pdf", "application/pdf", b"not a pdf"),
    ("fake.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", b"not zip"),
])
def test_invalid_uploads(name, mime, data):
    with pytest.raises(ValueError):
        validate_upload(name, mime, data, 1024)


def test_upload_size_limit():
    with pytest.raises(ValueError, match="upload limit"):
        validate_upload("faq.txt", "text/plain", b"x" * 11, 10)


def test_chunking_has_overlap_and_preserves_content():
    text = "A sentence. " * 300
    chunks = chunk_text(text, chunk_size=200, overlap=20)
    assert len(chunks) > 2
    assert all(0 < len(chunk) <= 201 for chunk in chunks)

