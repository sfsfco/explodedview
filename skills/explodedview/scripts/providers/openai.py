"""OpenAI image provider (gpt-image-1).

Request shape follows the documented /v1/images/generations and
/v1/images/edits endpoints. Response parsing is defensive - see
providers.base.extract_image_bytes. Not verified against a live call at build
time; `status` below is the single source of truth for that.
"""

from __future__ import annotations

import json
import mimetypes
import os
import uuid
from pathlib import Path
from typing import Any

from .base import (
    GenerationRequest,
    Provider,
    ProviderError,
    extract_image_bytes,
    http_json,
)

GENERATIONS_URL = "https://api.openai.com/v1/images/generations"
EDITS_URL = "https://api.openai.com/v1/images/edits"

DEFAULT_MODEL = "gpt-image-1"

#: Sizes gpt-image-1 accepts. `auto` lets the model choose.
VALID_SIZES = ("auto", "1024x1024", "1536x1024", "1024x1536")


class OpenAIProvider(Provider):
    name = "openai"
    env_key = "OPENAI_API_KEY"
    default_model = DEFAULT_MODEL
    supports_references = True
    status = "request shape from official docs; response parsing unverified against a live call"

    def available(self) -> bool:
        return bool(os.environ.get(self.env_key, "").strip())

    def _model(self, req: GenerationRequest) -> str:
        return req.model or self.default_model

    def _size(self, req: GenerationRequest) -> str | None:
        if not req.aspect_ratio:
            return None
        mapping = {"1:1": "1024x1024", "3:2": "1536x1024", "16:9": "1536x1024", "2:3": "1024x1536", "9:16": "1024x1536"}
        size = mapping.get(req.aspect_ratio)
        if not size:
            raise ProviderError(
                f"openai: gpt-image-1 has no size for aspect ratio {req.aspect_ratio!r}. "
                f"Pass one of {', '.join(VALID_SIZES)} via --size, or omit it."
            )
        return size

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._require_key()}",
            "Content-Type": "application/json",
        }

    def build_spec(self, req: GenerationRequest) -> dict[str, Any]:
        model = self._model(req)
        if req.references:
            return {
                "provider": self.name,
                "endpoint": "POST " + EDITS_URL,
                "note": "multipart/form-data with one file part per --reference",
                "auth_header": "Authorization: Bearer",
                "fields": {
                    "model": model,
                    "prompt": req.prompt,
                    "size": self._size(req),
                    "images": [str(Path(p)) for p in req.local_references()],
                },
            }
        body: dict[str, Any] = {"model": model, "prompt": req.prompt}
        size = self._size(req)
        if size:
            body["size"] = size
        return {
            "provider": self.name,
            "endpoint": "POST " + GENERATIONS_URL,
            "auth_header": "Authorization: Bearer",
            "body": body,
        }

    def generate(self, req: GenerationRequest) -> tuple[bytes, str]:
        if req.references:
            return self._generate_edits(req)
        spec = self.build_spec(req)
        payload = http_json(
            GENERATIONS_URL,
            self._headers(),
            json.dumps(spec["body"]).encode("utf-8"),
            timeout=req.timeout,
        )
        return extract_image_bytes(payload)

    def _generate_edits(self, req: GenerationRequest) -> tuple[bytes, str]:
        """multipart/form-data upload, built by hand to stay stdlib-only."""
        boundary = "----explodedview" + uuid.uuid4().hex
        chunks: list[bytes] = []

        def add_field(name: str, value: str) -> None:
            chunks.append(
                f"--{boundary}\r\n".encode()
                + f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
                + value.encode("utf-8")
                + b"\r\n"
            )

        add_field("model", self._model(req))
        add_field("prompt", req.prompt)
        size = self._size(req)
        if size:
            add_field("size", size)

        for path in req.local_references():
            p = Path(path)
            mime = mimetypes.guess_type(p.name)[0] or "image/png"
            chunks.append(
                f"--{boundary}\r\n".encode()
                + f'Content-Disposition: form-data; name="image[]"; filename="{p.name}"\r\n'.encode()
                + f"Content-Type: {mime}\r\n\r\n".encode()
                + p.read_bytes()
                + b"\r\n"
            )

        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)

        request_headers = {
            "Authorization": f"Bearer {self._require_key()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        payload = http_json_raw(EDITS_URL, request_headers, body, timeout=req.timeout)
        return extract_image_bytes(payload)


def http_json_raw(url: str, headers: dict[str, str], body: bytes, timeout: int):
    """POST a non-JSON (multipart) body and decode a JSON response."""
    import urllib.error
    import urllib.request

    from .base import ProviderError as _PE

    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", "replace")[:600]
        except Exception:
            pass
        raise _PE(f"POST {url} -> HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise _PE(f"POST {url} -> {exc.reason}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise _PE(f"Response was not JSON: {raw[:400]!r}") from exc
