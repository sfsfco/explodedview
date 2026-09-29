#!/usr/bin/env python3
"""Vendor-neutral image generation for the explodedview skill.

The agent's job is to write a good prompt. This script's job is to turn that
prompt into a file on disk without any host-specific knowledge. That split is
the whole point: an LLM is bad at remembering CLI flags, JSON envelopes and
ID-vs-URL distinctions, and a deterministic script is not.

Usage
-----
    python3 generate.py --prompt-file prompt.txt --out exploded.png
    python3 generate.py --prompt-file prompt.txt --reference src.png \
        --provider gemini --aspect-ratio 16:9 --out exploded.png
    python3 generate.py --list
    python3 generate.py --prompt-file prompt.txt --provider gemini --dry-run

Stdlib only. No pip install, ever.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from providers import (  # noqa: E402
    NO_IMAGE_SUPPORT,
    PROVIDERS,
    GenerationRequest,
    ProviderError,
    read_prompt,
    resolve,
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_UNSUPPORTED = 3


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="generate.py",
        description="Generate an image with whichever provider is available.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Providers (auto-detected in this order):\n"
            "  mcode    MiniMax Code connector, needs mcode-tools on PATH\n"
            "  gemini   Nano Banana, needs GEMINI_API_KEY\n"
            "  openai   gpt-image-1, needs OPENAI_API_KEY\n"
            "  minimax  MiniMax image-01, needs MINIMAX_API_KEY (text-only,\n"
            "           prompt <= 1500 chars; MINIMAX_API_HOST for the China endpoint)\n"
            "\n"
            "Anthropic is deliberately absent: Claude cannot generate images.\n"
        ),
    )
    parser.add_argument("--prompt", help="Prompt text. Prefer --prompt-file; "
                                         "long prompts break when inlined in shells.")
    parser.add_argument("--prompt-file", help="File containing the prompt text.")
    parser.add_argument(
        "--reference",
        action="append",
        default=[],
        metavar="PATH_OR_URL",
        help="Source image to condition on: a local path or an http(s) URL. "
             "Repeatable. A missing file, or a provider that cannot accept "
             "references, is an error - never silently dropped.",
    )
    parser.add_argument("--out", default="exploded.png", help="Output image path.")
    parser.add_argument(
        "--provider",
        default="auto",
        help="auto (default), mcode, gemini, openai, minimax. Or anthropic to see "
             "why it is not supported.",
    )
    parser.add_argument("--model", help="Override the provider's default image model.")
    parser.add_argument("--aspect-ratio", help="e.g. 16:9, 4:3, 1:1.")
    parser.add_argument("--timeout", type=int, default=600, help="Seconds. Default 600.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the request that would be sent and exit. Makes no network call.",
    )
    parser.add_argument("--list", action="store_true", help="List providers and status.")
    return parser


def cmd_list() -> int:
    print(f"{'provider':<10} {'available':<10} {'refs':<6} {'default model':<28} status")
    print("-" * 110)
    for provider in PROVIDERS:
        print(
            f"{provider.name:<10} "
            f"{'yes' if provider.available() else 'no':<10} "
            f"{'yes' if provider.supports_references else 'no':<6} "
            f"{provider.default_model:<28} {provider.status}"
        )
    print()
    for name, reason in NO_IMAGE_SUPPORT.items():
        print(f"{name}: unsupported - {reason}")
    return EXIT_OK


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list:
        return cmd_list()

    try:
        prompt = read_prompt(args.prompt, args.prompt_file)
        req = GenerationRequest(
            prompt=prompt,
            references=args.reference,
            model=args.model,
            aspect_ratio=args.aspect_ratio,
            timeout=args.timeout,
        )
        req.validate_references()
        provider = resolve(args.provider, req)
    except ProviderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR

    if args.dry_run:
        try:
            provider.guard_references(req)
            spec = provider.build_spec(req)
        except ProviderError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return EXIT_ERROR
        print(json.dumps(spec, indent=2, default=str))
        return EXIT_OK

    try:
        provider.guard_references(req)
        print(f"Generating with {provider.name} ({provider.default_model})...", file=sys.stderr)
        image_bytes, mime = provider.generate(req)
    except ProviderError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    except Exception as exc:  # noqa: BLE001 - surface anything unexpected cleanly
        print(f"error: unexpected {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_ERROR

    out = Path(args.out).expanduser().resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(image_bytes)
    print(json.dumps({"path": str(out), "bytes": len(image_bytes), "mime": mime,
                      "provider": provider.name}, indent=2))
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
