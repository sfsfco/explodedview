"""Google Gemini / Nano Banana provider.

Request shape verified against the official Gemini image-generation docs
(https://ai.google.dev/gemini-api/docs/image-generation, page last updated
2026-09-23) for the text-only `interactions` path. Response shape is parsed
defensively by providers.base.extract_image_bytes.

Note from those docs: Imagen is shut down and no longer served by the Gemini
API. Nano Banana models are the only image options, so they are the defaults.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from .base import (
    GenerationRequest,
    Provider,
    ProviderError,
    extract_image_bytes,
    guess_mime_for_path,
    http_json,
)

INTERACTIONS_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
GENERATE_CONTENT_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
)

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
        import os

        return bool(os.environ.get(self.env_key, "").strip())

    def _model(self, req: GenerationRequest) -> str:
        return req.model or self.default_model

    def _headers(self) -> dict[str, str]:
        return {
            "x-goog-api-key": self._require_key(),
            "Content-Type": "application/json",
        }

    def build_spec(self, req: GenerationRequest) -> dict[str, Any]:
        model = self._model(req)
        if req.references:
            return {
                "provider": self.name,
                "endpoint": "POST " + GENERATE_CONTENT_URL.format(model=model),
                "note": "inline reference images path (generateContent)",
                "auth_header": "x-goog-api-key",
                "model": model,
                "body": self._generate_content_body(req, model),
            }
        body: dict[str, Any] = {"model": model, "input": req.prompt}
        response_format: dict[str, Any] = {"type": "image"}
        if req.aspect_ratio:
            if req.aspect_ratio not in VALID_ASPECT_RATIOS:
                raise ProviderError(
                    f"gemini: unsupported aspect_ratio {req.aspect_ratio!r}. "
                    f"Valid: {', '.join(VALID_ASPECT_RATIOS)}"
                )
            response_format["aspect_ratio"] = req.aspect_ratio
        body["response_format"] = response_format
        return {
            "provider": self.name,
            "endpoint": "POST " + INTERACTIONS_URL,
            "note": "text-only path (interactions) - shape from official docs",
            "auth_header": "x-goog-api-key",
            "model": model,
            "body": body,
        }

    def _generate_content_body(self, req: GenerationRequest, model: str) -> dict[str, Any]:
        parts: list[dict[str, Any]] = [{"text": req.prompt}]
        for path in req.local_references():
            data = Path(path).read_bytes()
            parts.append(
                {
                    "inline_data": {
                        "mime_type": guess_mime_for_path(Path(path)),
                        "data": base64.b64encode(data).decode("ascii"),
                    }
                }
            )
        return {
            "contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"]},
        }

    def generate(self, req: GenerationRequest) -> tuple[bytes, str]:
        spec = self.build_spec(req)
        model = self._model(req)
        if req.references:
            url = GENERATE_CONTENT_URL.format(model=model)
        else:
            url = INTERACTIONS_URL
        payload = http_json(
            url,
            self._headers(),
            json.dumps(spec["body"]).encode("utf-8"),
            timeout=req.timeout,
        )
        return extract_image_bytes(payload)
