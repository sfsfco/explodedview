"""Provider registry and auto-detection.

Detection order is deliberate: prefer the provider that is already
authenticated in the host you are running in, because it needs no extra setup.

`mcode` is first because inside MiniMax Code the connector is already wired up,
so requiring a GEMINI_API_KEY or OPENAI_API_KEY would be a pointless
regression for the host this skill was written in.
"""

from __future__ import annotations

from .base import (
    GenerationRequest,
    Provider,
    ProviderError,
    ReferenceUnsupported,
    extract_image_bytes,
    read_prompt,
)
from .gemini import GeminiProvider
from .mcode import McodeProvider
from .openai import OpenAIProvider

#: Ordered by auto-detection preference.
PROVIDERS: list[Provider] = [McodeProvider(), GeminiProvider(), OpenAIProvider()]

BY_NAME: dict[str, Provider] = {p.name: p for p in PROVIDERS}

#: Providers that cannot draw, and why. Kept explicit so the CLI can give a
#: useful error instead of silently doing nothing.
NO_IMAGE_SUPPORT = {
    "anthropic": (
        "Anthropic does not offer an image-generation API - Claude models "
        "cannot produce raster images. In a Claude host, use this skill to "
        "write the prompt, then generate with --provider gemini or "
        "--provider openai."
    ),
}


def detect(auto: bool = True) -> list[Provider]:
    """Return providers that appear usable, in preference order."""
    if not auto:
        return []
    return [p for p in PROVIDERS if p.available()]


def get(name: str) -> Provider:
    key = name.strip().lower()
    if key in NO_IMAGE_SUPPORT:
        raise ProviderError(NO_IMAGE_SUPPORT[key])
    provider = BY_NAME.get(key)
    if provider is None:
        known = ", ".join(sorted(BY_NAME)) + ", auto"
        raise ProviderError(f"Unknown provider {name!r}. Known providers: {known}")
    return provider


def resolve(name: str, req: GenerationRequest | None = None) -> Provider:
    """Resolve a provider name, or auto-detect if the name is 'auto'."""
    key = name.strip().lower()
    if key != "auto":
        provider = get(key)
        if not provider.available():
            if provider.env_key:
                raise ProviderError(
                    f"{provider.name}: {provider.env_key} is not set and "
                    f"mcode-tools is not on PATH. Nothing to generate with."
                )
            raise ProviderError(f"{provider.name} is not available in this environment.")
        return provider

    available = detect()
    if not available:
        raise ProviderError(
            "No image provider available. Need one of:\n"
            "  - mcode-tools on PATH (MiniMax Code)\n"
            "  - GEMINI_API_KEY set (Gemini / Nano Banana)\n"
            "  - OPENAI_API_KEY set (gpt-image-1)\n"
            "Anthropic keys are intentionally not supported: Claude cannot "
            "generate images."
        )
    # Prefer a provider that can take the source image, if there is one.
    if req is not None and req.references:
        for provider in available:
            if provider.supports_references:
                return provider
    return available[0]


__all__ = [
    "PROVIDERS",
    "BY_NAME",
    "Provider",
    "ProviderError",
    "ReferenceUnsupported",
    "GenerationRequest",
    "extract_image_bytes",
    "read_prompt",
    "detect",
    "get",
    "resolve",
]
