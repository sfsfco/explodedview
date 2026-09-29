"""Shared plumbing for image-generation providers.

Deliberately stdlib-only: a skill that requires `pip install` is a skill that
half the users cannot run. Everything here uses urllib from the standard
library.

Response-shape honesty
----------------------
Request shapes are taken from official vendor documentation. *Response* shapes
could not be verified against a live call while building this (no API keys
were available at build time), so `extract_image_bytes` walks the decoded JSON
defensively instead of trusting one documented path. If it cannot find an
image it raises with the shape it saw, rather than crashing somewhere deep.
"""

from __future__ import annotations

import base64
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Keys that have ever carried inline base64 image payloads across the vendors
# we support, plus a length floor so we don't mistake short strings for images.
_IMAGE_KEY_HINTS = ("b64", "base64", "data", "bytes", "image")
_MIN_B64_LEN = 256
_B64_RE = re.compile(r"^[A-Za-z0-9+/=\s]+$")


class ProviderError(RuntimeError):
    """Anything that goes wrong talking to a provider."""


class ReferenceUnsupported(ProviderError):
    """Raised when a caller passes a source image a provider can't accept.

    This is deliberately loud. Silently dropping the reference image would
    make the generator draw an exploded view of nothing while reporting
    success, which is the worst possible failure mode for this skill.
    """


@dataclass
class GenerationRequest:
    """Everything a provider might need. Providers read what they support."""

    prompt: str
    references: list[str] = field(default_factory=list)
    model: str | None = None
    aspect_ratio: str | None = None
    timeout: int = 600

    def local_references(self) -> list[Path]:
        """References that are local files, as Paths. Remote URLs are skipped."""
        out = []
        for ref in self.references:
            p = Path(ref)
            if not p.exists():
                continue
            if p.is_file():
                out.append(p)
        return out


class Provider:
    """Base class. Subclasses implement `generate` and `build_spec`."""

    name: str = ""
    #: Environment variable holding the API key, or None if the provider
    #: authenticates some other way (e.g. via a CLI already on PATH).
    env_key: str | None = None
    default_model: str = ""
    #: Whether this provider can accept source images as input.
    supports_references: bool = False
    #: One-line human note about verification status, surfaced by --list.
    status: str = ""

    def available(self) -> bool:
        raise NotImplementedError

    def build_spec(self, req: GenerationRequest) -> dict[str, Any]:
        """Describe the request that *would* be sent. Used by --dry-run.

        Must not perform network I/O or read secrets beyond presence checks.
        """
        raise NotImplementedError

    def generate(self, req: GenerationRequest) -> tuple[bytes, str]:
        """Perform the call. Returns (image_bytes, mime_type)."""
        raise NotImplementedError

    def guard_references(self, req: GenerationRequest) -> None:
        if req.references and not self.supports_references:
            raise ReferenceUnsupported(
                f"Provider {self.name!r} cannot accept source reference images. "
                f"Drop --reference, or use --provider mcode (MiniMax Code) or "
                f"openai. Refusing to generate silently from text alone."
            )

    def _require_key(self) -> str:
        import os

        assert self.env_key, f"{self.name} has no env_key"
        key = os.environ.get(self.env_key, "").strip()
        if not key:
            raise ProviderError(
                f"{self.name}: {self.env_key} is not set. "
                f"Export it, or pass --provider auto to pick another provider."
            )
        return key


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------


def http_json(
    url: str,
    headers: dict[str, str],
    body: bytes,
    timeout: int = 600,
) -> Any:
    """POST JSON and decode the response as JSON."""
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    return _send(request, timeout, url)


def http_get_json(url: str, headers: dict[str, str], timeout: int = 120) -> Any:
    request = urllib.request.Request(url, headers=headers, method="GET")
    return _send(request, timeout, url)


def http_get_bytes(url: str, headers: dict[str, str], timeout: int = 300) -> tuple[bytes, str]:
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.read(), resp.headers.get("Content-Type", "image/png")
    except urllib.error.HTTPError as exc:  # pragma: no cover - network path
        raise ProviderError(f"GET {url} -> HTTP {exc.code}: {_read_error(exc)}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network path
        raise ProviderError(f"GET {url} -> {exc.reason}") from exc


def _send(request: urllib.request.Request, timeout: int, url: str) -> Any:
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            raw = resp.read()
    except urllib.error.HTTPError as exc:  # pragma: no cover - network path
        raise ProviderError(f"POST {url} -> HTTP {exc.code}: {_read_error(exc)}") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network path
        raise ProviderError(f"POST {url} -> {exc.reason}") from exc
    try:
        return json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        preview = raw[:400].decode("utf-8", "replace")
        raise ProviderError(f"Response was not JSON: {preview}") from exc


def _read_error(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", "replace")[:600]
    except Exception:  # pragma: no cover - defensive
        return "<unreadable error body>"


# --------------------------------------------------------------------------
# Response parsing
# --------------------------------------------------------------------------


def iter_base64_candidates(obj: Any, _key: str | None = None):
    """Yield every (key, value) string pair that could be inline base64 image data.

    Walks arbitrarily because the vendors disagree about where images live in
    a response, and the shapes are not all documented. Prefers keys that look
    image-ish, requires a plausible length and alphabet, and skips known
    non-image keys.
    """
    skip_keys = {"prompt", "text", "mimeType", "mime_type", "type", "role", "model"}
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in skip_keys:
                continue
            yield from iter_base64_candidates(value, key)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_base64_candidates(item, _key)
    elif isinstance(obj, str) and _key is not None:
        if len(obj) >= _MIN_B64_LEN and _B64_RE.match(obj):
            looks_image_ish = any(hint in _key.lower() for hint in _IMAGE_KEY_HINTS)
            if looks_image_ish:
                yield _key, obj


def extract_image_bytes(payload: Any) -> tuple[bytes, str]:
    """Pull image bytes out of a decoded JSON response.

    Raises ProviderError with a shape summary rather than a bare IndexError /
    KeyError, so a vendor shape change is diagnosable from the message alone.
    """
    for _key, b64 in iter_base64_candidates(payload):
        try:
            raw = base64.b64decode(b64, validate=False)
        except (ValueError, TypeError):
            continue
        if len(raw) > 1024:  # reject anything too small to be a real image
            return raw, _guess_mime(raw)
    raise ProviderError(
        "No image data found in the provider response. "
        f"Top-level shape was: {_describe_shape(payload)}. "
        "The vendor response format has probably changed; update this parser."
    )


def decode_b64_to_file(b64: str, out: Path) -> Path:
    raw = base64.b64decode(b64, validate=False)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(raw)
    return out


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------


def _guess_mime(raw: bytes) -> str:
    if raw[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if raw[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if raw[:4] == b"RIFF" and raw[8:12] == b"WEBP":
        return "image/webp"
    return "image/png"


def _describe_shape(obj: Any, depth: int = 0) -> str:
    """Shallow structural summary of a decoded JSON response, for error text.

    Short string values are inlined verbatim: an error reading
    `detail: "quota exceeded"` is diagnosable, `detail: str(14)` is not.
    """
    if depth > 2:
        return "..."
    if isinstance(obj, dict):
        return "{" + ", ".join(f"{k}: {_describe_shape(v, depth + 1)}" for k, v in list(obj.items())[:8]) + "}"
    if isinstance(obj, list):
        if not obj:
            return "[]"
        return f"[{len(obj)} x {_describe_shape(obj[0], depth + 1)}]"
    if isinstance(obj, str):
        if len(obj) <= 80:
            return json.dumps(obj)
        return f"str({len(obj)})"
    return type(obj).__name__


def guess_mime_for_path(path: Path) -> str:
    return {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }.get(path.suffix.lower(), "image/png")


def read_prompt(prompt: str | None, prompt_file: str | None) -> str:
    if prompt_file:
        text = Path(prompt_file).read_text(encoding="utf-8").strip()
        if not text:
            raise ProviderError(f"Prompt file {prompt_file} is empty.")
        return text
    if prompt:
        return prompt.strip()
    raise ProviderError("Provide either --prompt or --prompt-file.")
