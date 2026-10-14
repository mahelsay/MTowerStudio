"""Azure model clients for the fleet — Entra-only (keys disabled).

Builds an AzureOpenAI client authenticated with the studio SPN, and resolves which
data-plane endpoint actually serves the deployments (openai.azure.com vs cognitiveservices).
"""
from __future__ import annotations

from functools import lru_cache

from azure.identity import ClientSecretCredential, get_bearer_token_provider
from openai import AzureOpenAI

from . import config


@lru_cache(maxsize=1)
def _token_provider():
    auth = config.load_auth()
    cred = ClientSecretCredential(auth.tenant_id, auth.client_id, auth.client_secret)
    return get_bearer_token_provider(cred, config.AAD_SCOPE)


def _client(endpoint: str) -> AzureOpenAI:
    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_version=config.API_VERSION,
        azure_ad_token_provider=_token_provider(),
    )


@lru_cache(maxsize=1)
def get_client() -> AzureOpenAI:
    """Return an AzureOpenAI client bound to the first endpoint that answers.

    Tries each candidate endpoint with a tiny call against the reasoning deployment and
    keeps the first that works, so callers don't have to care which subdomain serves OpenAI.
    """
    last_err: Exception | None = None
    for ep in config.ENDPOINT_CANDIDATES:
        try:
            c = _client(ep)
            c.chat.completions.create(
                model=config.REASONING_DEPLOYMENT,
                messages=[{"role": "user", "content": "ping"}],
                max_completion_tokens=16,
            )
            return c
        except Exception as e:  # noqa: BLE001 — probe each endpoint, keep the working one
            last_err = e
            continue
    raise RuntimeError(f"No working OpenAI endpoint. Last error: {last_err}")


def chat(messages: list[dict], *, vision: bool = False, **kwargs) -> str:
    """One chat call. `vision=True` routes to the vision deployment (gpt-5.6-sol)."""
    client = get_client()
    model = config.VISION_DEPLOYMENT if vision else config.REASONING_DEPLOYMENT
    kwargs.setdefault("max_completion_tokens", 2048)
    resp = client.chat.completions.create(model=model, messages=messages, **kwargs)
    return resp.choices[0].message.content or ""
