"""OpenAI image provider (gpt-image-1).

Request shape follows the documented /v1/images/generations and
/v1/images/edits endpoints. Response parsing is defensive - see
providers.base.extract_image_bytes. Not verified against a live call at build
time; `status` below is the single source of truth for that.
"""

from __future__ import annotations

import json
import os
import uuid
from typing import Any

from .base import (
    GenerationRequest,
    Provider,
    ProviderError,
    describe_reference,
    extract_image_bytes,
    http_json,
    read_reference,
)

GENERATIONS_URL = "https://api.openai.com/v1/images/generations"
EDITS_URL = "https://api.openai.com/v1/images/edits"

DEFAULT_MODEL = "gpt-image-1"

#: The only aspect ratios gpt-image-1 can honour, mapped to its real sizes.
ASPECT_TO_SIZE = {
    "1:1": "1024x1024",
    "3:2": "1536x1024",
    "16:9": "1536x1024",
    "2:3": "1024x1536",
    "9:16": "1024x1536",
}


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
        size = ASPECT_TO_SIZE.get(req.aspect_ratio)
        if not size:
            raise ProviderError(
                f"openai: gpt-image-1 has no size for aspect ratio {req.aspect_ratio!r}. "
                f"Use one of {', '.join(ASPECT_TO_SIZE)} with --aspect-ratio, or omit it."
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
                    "image[]": [describe_reference(ref) for ref in req.references],
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

        for index, ref in enumerate(req.references):
            data, mime = read_reference(ref, timeout=req.timeout)
            filename = f"reference-{index}.{mime.rsplit('/', 1)[-1]}"
            chunks.append(
                f"--{boundary}\r\n".encode()
                + f'Content-Disposition: form-data; name="image[]"; filename="{filename}"\r\n'.encode()
                + f"Content-Type: {mime}\r\n\r\n".encode()
                + data
                + b"\r\n"
            )

        chunks.append(f"--{boundary}--\r\n".encode())
        body = b"".join(chunks)

        request_headers = {
            "Authorization": f"Bearer {self._require_key()}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
        payload = http_json(EDITS_URL, request_headers, body, timeout=req.timeout)
        return extract_image_bytes(payload)
