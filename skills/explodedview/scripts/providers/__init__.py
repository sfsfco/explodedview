"""Provider registry and auto-detection.

Detection order is deliberate: prefer the provider that is already
authenticated in the host you are running in, because it needs no extra setup.

`mcode` is first because inside MiniMax Code the connector is already wired up,
so requiring a GEMINI_API_KEY or OPENAI_API_KEY would be a pointless
regression for the host this skill was written in.

`minimax` (the HTTP API) is last: it cannot take the source drawing as a
reference and caps prompts at 1500 characters, so any other available
provider will produce a more faithful exploded view.
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
from .minimax import MiniMaxProvider
from .openai import OpenAIProvider

#: Ordered by auto-detection preference.
PROVIDERS: list[Provider] = [
    McodeProvider(),
    GeminiProvider(),
    OpenAIProvider(),
    MiniMaxProvider(),
]

BY_NAME: dict[str, Provider] = {p.name: p for p in PROVIDERS}

#: Providers that cannot draw, and why. Kept explicit so the CLI can give a
#: useful error instead of silently doing nothing.
NO_IMAGE_SUPPORT = {
    "anthropic": (
        "Anthropic does not offer an image-generation API - Claude models "
        "cannot produce raster images. In a Claude host, use this skill to "
        "write the prompt, then generate with --provider gemini, openai "
        "or minimax."
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
                raise ProviderError(f"{provider.name}: {provider.env_key} is not set.")
            raise ProviderError(
                f"{provider.name}: mcode-tools is not on PATH (it ships with MiniMax Code)."
            )
        return provider

    available = detect()
    if not available:
        raise ProviderError(
            "No image provider available. Need one of:\n"
            "  - mcode-tools on PATH (MiniMax Code)\n"
            "  - GEMINI_API_KEY set (Gemini / Nano Banana)\n"
            "  - OPENAI_API_KEY set (gpt-image-1)\n"
            "  - MINIMAX_API_KEY set (MiniMax image-01, text-only)\n"
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
