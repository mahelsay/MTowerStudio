"""fal.ai queue API client (https://queue.fal.run). Standard library only."""

from __future__ import annotations

import base64
import json
import mimetypes
import time
import urllib.error
import urllib.request
from pathlib import Path

from ..settings import engine_config, secret

REST_URL = "https://rest.fal.ai"
CDN_URL = "https://v3.fal.media"


class FalError(RuntimeError):
    pass


class FalClient:
    def __init__(self) -> None:
        cfg = engine_config()["providers"]["fal"]
        self.base = cfg["queue_url"].rstrip("/")
        self.poll = cfg["poll_seconds"]
        self.timeout = cfg["timeout_seconds"]
        key = secret(cfg["env_key"])
        if not key:
            raise FalError(f"{cfg['env_key']} is not set. Add it to the .env file at the repository root.")
        self._headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}

    def _request(self, method: str, url: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        # Status/result polls (GET) are safe to repeat after a network blip; a submission (POST) is not —
        # it may already have been accepted and billed.
        attempts = 4 if method == "GET" else 1
        for attempt in range(attempts):
            req = urllib.request.Request(url, data=data, method=method, headers=self._headers)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as err:
                detail = err.read().decode("utf-8", "replace")[:500]
                if method == "GET" and err.code >= 500 and attempt + 1 < attempts:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise FalError(f"fal.ai {method} {url} failed: HTTP {err.code} {detail}") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
                if attempt + 1 < attempts:
                    time.sleep(5 * (attempt + 1))
                    continue
                raise FalError(f"fal.ai {method} {url} failed: network error {err}") from None
        raise FalError(f"fal.ai {method} {url} failed")

    def run(self, model_id: str, payload: dict, timeout: float | None = None) -> dict:
        """Submit to the queue, wait for completion, and return the result JSON."""
        submitted = self._request("POST", f"{self.base}/{model_id}", payload)
        status_url, response_url = submitted["status_url"], submitted["response_url"]
        limit = timeout or self.timeout
        hard_stop = time.time() + 3 * limit  # queue wait + work, worst case
        deadline = hard_stop
        while time.time() < min(deadline, hard_stop):
            status = self._request("GET", status_url)
            if status.get("status") == "COMPLETED":
                result = self._request("GET", response_url)
                result["_request_id"] = submitted.get("request_id")
                return result
            if status.get("status") == "IN_PROGRESS" and deadline == hard_stop:
                deadline = time.time() + limit  # the work limit starts once fal begins processing
            time.sleep(self.poll)
        raise FalError(f"Timed out waiting for {model_id} request {submitted.get('request_id')} — "
                       "it may still finish; check https://fal.ai/dashboard/requests")

    def upload(self, data: bytes, content_type: str, file_name: str, expires_seconds: int | None = None) -> str:
        """Upload bytes to fal.ai storage and return a URL that models can read.

        Same flow as the official fal-client: a short-lived CDN token, then POST to the v3 CDN;
        falls back to the storage-initiate flow.
        """
        lifecycle = json.dumps({"expiration_duration_seconds": expires_seconds}) if expires_seconds else None
        try:
            token = self._request("POST", f"{REST_URL}/storage/auth/token?storage_type=fal-cdn-v3", {})
            headers = {"Authorization": f"{token['token_type']} {token['token']}", "Content-Type": content_type,
                       "X-Fal-File-Name": file_name}
            if lifecycle:
                headers["X-Fal-Object-Lifecycle"] = lifecycle
            req = urllib.request.Request(f"{CDN_URL}/files/upload", data=data, method="POST", headers=headers)
            with urllib.request.urlopen(req, timeout=600) as resp:
                return json.loads(resp.read().decode("utf-8"))["access_url"]
        except (FalError, urllib.error.URLError, KeyError):
            headers = dict(self._headers)
            if lifecycle:
                headers["X-Fal-Object-Lifecycle-Preference"] = lifecycle
            req = urllib.request.Request(f"{REST_URL}/storage/upload/initiate?storage_type=gcs", method="POST",
                                         data=json.dumps({"file_name": file_name, "content_type": content_type}).encode(),
                                         headers=headers)
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    init = json.loads(resp.read().decode("utf-8"))
                put = urllib.request.Request(init["upload_url"], data=data, method="PUT", headers={"Content-Type": content_type})
                with urllib.request.urlopen(put, timeout=600):
                    pass
            except urllib.error.HTTPError as err:
                raise FalError(f"fal.ai upload failed: HTTP {err.code} {err.read().decode('utf-8', 'replace')[:300]}") from None
            return init["file_url"]

    def upload_file(self, path: Path, expires_seconds: int | None = None) -> str:
        mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        return self.upload(path.read_bytes(), mime, path.name, expires_seconds)


def reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as resp:
            return resp.status < 400
    except (urllib.error.URLError, ValueError):
        return False


def data_uri(path: Path) -> str:
    """Encode a local file as a data URI for model inputs that accept file URLs."""
    mime = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


def download(url: str, dest: Path) -> Path:
    """Fetch a result file; retried because the generation is already paid for."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=300) as resp:
                data = resp.read()
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError) as err:
            if attempt == 3:
                raise FalError(f"Download failed for {url}: {err}") from None
            time.sleep(5 * (attempt + 1))
    dest.write_bytes(data)
    return dest
