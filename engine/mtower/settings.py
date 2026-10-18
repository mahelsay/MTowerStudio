"""Repository paths, local settings (.env), and JSON helpers. Standard library only."""

from __future__ import annotations

import json
import os
from pathlib import Path

ENGINE_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = ENGINE_DIR.parent          # the MTowerStudio repository (engine/, library/, productions/, media/)
STUDIO_DIR = REPO_ROOT
LIBRARY_DIR = REPO_ROOT / "library"
PRODUCTIONS_DIR = REPO_ROOT / "productions"
LEDGER_PATH = ENGINE_DIR / "ledger.jsonl"
EXTRA_CERTS = Path(__file__).resolve().parent / "certs" / "intermediates.pem"


def install_tls() -> None:
    """HTTPS for every urlopen with the system's trusted roots plus intermediates some CDNs forget to send (fal's
    v3.fal.media omits 'SSL.com TLS Issuing ECC CA R2'; Windows fetches it by itself, Python does not)."""
    import ssl
    import urllib.request
    ctx = ssl.create_default_context()
    if EXTRA_CERTS.exists():
        ctx.load_verify_locations(cafile=str(EXTRA_CERTS))
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx)))


install_tls()


def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_env(path: Path | None = None) -> None:
    """Load KEY=VALUE lines from the repo-root .env into os.environ (without overriding)."""
    path = path or REPO_ROOT / ".env"
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def secret(name: str) -> str | None:
    """Return a secret from the environment. Never print the value."""
    value = os.environ.get(name, "").strip()
    return value or None


def media_root() -> Path:
    configured = os.environ.get("MTOWER_MEDIA_ROOT", "").strip()
    return Path(configured) if configured else REPO_ROOT / "media"


def engine_config() -> dict:
    return load_json(ENGINE_DIR / "engine_config.json")
