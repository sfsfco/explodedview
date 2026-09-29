"""Tests for the explodedview generator.

Scope: request construction, response parsing, provider selection, and the
guard rails. These are the parts that can be verified without API keys, and
they are the parts that silently break.

NOT covered here: live calls to any provider. Nothing in this file proves
Gemini or OpenAI will accept the requests built. What it proves is that we
build the documented shape, and that a bad response fails with a message a
human can act on instead of a KeyError.

Run:  python3 -m unittest discover -s tests -v
"""

from __future__ import annotations

import base64
import json
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skills" / "explodedview" / "scripts"))

from providers import (  # noqa: E402
    NO_IMAGE_SUPPORT,
    GenerationRequest,
    ProviderError,
    ReferenceUnsupported,
    extract_image_bytes,
    resolve,
)
from providers.gemini import INTERACTIONS_URL, GeminiProvider  # noqa: E402
from providers.mcode import McodeProvider  # noqa: E402
from providers.openai import EDITS_URL, GENERATIONS_URL, OpenAIProvider  # noqa: E402

def make_png(width: int = 64, height: int = 64) -> bytes:
    """Build a real PNG large enough to clear the parser's size floor.

    Incompressible pixel data keeps it multi-KB, which is the size range an
    actual image generator returns. A 1x1 test image would be rejected by
    design, and testing around that floor would be testing the wrong thing.
    """
    import os
    import struct
    import zlib

    raw = bytearray()
    for _ in range(height):
        raw.append(0)  # PNG filter type 0 (None)
        raw.extend(os.urandom(width * 3))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 1))
        + chunk(b"IEND", b"")
    )


#: A realistic image payload, the way a provider would actually return one.
PNG = make_png()
PNG_B64 = base64.b64encode(PNG).decode("ascii")


def b64_png() -> str:
    return PNG_B64


class TestGeminiRequestShape(unittest.TestCase):
    """Locked to the shape in Google's official image-generation docs."""

    def setUp(self) -> None:
        self.p = GeminiProvider()
        self.req = GenerationRequest(prompt="exploded view of a pressure vessel")

    def test_text_only_uses_interactions_endpoint(self):
        spec = self.p.build_spec(self.req)
        self.assertEqual(spec["endpoint"], "POST " + INTERACTIONS_URL)
        self.assertEqual(spec["body"]["model"], "gemini-3.1-flash-image")
        self.assertEqual(spec["body"]["input"], "exploded view of a pressure vessel")
        self.assertEqual(spec["body"]["response_format"], {"type": "image"})

    def test_aspect_ratio_lands_in_response_format(self):
        spec = self.p.build_spec(GenerationRequest(prompt="x", aspect_ratio="16:9"))
        self.assertEqual(spec["body"]["response_format"]["aspect_ratio"], "16:9")

    def test_invalid_aspect_ratio_fails_loudly(self):
        with self.assertRaises(ProviderError) as ctx:
            self.p.build_spec(GenerationRequest(prompt="x", aspect_ratio="7:3"))
        self.assertIn("aspect_ratio", str(ctx.exception))

    def test_model_override(self):
        spec = self.p.build_spec(GenerationRequest(prompt="x", model="gemini-2.5-flash-image"))
        self.assertEqual(spec["body"]["model"], "gemini-2.5-flash-image")

    def test_references_switch_to_inline_data_path(self):
        with tempfile_reference("ref.png") as ref:
            spec = self.p.build_spec(GenerationRequest(prompt="x", references=[ref]))
        self.assertIn(":generateContent", spec["endpoint"])
        parts = spec["body"]["contents"][0]["parts"]
        self.assertEqual(parts[0]["text"], "x")
        self.assertEqual(parts[1]["inline_data"]["mime_type"], "image/png")
        base64.b64decode(parts[1]["inline_data"]["data"])  # must be valid base64


class TestOpenAIRequestShape(unittest.TestCase):
    def setUp(self) -> None:
        self.p = OpenAIProvider()
        self.req = GenerationRequest(prompt="exploded view")

    def test_text_only_uses_generations_endpoint(self):
        spec = self.p.build_spec(self.req)
        self.assertEqual(spec["endpoint"], "POST " + GENERATIONS_URL)
        self.assertEqual(spec["body"]["model"], "gpt-image-1")
        self.assertEqual(spec["body"]["prompt"], "exploded view")

    def test_aspect_ratio_maps_to_a_real_gpt_image_size(self):
        spec = self.p.build_spec(GenerationRequest(prompt="x", aspect_ratio="16:9"))
        self.assertIn(spec["body"]["size"], ("1024x1024", "1536x1024", "1024x1536"))

    def test_unmappable_aspect_ratio_explains_itself(self):
        with self.assertRaises(ProviderError) as ctx:
            self.p.build_spec(GenerationRequest(prompt="x", aspect_ratio="1:8"))
        self.assertIn("gpt-image-1 has no size", str(ctx.exception))

    def test_references_switch_to_multipart_edits(self):
        with tempfile_reference("ref.jpg") as ref:
            spec = self.p.build_spec(GenerationRequest(prompt="x", references=[ref]))
            self.assertEqual(spec["endpoint"], "POST " + EDITS_URL)
            self.assertIn("multipart/form-data", spec["note"])


class TestResponseParsing(unittest.TestCase):
    """Vendors disagree on where images live. Parse defensively or not at all."""

    def test_extracts_openai_shape(self):
        raw, mime = extract_image_bytes({"data": [{"b64_json": b64_png()}]})
        self.assertEqual(raw, PNG)
        self.assertEqual(mime, "image/png")

    def test_extracts_gemini_inline_data_shape(self):
        raw, _ = extract_image_bytes(
            {"candidates": [{"content": {"parts": [{"inlineData": {"data": b64_png()}}]}}]}
        )
        self.assertEqual(raw, PNG)

    def test_extracts_interactions_shape(self):
        raw, _ = extract_image_bytes({"output": [{"type": "image", "data": b64_png()}]})
        self.assertEqual(raw, PNG)

    def test_ignores_the_prompt_echo(self):
        """A long base64-looking prompt must never be mistaken for an image."""
        payload = {"prompt": "A" * 5000, "data": [{"b64_json": b64_png()}]}
        raw, _ = extract_image_bytes(payload)
        self.assertEqual(raw, PNG)

    def test_missing_image_raises_with_shape_not_keyerror(self):
        with self.assertRaises(ProviderError) as ctx:
            extract_image_bytes({"status": "error", "detail": "quota exceeded"})
        message = str(ctx.exception)
        self.assertIn("No image data found", message)
        self.assertIn("quota exceeded", message)  # shape is shown, so it is debuggable
        self.assertIn("status", message)

    def test_rejects_degenerate_payload(self):
        with self.assertRaises(ProviderError):
            extract_image_bytes({})


class TestReferenceGuard(unittest.TestCase):
    def test_silently_dropping_a_reference_is_refused(self):
        """The worst bug in this skill would be drawing nothing and saying OK."""
        p = OpenAIProvider()
        p.supports_references = False  # simulate an incapable provider
        with self.assertRaises(ReferenceUnsupported) as ctx:
            p.guard_references(GenerationRequest(prompt="x", references=["a.png"]))
        self.assertIn("Refusing to generate silently", str(ctx.exception))

    def test_capable_provider_passes(self):
        OpenAIProvider().guard_references(GenerationRequest(prompt="x", references=["a.png"]))


class TestProviderResolution(unittest.TestCase):
    def test_anthropic_is_rejected_with_a_real_reason(self):
        self.assertIn("anthropic", NO_IMAGE_SUPPORT)
        with self.assertRaises(ProviderError) as ctx:
            resolve("anthropic")
        message = str(ctx.exception)
        self.assertIn("image-generation API", message)
        self.assertIn("gemini", message)  # tells you what to do instead

    def test_unknown_provider_lists_the_known_ones(self):
        with self.assertRaises(ProviderError) as ctx:
            resolve("midjourney")
        self.assertIn("gemini", str(ctx.exception))

    def test_named_provider_without_credentials_fails_clearly(self):
        import os

        saved = os.environ.pop("GEMINI_API_KEY", None)
        try:
            with self.assertRaises(ProviderError) as ctx:
                resolve("gemini")
            self.assertIn("GEMINI_API_KEY", str(ctx.exception))
        finally:
            if saved is not None:
                os.environ["GEMINI_API_KEY"] = saved

    def test_auto_with_nothing_available_lists_the_requirements(self):
        import os
        import shutil

        saved = {k: os.environ.pop(k, None) for k in ("GEMINI_API_KEY", "OPENAI_API_KEY")}
        real_which = shutil.which
        shutil.which = lambda *_a, **_k: None
        try:
            with self.assertRaises(ProviderError) as ctx:
                resolve("auto")
            message = str(ctx.exception)
            self.assertIn("GEMINI_API_KEY", message)
            self.assertIn("OPENAI_API_KEY", message)
        finally:
            shutil.which = real_which
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v

    def test_auto_prefers_a_reference_capable_provider(self):
        import os
        import shutil

        saved = {k: os.environ.pop(k, None) for k in ("GEMINI_API_KEY", "OPENAI_API_KEY")}
        real_which = shutil.which
        os.environ["GEMINI_API_KEY"] = "test-key"
        shutil.which = lambda *_a, **_k: None
        try:
            chosen = resolve("auto", GenerationRequest(prompt="x", references=["a.png"]))
            self.assertEqual(chosen.name, "gemini")
            self.assertTrue(chosen.supports_references)
        finally:
            shutil.which = real_which
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


class TestMcodeHelpers(unittest.TestCase):
    def test_node_id_read_from_success_items(self):
        node = McodeProvider._find_node_id(
            {"success_items": [{"node_id": "abc123"}, {"node_id": "def456"}]}
        )
        self.assertEqual(node, "abc123")

    def test_node_id_falls_back_to_anywhere_in_the_tree(self):
        node = McodeProvider._find_node_id({"result": {"data": {"node_id": "zzz"}}})
        self.assertEqual(node, "zzz")

    def test_missing_node_id_reports_the_shape(self):
        with self.assertRaises(ProviderError) as ctx:
            McodeProvider._find_node_id({"ok": False})
        self.assertIn("success_items", str(ctx.exception))

    def test_args_payload_is_wrapped_in_a_requests_array(self):
        p = McodeProvider()
        payload = p._args_payload(GenerationRequest(prompt="x"), ["https://e.test/a.png"])
        self.assertIsInstance(payload["requests"], list)
        self.assertEqual(len(payload["requests"]), 1)
        self.assertEqual(payload["requests"][0]["reference_images"], ["https://e.test/a.png"])


class TestCliDryRun(unittest.TestCase):
    """--dry-run must never touch the network."""

    def test_dry_run_prints_request_and_exits_clean(self):
        import importlib

        generate = importlib.import_module("generate")
        import os

        os.environ["GEMINI_API_KEY"] = "test-key"
        try:
            code = generate.main(
                ["--prompt", "exploded view", "--provider", "gemini", "--dry-run"]
            )
        finally:
            os.environ.pop("GEMINI_API_KEY", None)
        self.assertEqual(code, 0)

    def test_missing_prompt_is_an_error_not_a_crash(self):
        import importlib

        generate = importlib.import_module("generate")
        self.assertEqual(generate.main(["--provider", "gemini", "--dry-run"]), 1)

    def test_list_succeeds(self):
        import importlib

        generate = importlib.import_module("generate")
        self.assertEqual(generate.main(["--list"]), 0)


class tempfile_reference:
    """Tiny context manager: makes a real file, cleans it up."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.path = None

    def __enter__(self) -> str:
        import tempfile

        fd, self.path = tempfile.mkstemp(suffix=Path(self.name).suffix)
        with open(fd, "wb") as fh:
            fh.write(PNG)
        return self.path

    def __exit__(self, *_exc) -> None:
        Path(self.path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
