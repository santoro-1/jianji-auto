from __future__ import annotations

import mimetypes
import re
import secrets
from pathlib import Path
from typing import Any, Iterator, Mapping
from urllib.parse import quote


H3_UPLOAD_CHUNK_SIZE = 1024 * 1024
_FIELD_NAME = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def _field_header(boundary: str, name: str, value: Any) -> bytes:
    if not _FIELD_NAME.fullmatch(name):
        raise ValueError("multipart 字段名不合法")
    rendered = str(value).lower() if isinstance(value, bool) else str(value)
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{name}"\r\n\r\n'
    ).encode("ascii") + rendered.encode("utf-8") + b"\r\n"


def _safe_filename(filename: str, fallback: str) -> tuple[str, str]:
    display = str(filename or fallback).replace("\r", "").replace("\n", "")
    display = display.replace('"', "").replace("\\", "_").strip() or fallback
    ascii_name = "".join(
        character if 32 <= ord(character) < 127 else "_" for character in display
    ).replace("%", "_")
    ascii_name = ascii_name.strip(" .") or "upload.bin"
    return ascii_name, quote(display, safe="!#$&+-.^_`|~")


class StreamingMultipartBody:
    """One-file multipart body whose memory use is independent of file size."""

    def __init__(
        self,
        *,
        fields: Mapping[str, Any],
        file_field: str,
        file_path: Path,
        filename: str,
        content_type: str | None = None,
        chunk_size: int = H3_UPLOAD_CHUNK_SIZE,
        boundary: str | None = None,
    ) -> None:
        if not _FIELD_NAME.fullmatch(file_field):
            raise ValueError("multipart 文件字段名不合法")
        self.file_path = Path(file_path)
        if not self.file_path.is_file():
            raise FileNotFoundError(str(self.file_path))
        self.chunk_size = min(H3_UPLOAD_CHUNK_SIZE, max(1, int(chunk_size)))
        self.boundary = boundary or f"----jyd-h3-{secrets.token_hex(16)}"
        self.content_type = f"multipart/form-data; boundary={self.boundary}"
        self._field_parts = tuple(
            _field_header(self.boundary, name, value)
            for name, value in fields.items()
        )
        ascii_name, encoded_name = _safe_filename(filename, self.file_path.name)
        mime = content_type or mimetypes.guess_type(filename)[0] or "application/octet-stream"
        self._file_header = (
            f"--{self.boundary}\r\n"
            f'Content-Disposition: form-data; name="{file_field}"; '
            f'filename="{ascii_name}"; filename*=UTF-8\'\'{encoded_name}\r\n'
            f"Content-Type: {mime}\r\n\r\n"
        ).encode("ascii")
        self._file_footer = b"\r\n"
        self._closing = f"--{self.boundary}--\r\n".encode("ascii")
        self.content_length = (
            sum(len(part) for part in self._field_parts)
            + len(self._file_header)
            + self.file_path.stat().st_size
            + len(self._file_footer)
            + len(self._closing)
        )

    def __len__(self) -> int:
        return self.content_length

    def __iter__(self) -> Iterator[bytes]:
        yield from self._field_parts
        yield self._file_header
        with self.file_path.open("rb") as source:
            while chunk := source.read(self.chunk_size):
                yield chunk
        yield self._file_footer
        yield self._closing
