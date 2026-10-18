"""ElevenLabs text-to-speech client. Standard library only."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from ..settings import engine_config, secret


class ElevenLabsError(RuntimeError):
    pass


class ElevenLabsClient:
    def __init__(self) -> None:
        cfg = engine_config()["providers"]["elevenlabs"]
        self.base = cfg["api_url"].rstrip("/")
        self.timeout = cfg["timeout_seconds"]
        key = secret(cfg["env_key"])
        if not key:
            raise ElevenLabsError(f"{cfg['env_key']} is not set. Add it to the .env file at the repository root.")
        self._key = key

    def speak(self, text: str, voice_id: str, model_id: str, voice_settings: dict, dest: Path) -> Path:
        body = json.dumps({"text": text, "model_id": model_id, "voice_settings": voice_settings}).encode("utf-8")
        req = urllib.request.Request(
            f"{self.base}/text-to-speech/{voice_id}?output_format=mp3_44100_128",
            data=body, method="POST",
            headers={"xi-api-key": self._key, "Content-Type": "application/json", "Accept": "audio/mpeg"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(resp.read())
                return dest
        except urllib.error.HTTPError as err:
            raise ElevenLabsError(f"ElevenLabs failed: HTTP {err.code} {err.read().decode('utf-8', 'replace')[:300]}") from None
