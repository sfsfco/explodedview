"""MiniMax image provider (image-01), called over HTTP with MINIMAX_API_KEY.

This is for MiniMax users *outside* MiniMax Code - e.g. running a MiniMax
model in Claude Code, OpenCode or Cline through an API key. Inside MiniMax
Code, the `mcode` provider is preferred and needs no key.

Request shape verified against the official docs
(https://platform.minimax.io/docs/api-reference/image-generation-t2i, checked
2026-09-29). Not verified against a live call.

Two hard limits from those docs shape this provider:

- `subject_reference` only accepts `type: "character"` (a person's face), so
  it cannot condition on an engineering drawing. The provider is therefore
  text-only, and the reference guard refuses a --reference rather than
  quietly drawing something unrelated.
- `prompt` is capped at 1500 characters. Longer prompts fail here with a
  clear message instead of an opaque API error.
"""

from __future__ import annotations

import json
import os
from typing import Any

from .base import (
    GenerationRequest,
    Provider,
    ProviderError,
    extract_image_bytes,
    http_json,
)

#: International endpoint. Mainland China accounts use https://api.minimaxi.com.
#: Overridable with MINIMAX_API_HOST, the same variable the MiniMax MCP server reads.
DEFAULT_HOST = "https://api.minimax.io"
PATH = "/v1/image_generation"

DEFAULT_MODEL = "image-01"
MAX_PROMPT_CHARS = 1500

VALID_ASPECT_RATIOS = ("1:1", "16:9", "4:3", "3:2", "2:3", "3:4", "9:16", "21:9")


class MiniMaxProvider(Provider):
    name = "minimax"
    env_key = "MINIMAX_API_KEY"
    default_model = DEFAULT_MODEL
    supports_references = False
    status = "request shape doc-verified; text-only (API references are faces only); not live-tested"

    def available(self) -> bool:
        return bool(os.environ.get(self.env_key, "").strip())

    def _url(self) -> str:
        host = os.environ.get("MINIMAX_API_HOST", "").strip() or DEFAULT_HOST
        return host.rstrip("/") + PATH

    def _body(self, req: GenerationRequest) -> dict[str, Any]:
        if len(req.prompt) > MAX_PROMPT_CHARS:
            raise ProviderError(
                f"minimax: prompt is {len(req.prompt)} characters; image-01 accepts at "
                f"most {MAX_PROMPT_CHARS}. Tighten the prompt or use another provider."
            )
        body: dict[str, Any] = {
            "model": req.model or self.default_model,
            "prompt": req.prompt,
            "response_format": "base64",
            "n": 1,
            # The optimizer rewrites the prompt; engineering fidelity needs it verbatim.
            "prompt_optimizer": False,
        }
        if req.aspect_ratio:
            if req.aspect_ratio not in VALID_ASPECT_RATIOS:
                raise ProviderError(
                    f"minimax: unsupported aspect_ratio {req.aspect_ratio!r}. "
                    f"Valid: {', '.join(VALID_ASPECT_RATIOS)}"
                )
            body["aspect_ratio"] = req.aspect_ratio
        return body

    def build_spec(self, req: GenerationRequest) -> dict[str, Any]:
        return {
            "provider": self.name,
            "endpoint": "POST " + self._url(),
            "auth_header": "Authorization: Bearer",
            "body": self._body(req),
        }

    def generate(self, req: GenerationRequest) -> tuple[bytes, str]:
        payload = http_json(
            self._url(),
            {
                "Authorization": f"Bearer {self._require_key()}",
                "Content-Type": "application/json",
            },
            json.dumps(self._body(req)).encode("utf-8"),
            timeout=req.timeout,
        )
        check_base_resp(payload)
        return extract_image_bytes(payload)


def check_base_resp(payload: Any) -> None:
    """MiniMax reports errors in `base_resp` on an HTTP 200, not via status code."""
    base = payload.get("base_resp") if isinstance(payload, dict) else None
    if isinstance(base, dict) and base.get("status_code") not in (0, None):
        raise ProviderError(
            f"minimax: API error {base.get('status_code')}: {base.get('status_msg', '')}"
        )
