"""Connectivity probe: prove the SPN can call both deployed gpt-5.6 models.

Run:  python -m mtower_fleet.probe
"""
from __future__ import annotations

from . import client, config


def main() -> int:
    print("MTower Studio — fleet connectivity probe")
    print(f"  reasoning: {config.REASONING_DEPLOYMENT}")
    print(f"  vision:    {config.VISION_DEPLOYMENT}")
    try:
        c = client.get_client()
    except Exception as e:  # noqa: BLE001
        print(f"FAILED to reach any endpoint: {e}")
        return 1
    print(f"  endpoint:  {c.base_url}")

    reasoning = client.chat(
        [{"role": "user", "content": "Reply with exactly: FLEET ONLINE"}]
    )
    print(f"\n[reasoning · terra] -> {reasoning.strip()!r}")

    vision = client.chat(
        [{"role": "user", "content": "In 3 words, what is your job as an image QA reviewer?"}],
        vision=True,
    )
    print(f"[vision · sol]     -> {vision.strip()!r}")

    print("\nOK — both deployments respond with Entra-only auth.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
