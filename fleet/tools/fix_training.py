"""Phase D helper: audit one actor's training set, reject drifted/defective keys, re-roll them with the identity
model. Usage: python fix_training.py ACT-0003 [--apply]   (without --apply: audit + show the plan only)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fleet"))
from mtower_fleet import audit_cast as ac, grounding  # noqa: E402

PY = str(ROOT / "fleet" / ".venv" / "Scripts" / "python.exe")
SKIP_DEFECTS = {"headwear"}  # deliberate recipe variety, not a defect


def main(aid: str, apply: bool) -> int:
    lib = {a["id"]: a for a in json.loads((grounding.LIBRARY_DIR / "actors" / "actors.json").read_text(encoding="utf-8"))["actors"]}
    cast = json.loads((grounding.PRODUCTIONS_DIR / "thunderbolt/ep01_romani/02_preproduction/casting.json").read_text(encoding="utf-8"))["cast"]
    pre = grounding.PRODUCTIONS_DIR / "thunderbolt/ep01_romani/02_preproduction/production_config.json"
    qa = json.loads(pre.read_text(encoding="utf-8")).get("qa", {})
    rules = f"PRODUCTION: {qa.get('story', '')}\nPRODUCTION RULES:\n" + "\n".join(f"- {r}" for r in qa.get("rules", []))
    a = lib[aid]
    roles = [{"cid": c, "character": v.get("character", ""), "additions": v.get("character_additions", "")}
             for c, v in cast.items() if v.get("actor") == aid]
    r = ac.audit_actor(a, roles, rules, {})
    t = r.get("training") or {}
    keys = sorted({k.split("@")[0] for k in (t.get("drift_keys") or [])}
                  | {k.split("@")[0] for k in (t.get("defect_keys") or []) if k.split("@")[0] not in SKIP_DEFECTS})
    print(f"{aid} verdict {r.get('verdict')} · training {t.get('score')} · re-roll {keys} · ${r['_cost_usd']:.3f}", flush=True)
    for i in (t.get("issues") or [])[:5]:
        print("   -", i[:180], flush=True)
    out = ROOT / "fleet" / "reports" / f"training_audit_{aid}.json"
    out.write_text(json.dumps(r, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    if not keys or not apply:
        return 0
    m = ac.actor_material(a)
    by_key: dict[str, list[Path]] = {}
    for img in m["training"]:
        by_key.setdefault(img["key"].split("@")[0], []).append(img["path"])
    for k in keys:
        for p in by_key.get(k, []):
            rej = p.parent / "rejected.json"
            files = json.loads(rej.read_text(encoding="utf-8")).get("files", []) if rej.exists() else []
            if p.name not in files:
                files.append(p.name)
                rej.write_text(json.dumps({"files": files}), encoding="utf-8")
    cost = round(len(keys) * 0.15 + 0.001, 2)
    env = {**os.environ, "PYTHONPATH": str(ROOT / "engine"), "PYTHONUTF8": "1"}
    subprocess.run([PY, "-m", "mtower", "generate", "training-set", aid, "--model", "image_edit_identity",
                    "--only", *keys, "--confirm-cost", str(cost)], cwd=ROOT / "engine", env=env, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1], "--apply" in sys.argv))
