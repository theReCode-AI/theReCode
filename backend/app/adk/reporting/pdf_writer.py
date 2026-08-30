"""Minimal PDF writer for plain-text reports without external dependencies."""

from __future__ import annotations

from pathlib import Path


def write_text_pdf(path: Path, title: str, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_build_pdf_bytes(title, lines))


def _build_pdf_bytes(title: str, lines: list[str]) -> bytes:
    pages = _paginate_lines([title, "", *lines], page_size=48)
    objects: list[bytes] = []

    def add_object(content: str) -> int:
        objects.append(content.encode("latin-1", errors="replace"))
        return len(objects)

    font_obj = add_object("<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    page_objs: list[int] = []
    content_objs: list[int] = []

    for page_lines in pages:
        stream = _page_content_stream(page_lines)
        content_objs.append(add_object(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream"))
        page_objs.append(
            add_object(
                "<< /Type /Page /Parent 0 0 R /MediaBox [0 0 612 792] "
                f"/Contents {content_objs[-1]} 0 R "
                f"/Resources << /Font << /F1 {font_obj} 0 R >> >> >>",
            ),
        )

    kids = " ".join(f"{page_obj} 0 R" for page_obj in page_objs)
    pages_obj = add_object(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_objs)} >>")
    for page_obj in page_objs:
        page_content = objects[page_obj - 1].decode("latin-1")
        objects[page_obj - 1] = page_content.replace(
            "/Parent 0 0 R",
            f"/Parent {pages_obj} 0 R",
        ).encode("latin-1")

    catalog_obj = add_object(f"<< /Type /Catalog /Pages {pages_obj} 0 R >>")

    header = b"%PDF-1.4\n"
    body = bytearray()
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(header) + len(body))
        body.extend(f"{index} 0 obj\n".encode("latin-1"))
        body.extend(obj)
        body.extend(b"\nendobj\n")

    xref_offset = len(header) + len(body)
    xref = bytearray(b"xref\n")
    xref.extend(f"0 {len(offsets)}\n".encode("latin-1"))
    xref.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        xref.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))

    trailer = (
        f"trailer\n<< /Size {len(offsets)} /Root {catalog_obj} 0 R >>\n"
        f"startxref\n{xref_offset}\n%%EOF\n"
    )
    return header + bytes(body) + bytes(xref) + trailer.encode("latin-1")


def _paginate_lines(lines: list[str], page_size: int) -> list[list[str]]:
    if not lines:
        return [[]]
    return [lines[index : index + page_size] for index in range(0, len(lines), page_size)]


def _page_content_stream(lines: list[str]) -> str:
    commands = ["BT", "/F1 10 Tf", "14 TL", "50 760 Td"]
    for index, line in enumerate(lines):
        if index > 0:
            commands.append("T*")
        commands.append(f"({_escape_pdf_text(line)}) Tj")
    commands.append("ET")
    return "\n".join(commands)


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
