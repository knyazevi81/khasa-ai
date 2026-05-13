from __future__ import annotations

import io
import logging

from pypdf import PdfReader
from pypdf.errors import PdfReadError, PdfStreamError

from app.domain.exceptions.base import AppException
from app.domain.models.llm import FileKind

logger = logging.getLogger(__name__)


class UnsupportedFileTypeError(AppException):
    code = 415
    message = "Поддерживаются только .txt и .pdf с текстовым слоем"


class FileTooLargeError(AppException):
    code = 413
    message = "Файл слишком большой"


class FileParseError(AppException):
    code = 400
    message = "Не удалось прочитать файл"


# Жёсткие лимиты — чтобы не пускать в LLM мегафайлы:
MAX_FILE_BYTES = 10 * 1024 * 1024            # 10 MB
MAX_EXTRACTED_CHARS = 200_000                 # ~50K токенов на текст


def detect_kind(filename: str, mime: str | None) -> FileKind:
    name = (filename or "").lower()
    if name.endswith(".txt") or (mime and "text/plain" in mime):
        return FileKind.TXT
    if name.endswith(".pdf") or (mime and "application/pdf" in mime):
        return FileKind.PDF
    raise UnsupportedFileTypeError()


def extract_text(data: bytes, kind: FileKind, filename: str = "") -> str:
    if len(data) > MAX_FILE_BYTES:
        raise FileTooLargeError(
            f"Размер файла {len(data) // 1024} KB превышает лимит "
            f"{MAX_FILE_BYTES // 1024 // 1024} MB"
        )

    if kind == FileKind.TXT:
        return _extract_txt(data)
    if kind == FileKind.PDF:
        return _extract_pdf(data, filename)

    raise UnsupportedFileTypeError()


# ── private ───────────────────────────────────────────────────────────────────


def _extract_txt(data: bytes) -> str:
    # Сначала пробуем utf-8, потом cp1251 как fallback для русских txt
    for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            text = data.decode(enc)
            return _truncate(text)
        except UnicodeDecodeError:
            continue
    raise FileParseError("Не удалось распознать кодировку текста")


def _extract_pdf(data: bytes, filename: str) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
    except (PdfReadError, PdfStreamError, OSError) as exc:
        raise FileParseError(f"Битый PDF: {exc}") from exc

    if reader.is_encrypted:
        # pypdf может попытаться расшифровать пустым паролем
        try:
            ok = reader.decrypt("")
        except Exception:
            ok = 0
        if not ok:
            raise FileParseError("PDF зашифрован и пароль не задан")

    parts: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            text = page.extract_text() or ""
        except Exception as exc:
            logger.warning("pdf.extract_failed file=%s page=%s err=%s", filename, i, exc)
            continue
        parts.append(text.strip())

    full = "\n\n".join(p for p in parts if p)
    if not full.strip():
        raise FileParseError(
            "В PDF не найден текстовый слой — вероятно, это скан. OCR пока не поддерживается."
        )
    return _truncate(full)


def _truncate(text: str) -> str:
    if len(text) <= MAX_EXTRACTED_CHARS:
        return text
    return text[:MAX_EXTRACTED_CHARS] + "\n\n[…текст обрезан…]"
