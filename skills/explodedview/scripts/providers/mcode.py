"""MiniMax Code provider - drives the `mcode-tools` CLI.

This is the only provider that does not speak HTTP directly. It shells out to
`mcode-tools`, which handles connector auth and asset hosting on the user's
behalf, so no API key is needed.

Step order (matches the MiniMax Code runtime):

1. `mcode-tools upload_temp_url <path> --mime-type <mime>`  -> temp_url
   (local references only; http(s) references are passed through as-is)
2. `mcode-tools connector call connector__matrix__generate_image --args-file <f>`
   -> success_items[].node_id
3. `mcode-tools get_asset_url <node_id>`                     -> download_url
4. GET download_url

PAYLOAD CAVEAT: step 2 requires the arguments to be wrapped in a `requests`
array, but the exact inner field names (`prompt`, `reference_images`) are not
part of any public schema and have not been confirmed against the connector.
If it rejects them, `_args_payload` is the only place to change.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .base import (
    GenerationRequest,
    Provider,
    ProviderError,
    guess_mime_for_path,
    http_get_bytes,
    is_url,
)

CONNECTOR = "connector__matrix__generate_image"
DEFAULT_TIMEOUT = 600


class McodeProvider(Provider):
    name = "mcode"
    env_key = None
    default_model = "(connector-managed)"
    supports_references = True
    status = "CLI flow verified by hand in MiniMax Code; connector arg field names unconfirmed"

    def available(self) -> bool:
        return shutil.which("mcode-tools") is not None

    def build_spec(self, req: GenerationRequest) -> dict[str, Any]:
        return {
            "provider": self.name,
            "requires": "mcode-tools on PATH",
            "steps": [
                "mcode-tools upload_temp_url <path> --mime-type <mime>  "
                f"(x{sum(not is_url(r) for r in req.references)} local references)",
                f"mcode-tools connector call {CONNECTOR} --args-file <tmp.json>",
                "mcode-tools get_asset_url <node_id>",
                "GET <download_url>",
            ],
            "args_file_shape": self._args_payload(
                req, [r if is_url(r) else f"<temp_url for {r}>" for r in req.references]
            ),
        }

    def _args_payload(self, req: GenerationRequest, ref_urls: list[str]) -> dict[str, Any]:
        entry: dict[str, Any] = {"prompt": req.prompt}
        if ref_urls:
            entry["reference_images"] = ref_urls
        return {"requests": [entry]}

    # -- CLI plumbing ------------------------------------------------------

    def _run(self, argv: list[str], timeout: int = DEFAULT_TIMEOUT) -> str:
        try:
            proc = subprocess.run(
                argv, capture_output=True, text=True, timeout=timeout, check=False
            )
        except FileNotFoundError as exc:
            raise ProviderError(
                "mcode-tools not found on PATH. Install the MiniMax Code runtime "
                "or pass --provider gemini / --provider openai."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ProviderError(f"mcode-tools {argv[1]} timed out after {timeout}s") from exc
        if proc.returncode != 0:
            raise ProviderError(
                f"mcode-tools {' '.join(argv[1:])} exited {proc.returncode}: "
                f"{(proc.stderr or proc.stdout or '').strip()[:600]}"
            )
        return proc.stdout

    @staticmethod
    def _load_json(text: str) -> Any:
        text = text.strip()
        if not text:
            raise ProviderError("mcode-tools returned empty output.")
        # Some mcode-tools commands prefix JSON with non-JSON log lines.
        start = text.find("{")
        if start == -1:
            raise ProviderError(f"mcode-tools output was not JSON: {text[:300]}")
        if start > 0:
            text = text[start:]
        try:
            return json.loads(text)
        except ValueError as exc:
            raise ProviderError(f"Could not parse mcode-tools JSON: {text[:300]}") from exc

    def _upload(self, path: Path, timeout: int) -> str:
        mime = guess_mime_for_path(path)
        out = self._run(
            ["mcode-tools", "upload_temp_url", str(path), "--mime-type", mime], timeout
        )
        data = self._load_json(out)

        def find_url(node: Any) -> str | None:
            if isinstance(node, dict):
                for key in ("temp_url", "tempUrl", "url", "download_url"):
                    val = node.get(key)
                    if isinstance(val, str) and val.startswith("http"):
                        return val
                for val in node.values():
                    found = find_url(val)
                    if found:
                        return found
            elif isinstance(node, list):
                for item in node:
                    found = find_url(item)
                    if found:
                        return found
            return None

        url = find_url(data)
        if not url:
            raise ProviderError(
                f"Could not find a temp URL in upload_temp_url response. Got shape: "
                f"{json.dumps(data)[:300]}"
            )
        return url

    def generate(self, req: GenerationRequest) -> tuple[bytes, str]:
        ref_urls = [
            ref if is_url(ref) else self._upload(Path(ref).expanduser(), req.timeout)
            for ref in req.references
        ]

        args_file = None
        try:
            with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False, encoding="utf-8"
            ) as fh:
                json.dump(self._args_payload(req, ref_urls), fh)
                args_file = fh.name

            out = self._run(
                [
                    "mcode-tools",
                    "connector",
                    "call",
                    CONNECTOR,
                    "--args-file",
                    args_file,
                ],
                req.timeout,
            )
            data = self._load_json(out)

            node_id = self._find_node_id(data)
            asset_out = self._run(["mcode-tools", "get_asset_url", node_id], req.timeout)
            asset_data = self._load_json(asset_out)
            download_url = self._find_download_url(asset_data)
            return http_get_bytes(download_url, {}, timeout=req.timeout)
        finally:
            if args_file:
                Path(args_file).unlink(missing_ok=True)

    @staticmethod
    def _find_node_id(data: Any) -> str:
        items = data.get("success_items") if isinstance(data, dict) else None
        if isinstance(items, list):
            for item in items:
                if isinstance(item, dict) and isinstance(item.get("node_id"), str):
                    return item["node_id"]
        # Fall back to any node_id anywhere in the tree.
        def walk(node: Any) -> str | None:
            if isinstance(node, dict):
                if isinstance(node.get("node_id"), str):
                    return node["node_id"]
                for val in node.values():
                    found = walk(val)
                    if found:
                        return found
            elif isinstance(node, list):
                for item in node:
                    found = walk(item)
                    if found:
                        return found
            return None

        found = walk(data)
        if not found:
            raise ProviderError(
                "No node_id in the connector response. Expected "
                f"success_items[].node_id. Got shape: {json.dumps(data)[:300]}"
            )
        return found

    @staticmethod
    def _find_download_url(data: Any) -> str:
        def walk(node: Any) -> str | None:
            if isinstance(node, dict):
                for key in ("download_url", "downloadUrl", "url", "signed_url"):
                    val = node.get(key)
                    if isinstance(val, str) and val.startswith("http"):
                        return val
                for val in node.values():
                    found = walk(val)
                    if found:
                        return found
            elif isinstance(node, list):
                for item in node:
                    found = walk(item)
                    if found:
                        return found
            return None

        url = walk(data)
        if not url:
            raise ProviderError(
                f"No download URL in get_asset_url response. Got: {json.dumps(data)[:300]}"
            )
        return url
