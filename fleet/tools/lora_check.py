"""Phase D final gate: does each new face model (LoRA) reproduce the approved actor?

For each actor: 4 studio test portraits from the face model (engine lora-tests, studio variant: never production
shots) → one vision review against the approved anchor → pass when >= 3 of 4 are the same person (score >= 8).
Usage: python lora_check.py ACT-0004 [ACT-…] --confirm-cost 1.20
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "fleet"))
sys.path.insert(0, str(ROOT / "engine"))

from mtower.settings import load_env  # noqa: E402

load_env()
from mtower import jobs as ej  # noqa: E402
from mtower.library import Library  # noqa: E402
from mtower.production import Production  # noqa: E402
from mtower_fleet import client, lessons  # noqa: E402
from mtower_fleet.agents.base import _cost, _parse_json  # noqa: E402
from mtower_fleet.agents.image_qa import _image_part  # noqa: E402

SYSTEM = (
    "You are the Casting QA lead. Image 1 is the APPROVED portrait of a virtual actor. The other images were generated "
    "by the actor's newly trained face model in new lighting/angles/expressions. For each test image judge: is it "
    "unmistakably the SAME person (bone structure, nose, eyes, brows, skin marks, age, facial hair, hairline)? Score "
    "0-10. Output JSON: { tests: [ { file, identity: 'same'|'drifted', score, issue } ], same_count, verdict: "
    "'pass'|'fail' (pass = at least 3 tests 'same' with score >= 8), note }."
)


def main(ids: list[str], confirm: float | None) -> int:
    lib, prod = Library.load(), Production.load("thunderbolt/ep01_romani")
    ej.actor_solo_shots = lambda *_a, **_k: []  # studio test portraits only — never spend on production shots here
    plan = ej.plan_lora_tests(lib, prod, ids)
    est = sum(e.total for e in ej.estimates(plan)) + 0.03 * len(ids)
    print(f"{len(plan)} test portrait(s) for {', '.join(ids)} + {len(ids)} QA review(s): estimate ${est:.2f}")
    if confirm is None or confirm < est:
        print(f"Not run. Re-run with --confirm-cost {round(est + 0.005, 2)}")
        return 0
    ej.run(plan, sum(e.total for e in ej.estimates(plan)), prod.key)
    results = {}
    for aid in ids:
        actor = lib.actors[aid]
        tests = sorted((ej.actor_dir(lib, aid) / "lora_tests").glob("*/*.png"), key=lambda p: p.stat().st_mtime)[-4:]
        content = [{"type": "text", "text": f"ACTOR {aid}: {actor.get('face_and_body')}"},
                   {"type": "text", "text": "IMAGE 1 — APPROVED PORTRAIT:"}, _image_part(str(ej.anchor_path(lib, aid)))]
        for n, t in enumerate(tests, start=2):
            content += [{"type": "text", "text": f"IMAGE {n} — test '{t.name}':"}, _image_part(str(t))]
        raw, usage = client.complete([{"role": "system", "content": SYSTEM + "\nRespond ONLY with JSON."},
                                      {"role": "user", "content": content}], vision=True,
                                     response_format={"type": "json_object"}, max_completion_tokens=3000)
        r = _parse_json(raw)
        r["_cost_usd"] = _cost(usage, True)
        results[aid] = r
        (tests[0].parent / "studio_lora_check.json").write_text(json.dumps(r, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"{aid} {r.get('verdict')} · same {r.get('same_count')}/4 · "
              f"{[(t.get('identity'), t.get('score')) for t in r.get('tests', [])]} · {r.get('note', '')[:140]}", flush=True)
        if r.get("verdict") != "pass":
            lessons.capture(kind="training_set", target=aid, department="casting", source="studio-lora-check",
                            problem="; ".join(str(t.get("issue")) for t in r.get("tests", []) if t.get("identity") != "same"),
                            resolved=False, tags=[f"KIND:training_set"])
    out = ROOT / "fleet" / "reports" / "lora_check.json"
    prev = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    out.write_text(json.dumps({**prev, **results}, indent=2, ensure_ascii=False), encoding="utf-8")
    return 0


if __name__ == "__main__":
    args = sys.argv[1:]
    confirm = float(args[args.index("--confirm-cost") + 1]) if "--confirm-cost" in args else None
    raise SystemExit(main([a for a in args if a.startswith("ACT-")], confirm))
