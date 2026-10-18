"""Azure AI Foundry client (OpenAI image models on the studio's Foundry resource). Standard library only.

Signs in as the studio service principal (Entra ID client credentials from .env); the resource has keys disabled
and sits in a network security perimeter that admits only the studio PC (docs/04-azure-landing-zone.md).
"""

from __future__ import annotations

import base64
import json
import mimetypes
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ..settings import engine_config, secret


class AzureError(RuntimeError):
    pass


@dataclass
class ImageResult:
    images: list[bytes]
    usage: dict = field(default_factory=dict)
    request_id: str | None = None


def usage_cost(usage: dict, pricing: dict) -> float:
    """Actual cost of one image call from the token usage the API returns (prices per 1M tokens)."""
    details = usage.get("input_tokens_details") or {}
    text_in = details.get("text_tokens", usage.get("input_tokens", 0) - details.get("image_tokens", 0))
    image_in = details.get("image_tokens", 0)
    out = usage.get("output_tokens", 0)
    return round((text_in * pricing["text_input_per_m"] + image_in * pricing["image_input_per_m"]
                  + out * pricing["output_per_m"]) / 1_000_000, 4)


def _multipart(fields: dict[str, str], files: list[tuple[str, Path]]) -> tuple[bytes, str]:
    boundary = f"mtower-{uuid.uuid4().hex}"
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode())
    for name, path in files:
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{path.name}"\r\n'
                     f"Content-Type: {mime}\r\n\r\n".encode() + path.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


class AzureClient:
    def __init__(self) -> None:
        cfg = engine_config()["providers"]["azure"]
        self.endpoint = cfg["endpoint"].rstrip("/")
        self.api_version = cfg["api_version"]
        self.timeout = cfg.get("timeout_seconds", 300)
        self.scope = cfg.get("scope", "https://cognitiveservices.azure.com/.default")
        names = cfg["env"]
        self._tenant, self._client, self._secret = (secret(names[k]) for k in ("tenant", "client_id", "client_secret"))
        missing = [names[k] for k, v in zip(("tenant", "client_id", "client_secret"), (self._tenant, self._client, self._secret)) if not v]
        if missing:
            raise AzureError(f"{', '.join(missing)} not set. Fill the Azure section of the .env file at the repository root.")
        self._token: tuple[str, float] | None = None

    # ---- auth ----------------------------------------------------------------------
    def token(self) -> str:
        if self._token and self._token[1] > time.time() + 120:
            return self._token[0]
        body = urllib.parse.urlencode({"grant_type": "client_credentials", "client_id": self._client,
                                       "client_secret": self._secret, "scope": self.scope}).encode()
        req = urllib.request.Request(f"https://login.microsoftonline.com/{self._tenant}/oauth2/v2.0/token", data=body,
                                     method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as err:
            detail = err.read().decode("utf-8", "replace")[:300]
            raise AzureError(f"Azure sign-in failed (check AZURE_CLIENT_ID / AZURE_CLIENT_SECRET in .env): HTTP {err.code} {detail}") from None
        self._token = (data["access_token"], time.time() + int(data.get("expires_in", 3600)))
        return self._token[0]

    # ---- calls ---------------------------------------------------------------------
    def _post(self, url: str, body: bytes, content_type: str) -> dict:
        """POST once; retry only on 429 (rate limit: the request was not processed, so not billed)."""
        for attempt in range(4):
            req = urllib.request.Request(url, data=body, method="POST",
                                         headers={"Authorization": f"Bearer {self.token()}", "Content-Type": content_type})
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                    data["_request_id"] = resp.headers.get("apim-request-id") or resp.headers.get("x-request-id")
                    return data
            except urllib.error.HTTPError as err:
                detail = err.read().decode("utf-8", "replace")[:600]
                if err.code == 429 and attempt < 3:
                    wait = int(err.headers.get("Retry-After") or 30)
                    print(f"     … Azure rate limit (quota per minute); waiting {wait}s", flush=True)
                    time.sleep(wait)
                    continue
                hint = ""
                if err.code == 403 and ("network" in detail.lower() or "perimeter" in detail.lower() or "public access" in detail.lower()):
                    hint = " — your IP may have changed: run infra/scripts/Deploy-Studio.ps1 -Apply (update allowedIps in infra/bicep/main.bicepparam)"
                elif err.code in (401, 403):
                    hint = " — check the SPN's roles (infra/scripts/Grant-StudioAccess.ps1)"
                raise AzureError(f"Azure {url.split('/openai/')[-1].split('?')[0]} failed: HTTP {err.code} {detail}{hint}") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
                raise AzureError(f"Azure request failed: network error {err} (not retried: it may have been billed)") from None
        raise AzureError("Azure request failed: still rate-limited after 4 attempts")

    def images(self, deployment: str, prompt: str, references: list[Path] | None = None, n: int = 1,
               size: str = "1280x720", quality: str = "medium", output_format: str = "png",
               moderation: str | None = None) -> ImageResult:
        """Generate n images; with references, the edits endpoint uses them as visual references (up to 16).
        moderation "low" relaxes gpt-image's own output moderation (the OpenAI image-API setting; Azure accepts it)."""
        base = f"{self.endpoint}/openai/deployments/{urllib.parse.quote(deployment)}/images"
        query = f"?api-version={self.api_version}"
        extra = {"moderation": moderation} if moderation else {}
        if references:
            fields = {"prompt": prompt, "n": str(n), "size": size, "quality": quality, "output_format": output_format, **extra}
            body, ctype = _multipart(fields, [("image[]", p) for p in references[:16]])
            data = self._post(f"{base}/edits{query}", body, ctype)
        else:
            payload = {"prompt": prompt, "n": n, "size": size, "quality": quality, "output_format": output_format, **extra}
            data = self._post(f"{base}/generations{query}", json.dumps(payload).encode("utf-8"), "application/json")
        images = [base64.b64decode(item["b64_json"]) for item in data.get("data") or [] if item.get("b64_json")]
        if not images:
            raise AzureError(f"Azure returned no image (content filter or empty response): {json.dumps(data)[:300]}")
        return ImageResult(images, data.get("usage") or {}, data.get("_request_id"))

    def edit(self, deployment: str, prompt: str, images: list[Path], mask: Path | None = None, size: str = "1280x720",
             quality: str = "medium", output_format: str = "png", input_fidelity: str | None = "high",
             moderation: str | None = None) -> ImageResult:
        """Masked edit: the mask (RGBA, transparent = repaint) applies to the first image; the others are references
        (e.g. the actor's anchor portrait). input_fidelity 'high' keeps the faces of the input images closer."""
        fields = {"prompt": prompt, "n": "1", "size": size, "quality": quality, "output_format": output_format}
        if input_fidelity:
            fields["input_fidelity"] = input_fidelity
        if moderation:
            fields["moderation"] = moderation
        files = [("image[]", p) for p in images[:16]] + ([("mask", mask)] if mask else [])
        body, ctype = _multipart(fields, files)
        data = self._post(f"{self.endpoint}/openai/deployments/{urllib.parse.quote(deployment)}/images/edits"
                          f"?api-version={self.api_version}", body, ctype)
        out = [base64.b64decode(item["b64_json"]) for item in data.get("data") or [] if item.get("b64_json")]
        if not out:
            raise AzureError(f"Azure returned no image (content filter or empty response): {json.dumps(data)[:300]}")
        return ImageResult(out, data.get("usage") or {}, data.get("_request_id"))

    def flux(self, deployment: str, model_path: str, prompt: str, payload: dict) -> ImageResult:
        """Black Forest Labs FLUX on Foundry (provider API): one image per call. A refusal comes back as HTTP 200 with
        stop_reason 'refusal' and no image."""
        body = json.dumps({"model": deployment, "prompt": prompt, **payload}).encode("utf-8")
        data = self._post(f"{self.endpoint}/providers/blackforestlabs/v1/{model_path}?api-version=preview", body,
                          "application/json")
        images = [base64.b64decode(item["b64_json"]) for item in data.get("data") or [] if item.get("b64_json")]
        if not images:
            raise AzureError(f"FLUX returned no image (stop_reason {data.get('stop_reason')!r}): {json.dumps(data)[:300]}")
        return ImageResult(images, {}, data.get("_request_id"))
