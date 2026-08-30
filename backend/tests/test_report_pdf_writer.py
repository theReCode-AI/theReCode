from pathlib import Path

from app.adk.reporting.pdf_writer import write_text_pdf


def test_write_text_pdf_creates_valid_pdf_header(tmp_path: Path) -> None:
    pdf_path = tmp_path / "report.pdf"
    write_text_pdf(pdf_path, "theReCode Run Report", ["Line one", "Line two"])

    content = pdf_path.read_bytes()
    assert content.startswith(b"%PDF-1.4")
    assert b"%%EOF" in content
