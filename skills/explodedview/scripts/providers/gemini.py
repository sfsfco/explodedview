"""Google Gemini / Nano Banana provider.

Request shape verified against the official Gemini image-generation docs
(https://ai.google.dev/gemini-api/docs/image-generation, checked 2026-09-29).
Both text-only and reference-image requests go through the `interactions`
endpoint: references are extra `{"type": "image"}` input blocks, and
`response_format` (aspect ratio) applies either way. Response shape is parsed
defensively by providers.base.extract_image_bytes.

Note from those docs: Imagen is shut down and no longer served by the Gemini
API. Nano Banana models are the only image options, so they are the defaults.
"""

from __future__ import annotations

import base64
import json
import os
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

INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"

#: Nano Banana 2 - Google's recommended all-rounder for generation.
DEFAULT_MODEL = "gemini-3.1-flash-image"

#: Aspect ratios Gemini accepts. Kept explicit so a typo fails loudly.
VALID_ASPECT_RATIOS = (
    "1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4",
    "9:16", "16:9", "21:9", "1:4", "4:1", "1:8", "8:1",
)


class GeminiProvider(Provider):
    name = "gemini"
    env_key = "GEMINI_API_KEY"
    default_model = DEFAULT_MODEL
    supports_references = True
    status = "request shape doc-verified; response parsing unverified against a live call"

    def available(self) -> bool:
        return bool(os.environ.get(self.env_key, "").strip())

    def _model(self, req: GenerationRequest) -> str:
        return req.model or self.default_model

    def _headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": self._require_key(),
            "Content-Type": "application/json",
        }

    def _body(self, req: GenerationRequest, image_blocks: list[dict[str, Any]]) -> dict[str, Any]:
        response_format: dict[str, Any] = {"type": "image"}
        if req.aspect_ratio:
            if req.aspect_ratio not in VALID_ASPECT_RATIOS:
                raise ProviderError(
                    f"gemini: unsupported aspect_ratio {req.aspect_ratio!r}. "
                    f"Valid: {', '.join(VALID_ASPECT_RATIOS)}"
                )
            response_format["aspect_ratio"] = req.aspect_ratio
        if image_blocks:
            model_input: Any = [{"type": "text", "text": req.prompt}, *image_blocks]
        else:
            model_input = req.prompt
        return {
            "model": self._model(req),
            "input": model_input,
            "response_format": response_format,
        }

    def build_spec(self, req: GenerationRequest) -> dict[str, Any]:
        blocks = [
            {"type": "image", "data": describe_reference(ref), "mime_type": "<sniffed>"}
            for ref in req.references
        ]
        return {
            "provider": self.name,
            "endpoint": "POST " + INTERACTIONS_URL,
            "auth_header": "x-goog-api-key",
            "model": self._model(req),
            "body": self._body(req, blocks),
        }

    def generate(self, req: GenerationRequest) -> tuple[bytes, str]:
        blocks = []
        for ref in req.references:
            data, mime = read_reference(ref, timeout=req.timeout)
            blocks.append(
                {"type": "image", "data": base64.b64encode(data).decode("ascii"), "mime_type": mime}
            )
        payload = http_json(
            INTERACTIONS_URL,
            self._headers(),
            json.dumps(self._body(req, blocks)).encode("utf-8"),
            timeout=req.timeout,
        )
        return extract_image_bytes(payload)
