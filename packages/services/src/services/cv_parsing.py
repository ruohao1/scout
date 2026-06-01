from __future__ import annotations

from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


class UnsupportedCVFileError(ValueError):
    pass


class EmptyCVError(ValueError):
    pass


class InvalidCVFileError(ValueError):
    pass


def extract_cv_text(filename: str, content_type: str | None, data: bytes) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix != ".pdf":
        raise UnsupportedCVFileError("Only PDF CV uploads are supported")
    if content_type and content_type not in {"application/pdf", "application/octet-stream"}:
        raise UnsupportedCVFileError("Only PDF CV uploads are supported")
    return _extract_pdf(data)


def _extract_pdf(data: bytes) -> str:
    if not data:
        raise EmptyCVError("Uploaded CV is empty")

    try:
        reader = PdfReader(BytesIO(data))
        page_text = [page.extract_text() or "" for page in reader.pages]
    except Exception as exc:
        raise InvalidCVFileError("Uploaded CV is not a readable PDF") from exc

    text = "\n\n".join(value.strip() for value in page_text if value.strip()).strip()
    if not text:
        raise EmptyCVError("Uploaded PDF has no extractable text")
    return text
