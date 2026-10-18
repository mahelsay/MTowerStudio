"""Cost estimation, spending limits, and the cost ledger."""

from __future__ import annotations

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timezone

from .settings import LEDGER_PATH, engine_config


class SpendingError(RuntimeError):
    """Raised when a paid run is not allowed."""


@dataclass
class Estimate:
    model_key: str
    units: float
    unit: str
    price_usd: float | None
    extra_usd: float | None = 0.0  # helper calls billed with the job (e.g. face detection for a face pass)
    provider: str = "fal"

    @property
    def total(self) -> float | None:
        if self.price_usd is None or self.extra_usd is None:
            return None
        return round(self.units * self.price_usd + self.extra_usd, 4)


def model(model_key: str) -> dict:
    models = engine_config()["models"]
    if model_key not in models:
        raise KeyError(f"Unknown model '{model_key}'. Known: {', '.join(models)}")
    return models[model_key]


def estimate(model_key: str, units: float, extra: list[tuple[str, float]] | None = None,
             price_usd: float | None = None) -> Estimate:
    """price_usd overrides the model's unit price (e.g. a quality level); extra items may be a model key or 'usd'."""
    m = model(model_key)
    extra_usd: float | None = 0.0
    for key, n in extra or []:
        price = 1.0 if key == "usd" else model(key).get("price_usd")
        extra_usd = None if price is None or extra_usd is None else extra_usd + n * price
    return Estimate(model_key, units, m["unit"], price_usd if price_usd is not None else m.get("price_usd"), extra_usd,
                    m.get("provider", "fal"))


def budget_group(provider: str | None) -> str:
    """Azure spending has its own monthly limit (the studio's Azure budget); everything else shares the default one."""
    return "azure" if provider == "azure" else "default"


def _limit(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


def limits(group: str = "default") -> tuple[float, float]:
    """(batch limit, monthly limit) in USD for a budget group."""
    cfg = engine_config()
    defaults = cfg["budget_defaults"]
    batch = _limit("MTOWER_BATCH_LIMIT_USD", defaults["batch_limit_usd"])
    if group == "azure":
        az = cfg["providers"]["azure"]
        return batch, _limit(az.get("monthly_limit_env", "MTOWER_AZURE_MONTHLY_LIMIT_USD"), az.get("monthly_limit_usd", 0))
    return batch, _limit("MTOWER_MONTHLY_LIMIT_USD", defaults["monthly_limit_usd"])


def spent_this_month(group: str | None = None) -> float:
    """Spending recorded this month; group 'azure' / 'default' filters by budget group (None = everything)."""
    if not LEDGER_PATH.exists():
        return 0.0
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    total = 0.0
    for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        if entry.get("timestamp", "").startswith(month) and (group is None or budget_group(entry.get("provider")) == group):
            total += float(entry.get("cost_usd") or 0)
    return round(total, 4)


def authorize(estimates: list[Estimate], confirm_cost: float | None) -> float:
    """Check prices, limits, and explicit confirmation. Returns the total estimate."""
    unknown = [e.model_key for e in estimates if e.total is None]
    if unknown:
        raise SpendingError(
            f"Price not verified for: {', '.join(sorted(set(unknown)))}. "
            "Check the price on the provider's website and set price_usd in engine/engine_config.json.")
    total = round(sum(e.total for e in estimates), 4)
    batch_limit, _ = limits()
    if total > batch_limit:
        raise SpendingError(f"Estimate ${total:.2f} exceeds the batch limit ${batch_limit:.2f} (MTOWER_BATCH_LIMIT_USD).")
    for group in sorted({budget_group(e.provider) for e in estimates}):
        part = round(sum(e.total for e in estimates if budget_group(e.provider) == group), 4)
        monthly_limit = limits(group)[1]
        month = spent_this_month(group)
        if month + part > monthly_limit:
            name = "Azure" if group == "azure" else "fal/ElevenLabs"
            raise SpendingError(f"This batch (${part:.2f} on {name}) would bring this month to ${month + part:.2f}, "
                                f"over the {name} monthly limit ${monthly_limit:.2f}.")
    if confirm_cost is None:
        raise SpendingError(f"Dry run only. To spend up to ${math.ceil(total * 100) / 100:.2f}, re-run with --confirm-cost {math.ceil(total * 100) / 100:.2f}")
    if confirm_cost + 1e-9 < total:
        raise SpendingError(f"--confirm-cost ${confirm_cost:.2f} is below the estimate ${total:.2f}.")
    return total


def record(entry: dict) -> None:
    entry = {"timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"), **entry}
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
