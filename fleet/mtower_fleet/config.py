"""Configuration for the MTower Studio agent fleet.

Loads settings from the repo-root .env (git-ignored). No secrets are logged.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# repo root = two levels up from this file (fleet/mtower_fleet/config.py -> repo root)
REPO_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(REPO_ROOT / ".env")

# Deployment names (from infra/bicep/main.bicepparam)
REASONING_DEPLOYMENT = os.getenv("MTOWER_REASONING_DEPLOYMENT", "me-eus2-gpt-5-6-terra")
VISION_DEPLOYMENT = os.getenv("MTOWER_VISION_DEPLOYMENT", "me-eus2-gpt-5-6-sol")

# Foundry custom subdomain (account name)
FOUNDRY_SUBDOMAIN = "me-eus2-mtowerstudio-fdy"

# Azure OpenAI data-plane endpoint candidates (keys disabled → Entra token auth).
# AIServices accounts usually serve OpenAI at <subdomain>.openai.azure.com; some tenants use cognitiveservices.
ENDPOINT_CANDIDATES = [
    f"https://{FOUNDRY_SUBDOMAIN}.openai.azure.com/",
    f"https://{FOUNDRY_SUBDOMAIN}.cognitiveservices.azure.com/",
]
API_VERSION = os.getenv("MTOWER_OPENAI_API_VERSION", "2025-04-01-preview")
AAD_SCOPE = "https://cognitiveservices.azure.com/.default"


@dataclass(frozen=True)
class AzureAuth:
    tenant_id: str
    client_id: str
    client_secret: str
    subscription_id: str


def load_auth() -> AzureAuth:
    """Read the SPN credentials from the environment (.env)."""
    missing = [
        k
        for k in ("AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID")
        if not os.getenv(k)
    ]
    if missing:
        raise RuntimeError(f"Missing Azure settings in .env: {', '.join(missing)}")
    return AzureAuth(
        tenant_id=os.environ["AZURE_TENANT_ID"],
        client_id=os.environ["AZURE_CLIENT_ID"],
        client_secret=os.environ["AZURE_CLIENT_SECRET"],
        subscription_id=os.environ["AZURE_SUBSCRIPTION_ID"],
    )
