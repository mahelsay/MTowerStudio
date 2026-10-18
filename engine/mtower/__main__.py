"""Command-line interface:  python -m mtower <command> ...   (or engine/mtower.ps1 <command>)"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import __version__, casting, costs, jobs
from .library import Library
from .production import Production
from .prompts import PromptComposer
from .settings import LEDGER_PATH, REPO_ROOT, engine_config, load_env, media_root, secret

DEFAULT_PRODUCTION = "thunderbolt/ep01_romani"


def _print_plan(plan: list[jobs.Job]) -> None:
    ests = jobs.estimates(plan)
    print(f"{'kind':9} {'target':28} {'model':15} {'units':>6}  {'est. USD':>9}")
    for job, est in zip(plan, ests):
        cost = "unknown" if est.total is None else f"{est.total:.3f}"
        print(f"{job.kind:9} {job.target[:28]:28} {job.model_key:15} {job.units:>6g}  {cost:>9}")
    known = [e.total for e in ests if e.total is not None]
    unknown = len(ests) - len(known)
    print(f"\n{len(plan)} job(s). Estimated total: ${sum(known):.2f}" + (f"  (+{unknown} job(s) with unverified prices)" if unknown else ""))
    print("Limits: " + _limits_line())


def _limits_line() -> str:
    batch, monthly = costs.limits()
    az = costs.limits("azure")[1]
    return (f"batch ${batch:.2f} · fal/ElevenLabs monthly ${monthly:.2f} (spent ${costs.spent_this_month('default'):.2f})"
            f" · Azure monthly ${az:.2f} (spent ${costs.spent_this_month('azure'):.2f})")


def cmd_doctor(args) -> int:
    ok = True
    print(f"MTower engine {__version__} · Python {sys.version.split()[0]}")
    print(f"Repository: {REPO_ROOT}")
    env = REPO_ROOT / ".env"
    print(f".env file: {'found' if env.exists() else 'NOT FOUND — copy .env.example to .env and fill it in'}")
    for name in ("FAL_KEY", "ELEVENLABS_API_KEY", "AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET"):
        print(f"  {name}: {'set' if secret(name) else 'not set'}")
    root = media_root()
    try:
        root.mkdir(parents=True, exist_ok=True)
        print(f"Media root: {root} (writable)")
    except OSError as err:
        ok = False
        print(f"Media root: {root} — NOT WRITABLE ({err})")
    lib = Library.load()
    print(f"Library: {len(lib.actors)} actors · {len(lib.wardrobe)} wardrobe · {len(lib.locations)} locations · "
          f"{len(lib.vehicles)} vehicles · {len(lib.props)} props")
    print("Model prices:")
    for key, m in engine_config()["models"].items():
        price = m.get("price_usd")
        print(f"  {key:14} {m['model_id']:50} {'$' + str(price) + '/' + m['unit'] if price is not None else 'NOT VERIFIED'}")
    print("Spending limits: " + _limits_line())
    return 0 if ok else 1


def cmd_check(args) -> int:
    lib, prod = Library.load(), Production.load(args.production)
    composer = PromptComposer(lib, prod)
    problems, shots = [], 0
    screenplays = {}
    for sl, beat, shot in prod.all_shots():
        shots += 1
        composer.shot(beat, shot)
        text = screenplays.setdefault(sl["part"], prod.screenplay(sl)).get(beat["beat"])
        if text is None:
            problems.append(f"{sl['part']} beat {beat['beat']}: not found in the screenplay")
            continue
        if beat.get("vo") and not text.vo:
            problems.append(f"beat {beat['beat']}: shot list expects VO but the screenplay has none")
    for sl_path in prod.shot_list_paths():
        sl = json.loads(sl_path.read_text(encoding="utf-8"))
        text_beats = screenplays.get(sl["part"]) or prod.screenplay(sl)
        for beat in sl["beats"]:
            lines = text_beats.get(beat["beat"]).dialogue if beat["beat"] in text_beats else []
            for ref in beat.get("dialogue_refs") or []:
                if ref["line"] > len(lines):
                    problems.append(f"beat {beat['beat']}: dialogue line {ref['line']} missing (screenplay has {len(lines)})")
    script = prod.config.get("narration", {}).get("script")
    if script:
        from . import voice
        for sl_path in prod.shot_list_paths():
            sl = json.loads(sl_path.read_text(encoding="utf-8"))
            text_beats = screenplays.get(sl["part"]) or prod.screenplay(sl)
            for beat in sl["beats"]:
                t = text_beats.get(beat["beat"])
                if t and t.vo:
                    try:
                        voice.narration_text(prod, sl["part"], beat["beat"], script)
                    except KeyError:
                        problems.append(f"beat {beat['beat']}: has VO in the screenplay but no section in narration_{script}.md"
                                        " (write '—' to keep it silent)")
    from . import dialogue
    problems += dialogue.check_performance(prod)
    problems += script_rule_problems(prod)
    clashes = dialogue.voice_clashes(prod)
    print(f"Checked {shots} shots in {len(prod.shot_list_paths())} shot lists against the library and screenplay.")
    for p in problems:
        print(f"  x {p}")
    for c in clashes:
        print(f"  ! voice clash: {c}")
    print("OK - no issues" if not problems else f"{len(problems)} issue(s)")
    return 1 if problems else 0


def script_rule_problems(prod) -> list[str]:
    """Forbidden content (production_config script_rules, e.g. no Quran) in the screenplay, narration scripts and shot
    lists; Arabic vowel marks are ignored when matching."""
    import re
    rules = prod.config.get("script_rules", {}).get("forbidden", [])
    if not rules:
        return []
    marks = re.compile(r"[\u064B-\u0652\u0670\u0640]")
    files = sorted(p for p in (prod.root / "01_development" / "screenplay").rglob("*.md") if "qa" not in p.parent.parts[-2:])
    files += sorted((prod.root / "03_production" / "voice").glob("narration_*.md")) + prod.shot_list_paths()
    problems = []
    for path in files:
        for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            plain = marks.sub("", line)
            for rule in rules:
                m = re.search(rule["pattern"], plain)
                if m:
                    problems.append(f"{path.name}:{n}: '{m.group(0)}' — {rule.get('why', 'forbidden by script_rules')}")
    return problems


def cmd_prompt(args) -> int:
    lib, prod = Library.load(), Production.load(args.production)
    composer = PromptComposer(lib, prod)
    if args.actor:
        print(composer.actor_reference(args.actor, args.variation))
        return 0
    sl, beat, shot = prod.find_shot(args.shot)
    if args.chatgpt:
        print(f"[{args.shot}] Paste this into ChatGPT (image generation):\n")
        print(composer.chatgpt_prompt(beat, shot) + "\n")
        refs = jobs.shot_references(lib, shot)
        if refs:
            print("Attach these reference photos (they show the real weapons/props):")
            for r in refs:
                print(f"  {r}")
            print('and add: "Use the attached photos as the exact reference for the weapons\' shape, size, and colour."\n')
        print(f"Then save the image as:  {jobs.inbox_dir() / (args.shot + '.png')}")
        print(f"and run:  ./mtower.ps1 import {args.shot}   then   ./mtower.ps1 generate face-pass {args.shot}")
        return 0
    c = composer.shot(beat, shot)
    print(f"[{c.shot_id}] model tier: {c.model_tier} · {c.duration_s:g}s · characters: {', '.join(c.characters) or '-'}\n")
    print("IMAGE PROMPT:\n" + c.image_prompt + "\n")
    print("MOTION PROMPT:\n" + c.motion_prompt + "\n")
    print("NEGATIVE / REVIEW LIST:\n" + c.negative_prompt)
    return 0


def cmd_script(args) -> int:
    prod = Production.load(args.production)
    sl = prod.shot_list(args.part)
    beat = prod.screenplay(sl).get(args.beat)
    if not beat:
        print(f"Beat {args.beat} not found")
        return 1
    print(f"Beat {beat.beat}\n\nVO:\n{beat.vo or '-'}\n\nDIALOGUE:")
    for n, line in enumerate(beat.dialogue, 1):
        print(f"  {n}. {line.speaker} {line.note}\n     {line.text}" + (f"\n     [subtitle] {line.subtitle}" if line.subtitle else ""))
    return 0


def cmd_cast_check(args) -> int:
    lib = Library.load()
    report = casting.check(lib)
    ids = args.ids or sorted(lib.actors)
    print(f"Roster distinctness check · {len(lib.actors)} actors · limits {casting.limits()}\n")
    for p in report.card_problems:
        print(f"  x {p}")
    for p in report.pairs:
        mark = "x TOO SIMILAR" if p.level == "block" else "! close"
        print(f"  {mark}: {p.a} / {p.b} share {len(p.shared)} traits — {', '.join(p.shared)}")
    print("\nNearest look-alike per actor (same gender and age group, family excluded):")
    for aid in ids:
        near = casting.nearest(lib, aid)
        name = lib.actors[aid].get("name_en", "")
        print(f"  {aid} {name:18} " + (f"closest {near[0]} · {len(near[1])} shared ({', '.join(near[1]) or '-'})"
                                         if near else "no comparable actor"))
    if args.coverage:
        print("\nTrait coverage (used ×count) — pick unused values for new actors:")
        free = casting.unused(lib)
        for f, counts in casting.coverage(lib).items():
            used = ", ".join(f"{v}×{n}" for v, n in counts.most_common())
            print(f"  {f:12} used: {used}\n  {'':12} unused: {', '.join(free[f]) or '-'}")
    blocking = report.card_problems + [p for p in report.pairs if p.level == "block"]
    if args.visual:
        from . import qa
        if args.confirm_cost is None or args.confirm_cost < 0.15:
            print("\nVisual check (all approved portraits, one vision review): about $0.10 — re-run with --visual --confirm-cost 0.15")
        else:
            roles = {}
            try:
                prod = Production.load(args.production)
                roles = {v["actor"]: f"{k} {v['character']}" for k, v in prod.casting["cast"].items()}
            except Exception:  # noqa: BLE001 — roles are only labels
                pass
            seen = qa.lookalike_review(lib, roles)
            print(f"\nVisual look-alike check (${seen['cost_usd']:.3f}): {seen['summary']}")
            for p in seen["confusable"]:
                mark = "x LOOK-ALIKE" if p["risk"] >= 7 else "! close"
                print(f"  {mark} {p['a']} / {p['b']} risk {p['risk']}/10 — {p['why']}\n      fix: {p['fix']}")
            blocking += [p for p in seen["confusable"] if p["risk"] >= 7]
    print("\nOK - every actor is clearly distinct" if not blocking else f"\n{len(blocking)} issue(s) to fix in actors.json")
    return 1 if blocking else 0


def _plan(args, lib: Library, prod: Production) -> list[jobs.Job]:
    if args.kind == "anchors":
        return jobs.plan_anchors(lib, prod, args.ids, args.variants or 8, args.tier or "final", args.model)
    if args.kind == "anchor-edit":
        if len(args.ids) != 1:
            raise ValueError("name one actor, e.g. 'generate anchor-edit ACT-0004 --instruction \"...\"'")
        return jobs.plan_anchor_edit(lib, args.ids[0], args.instruction or "", args.variants or 3,
                                     args.model or "image_edit_identity", args.source)
    props = bool(args.ids) and all(i.startswith("PRP-") for i in args.ids)
    if args.kind == "training-set":
        return (jobs.plan_prop_training_set if props else jobs.plan_training_set)(lib, args.ids, args.only)
    if args.kind == "lora":
        return (jobs.plan_prop_lora if props else jobs.plan_lora)(
            lib, args.ids, args.steps or engine_config().get("training", {}).get("default_steps", 1000), args.allow_weak_set)
    if args.kind == "lora-tests":
        return jobs.plan_lora_tests(lib, prod, args.ids)
    if args.kind == "plates":
        return jobs.plan_plates(lib, prod, args.ids, args.tier or "draft", args.variants or 2)
    if args.kind == "keyframes":
        return jobs.plan_keyframes(lib, prod, args.part, args.ids or None, args.tier or "draft", args.variants or 2, args.lora_scale)
    if args.kind == "face-pass":
        return jobs.plan_face_pass(lib, prod, args.ids, args.lead_face)
    if args.kind == "composition":
        if not args.ids:
            raise ValueError("name the shot(s), e.g. 'generate composition 1.6-03 3.13-01'")
        return jobs.plan_compositions(lib, prod, args.ids, args.variants or 1, args.quality, args.lead_face,
                                      not args.no_face_pass, args.actor_refs)
    if args.kind == "edit":
        if len(args.ids) != 1:
            raise ValueError("name one shot, e.g. 'generate edit 4.8-03 --instruction \"...\"'")
        return jobs.plan_edit(prod, args.ids[0], args.instruction or "", Path(args.source) if args.source else None)
    if not args.part and not args.ids:
        raise ValueError("name the shot(s) or a --part, e.g. 'generate clips 2.5-05 --models video_default video_premium'")
    return jobs.plan_clips(lib, prod, args.part, args.ids or None, args.models)


def cmd_import(args) -> int:
    prod = Production.load(args.production)
    found = jobs.inbox_files(args.ids or None)
    if not found:
        print(f"No images to import. Save them in {jobs.inbox_dir()} named after the shot, e.g. 'T.2-01.png'.")
        return 1
    for shot_id, files in found.items():
        try:
            out = jobs.import_keyframes(prod, shot_id, files)
        except (KeyError, RuntimeError) as err:
            print(f"  x {shot_id}: {err}")
            continue
        print(f"Imported {len(files)} image(s) for {shot_id} -> {out}")
    print("Next: './mtower.ps1 generate face-pass <SHOT>' puts the actors' faces on the leads (dry run first).")
    return 0


def cmd_generate(args) -> int:
    lib, prod = Library.load(), Production.load(args.production)
    if args.kind == "anchors":
        blocking = casting.check(lib).blocking_for(args.ids)
        if blocking and not args.allow_similar:
            print("Not generating: these actor cards are not distinct enough yet (run 'cast-check' for details):")
            for msg in blocking:
                print(f"  x {msg}")
            print("Change the traits and face_and_body in library/actors/actors.json, or pass --allow-similar.")
            return 4
    try:
        plan = _plan(args, lib, prod)
    except (FileNotFoundError, ValueError, KeyError) as err:
        print(f"Cannot plan this batch: {err}")
        return 1
    if not plan:
        print("Nothing to generate.")
        return 0
    _print_plan(plan)
    try:
        if args.confirm_cost is None:
            costs.authorize(jobs.estimates(plan), None)
        jobs.run(plan, args.confirm_cost, prod.key)
    except costs.SpendingError as err:
        print(f"\n{err}")
        return 0 if args.confirm_cost is None else 2
    except Exception as err:  # provider errors: show a plain message, no traceback
        name = type(err).__name__
        if name in ("FalError", "ElevenLabsError", "AzureError"):
            print(f"\nThe provider rejected the request — nothing was generated for the failed job.\n{err}")
            if "balance" in str(err).lower():
                print("Fix: add credits at https://fal.ai/dashboard/billing, then re-run the same command.")
            return 3
        raise
    return 0


def cmd_review(args) -> int:
    from .gallery import serve
    root = Path(args.path) if args.path else media_root()
    serve(root, args.port, not args.no_browser)
    return 0


def cmd_ledger(args) -> int:
    if not LEDGER_PATH.exists():
        print("No spending recorded yet.")
        return 0
    total = 0.0
    for line in LEDGER_PATH.read_text(encoding="utf-8").splitlines():
        e = json.loads(line)
        total += float(e.get("cost_usd") or 0)
        print(f"{e['timestamp']}  {e.get('kind', ''):9} {e.get('target', ''):24} ${float(e.get('cost_usd') or 0):.3f}")
    print(f"\nTotal recorded: ${total:.2f} · this month: ${costs.spent_this_month():.2f}")
    return 0


def cmd_qa(args) -> int:
    from . import qa

    lib, prod = Library.load(), Production.load(args.production)
    if args.report:
        print(f"Report: {qa.write_report(prod, lib)}")
        return 0
    if args.anchors:
        items = qa.anchor_items(lib, args.ids or None)
    else:
        items = qa.keyframe_items(lib, prod, args.ids or None, args.part, args.scope)
    done = [i for i in items if i.qa_path.exists()]
    if not args.force:
        items = [i for i in items if not i.qa_path.exists()]
    print(f"{len(items)} image(s) to review" + (f" ({len(done)} already reviewed{'' if args.force else ', skipped'})" if done else ""))
    if not items:
        print(f"Report: {qa.write_report(prod, lib)}")
        return 0
    est = qa.estimates(items)[0]
    print(f"Reviewer {costs.model('qa_review')['model_id']} · ceiling ${est.total:.2f} · Limits: {_limits_line()}")
    try:
        qa.run(items, args.confirm_cost, prod)
    except costs.SpendingError as err:
        print(f"\n{err}")
        return 0 if args.confirm_cost is None else 2
    print(f"Report: {qa.write_report(prod, lib)}")
    return 0


def cmd_script_qa(args) -> int:
    from . import scriptqa

    prod = Production.load(args.production)
    root = prod.root / "01_development" / "screenplay"
    path = root / (args.file if args.file.endswith(".md") else args.file + ".md")
    if not path.is_file():
        print(f"No screenplay file {path}")
        return 2
    if not args.report:
        items = scriptqa.plan(prod, path, args.beats, args.force)
        print(f"{len(items)} beat(s) to review in {path.name}" + ("" if items else " (all unchanged since their last review)"))
        if items:
            est = scriptqa.estimates(items)[0]
            print(f"Reviewer {costs.model('script_review')['model_id']} · ceiling ${est.total:.2f} · Limits: {_limits_line()}")
            try:
                scriptqa.run(prod, path, items, args.confirm_cost)
            except costs.SpendingError as err:
                print(f"\n{err}")
                return 0 if args.confirm_cost is None else 2
    verdicts = scriptqa.saved(prod, path)
    if args.beats:
        verdicts = [v for v in verdicts if v["beat"] in args.beats]
    print("\n".join(scriptqa.summary_lines(verdicts)))
    print(f"Report: {scriptqa.write_report(prod, path)}")
    return 0


def cmd_voice(args) -> int:
    from . import voice

    prod = Production.load(args.production)
    narration = prod.config.get("narration", {})
    script = args.script or narration.get("script")
    if script in ("formal", "screenplay"):
        script = None
    if args.check:
        beats = []
        for sl_path in prod.shot_list_paths():
            sl = json.loads(sl_path.read_text(encoding="utf-8"))
            if args.part and args.part not in sl_path.stem:
                continue
            text = prod.screenplay(sl)
            beats += [b["beat"] for b in sl["beats"] if (not args.beat or b["beat"] == args.beat)
                      and b["beat"] in text and text[b["beat"]].vo
                      and (not script or voice.narration_text(prod, sl["part"], b["beat"], script))]
        try:
            rows = voice.check_beats(prod, beats)
        except RuntimeError as err:
            print(f"Cannot check narration: {err}")
            return 1
        for r in rows:
            print(f"  {'✓' if r['ok'] else '✗'} {r['beat']:5} match {r['match']:.2f}  {r['take'] or ''}"
                  + (f"  not heard: {' | '.join(r['missing'])}" if r["missing"] else ""))
        bad = [r for r in rows if not r["ok"]]
        print(f"{len(rows) - len(bad)} of {len(rows)} take(s) heard as written" + (" — listen to the ✗ ones" if bad else ""))
        return 0
    if not (args.part and args.beat):
        print("voice needs --part and --beat to make takes (or --check)")
        return 1
    if narration.get("cast") and script == narration.get("script") and not args.voices:
        from . import dialogue
        try:
            text, perf = dialogue.narration(prod, args.beat, script)
            if not text:
                print(f"Beat {args.beat} is silent in narration_{script}.md — nothing to record.")
                return 0
            entry = dialogue.resolve(prod, narration["cast"])
            if entry:
                est = sum(e.total for e in dialogue.take_estimate(entry, text, args.tries))
                print(f"{narration['cast']} {dialogue.file_tag(entry)} · [{perf.get('intensity')}/10 {perf.get('volume')} "
                      f"{perf.get('pace')}] {perf.get('emotion')} · up to {args.tries} tries · ceiling ${est:.3f}\n{text}")
            out = dialogue.run_narration(prod, args.part, args.beat, args.confirm_cost, args.tries)
        except costs.SpendingError as err:
            print(f"\n{err}")
            return 0 if args.confirm_cost is None else 2
        except (KeyError, RuntimeError) as err:
            print(f"Cannot make narration: {err}")
            return 1
        take = json.loads((out / "take.json").read_text(encoding="utf-8"))
        print(f"{'✓' if take['ok'] else '✗'} match {take['match']:.2f} after {take['tries']} try(ies) · ${take['cost_usd']:.3f}\nTake saved in {out}")
        return 0
    voices = args.voices or narration.get("voices") or costs.model("voice_azure").get("voices", [])
    try:
        text = voice.narration_text(prod, args.part, args.beat, script)
        if not text:
            print(f"Beat {args.beat} is silent in narration_{script}.md — nothing to record.")
            return 0
        est = voice.plan_cost(text, voices)[0]
        print(f"{len(text)} characters × {len(voices)} voice(s): {', '.join(voices)} · ceiling ${est.total:.3f}"
              f" · script: {script or 'screenplay (formal)'}")
        out = voice.run(prod, args.part, args.beat, voices, args.rate, args.confirm_cost, script)
    except costs.SpendingError as err:
        print(f"\n{err}")
        return 0 if args.confirm_cost is None else 2
    except (KeyError, RuntimeError) as err:
        print(f"Cannot make narration: {err}")
        return 1
    print(f"Takes saved in {out}")
    return 0


def cmd_dialogue(args) -> int:
    from . import dialogue

    prod = Production.load(args.production)
    if args.reel:
        try:
            out = dialogue.voice_reel(prod)
        except KeyError as err:
            print(f"Cannot build the reel: {err}")
            return 1
        print(f"Voice reel: {out}\nCue sheet: {out.with_name('cues.txt')}")
        return 0
    if not args.beat:
        print("dialogue needs --beat (or --reel)")
        return 1
    try:
        todo, missing, estimates = dialogue.plan_dialogue(prod, args.beat, args.lines, args.tries)
        for ln, entry in todo:
            p = ln.perf
            print(f"  L{ln.n} {ln.speaker:10} {dialogue.file_tag(entry) if entry.get('voice') else 'group':32} "
                  f"[{p.get('intensity')}/10 {p.get('volume'):7} {p.get('pace'):8}] {ln.text[:60]}")
        for s in missing:
            print(f"  ✗ {s}: not cast yet — run 'audition {s}' and approve a voice")
        total = sum(e.total for e in estimates)
        print(f"{len(todo)} line(s) · up to {args.tries} tries each · ceiling ${total:.2f}")
        rows = dialogue.run_dialogue(prod, args.beat, args.lines, args.confirm_cost, args.tries)
    except costs.SpendingError as err:
        print(f"\n{err}")
        return 0 if args.confirm_cost is None else 2
    except (KeyError, RuntimeError) as err:
        print(f"Cannot record dialogue: {err}")
        return 1
    for r in rows:
        print(f"  {'✓' if r['ok'] else '✗'} L{r['line'].n} {r['line'].speaker:10} match {r['match']:.2f} ({r['tries']} try) "
              f"{r['seconds']:.1f}s ${r['cost_usd']:.3f}  {r['dir']}" + (f"  not heard: {' | '.join(r['missing'])}" if r["missing"] else ""))
    print(f"Spent about ${sum(r['cost_usd'] for r in rows):.2f} · review in the app: Dialogue")
    return 0


def cmd_audition(args) -> int:
    from . import dialogue

    prod = Production.load(args.production)
    if not args.speakers:
        for r in dialogue.cast_status(prod):
            print(f"  {r['speaker']:26} {r['name'][:28]:28} {(r['voice'] or '—'):38} {r['status']:32} {', '.join(r['beats'])[:40]}")
        for c in dialogue.voice_clashes(prod):
            print(f"  ! {c}")
        return 0
    speakers = [s for s in prod.config.get("voice_cast", {}) if not s.startswith("_") and not dialogue.resolve(prod, s)] \
        if args.speakers == ["uncast"] else args.speakers
    try:
        plans = [(s, *dialogue.plan_audition(prod, s, args.tries)) for s in speakers]
        total = 0.0
        for s, entry, candidates, samples, estimates in plans:
            cost = sum(e.total for e in estimates)
            total += cost
            print(f"  {s:26} {len(candidates)} voice(s) × {len(samples)} sample(s) · ceiling ${cost:.2f}")
        print(f"{len(plans)} audition(s) · ceiling ${total:.2f}")
        costs.authorize([e for *_, estimates in plans for e in estimates], args.confirm_cost)
    except costs.SpendingError as err:
        print(f"\n{err}")
        return 0 if args.confirm_cost is None else 2
    except KeyError as err:
        print(f"Cannot audition: {err}")
        return 1
    failed = 0
    for s, *_ in plans:
        print(f"{s}:")
        try:
            out = dialogue.run_audition(prod, s, args.confirm_cost, args.tries)
            print(f"  saved in {out}")
        except (KeyError, RuntimeError) as err:
            failed += 1
            print(f"  ✗ {err}")
    print("Review in the app: Voice casting — approve one voice per character" + (f" · {failed} failed" if failed else ""))
    return 1 if failed else 0


def cmd_lipsync(args) -> int:
    from . import dialogue

    prod = Production.load(args.production)
    if args.recover:
        try:
            print(f"Recovered: {dialogue.recover_lipsync(prod, args.recover[0], args.recover[1], args.model)}")
        except (KeyError, RuntimeError) as err:
            print(f"Cannot recover: {err}")
            return 1
        return 0
    if args.crop:
        failed = 0
        for sid in args.crop:
            try:
                print(f"  ✓ {sid:8} cropped: {dialogue.crop_subtitles(prod, sid, args.keep)}")
            except (KeyError, ValueError) as err:
                print(f"  ✗ {sid:8} {err}")
                failed += 1
        return 1 if failed else 0
    if args.reel:
        try:
            print(f"Talking reel: {dialogue.talking_reel(prod, args.reel)}")
        except KeyError as err:
            print(f"Cannot build the reel: {err}")
            return 1
        return 0
    if args.fit:
        changes = dialogue.fit_talking_shots(prod, args.fit, apply=args.apply)
        for sid, audio, new in changes:
            print(f"  {sid:9} audio {audio:5.2f}s → shot {new}s")
        print(f"{len(changes)} talking shot(s) " + ("resized in the shot list" if args.apply else "to resize — add --apply to write"))
        return 0
    if not args.beat:
        print("lipsync needs --beat (or --reel PART)")
        return 1
    plan = dialogue.lipsync_plan(prod, args.beat, args.shots)
    for p in plan:
        takes = ", ".join(f"L{ln.n} {ln.speaker} {'✓' if f else '✗ no take'}" for ln, f in p["lines"]) or "✗ no line"
        warn = "  ! two speakers in one shot — only one face can be animated" if len(p["speakers"]) > 1 else ""
        print(f"  {p['shot']['shot_id']:8} keyframe {p['keyframe_pick']:10} · {takes}{warn}")
    try:
        rows = dialogue.run_lipsync(prod, args.beat, args.model, args.confirm_cost, args.shots)
    except costs.SpendingError as err:
        print(f"\n{err}")
        return 0 if args.confirm_cost is None else 2
    except (KeyError, RuntimeError) as err:
        print(f"Cannot lip-sync: {err}")
        return 1
    print(f"Spent about ${sum(r['cost'] for r in rows):.2f} · rough cut: animatic --part <part> --beats {args.beat} --clips --dialogue")
    return 0


def cmd_autofix(args) -> int:
    from . import autofix, qa

    lib, prod = Library.load(), Production.load(args.production)
    ids = args.ids
    if not ids:
        ids = []
        for sl, _, shot in prod.all_shots(args.part):
            image = autofix.current_keyframe(prod, shot["shot_id"]) if (media_root() / "productions" / prod.key / "keyframes"
                                                                         / sl["part"] / shot["shot_id"]).exists() else None
            verdict = image.with_suffix(".qa.json") if image else None
            if verdict and verdict.exists() and json.loads(verdict.read_text(encoding="utf-8")).get("score", 0) < args.min_score:
                ids.append(shot["shot_id"])
    if not ids:
        print("Nothing to fix (no reviewed, failing keyframes in scope — run 'qa' first).")
        return 0
    if args.confirm_cost is None:
        per = 0.6
        print(f"{len(ids)} shot(s): {' '.join(ids)}\nUp to {args.rounds} round(s) each, about ${per:.2f} per round at most "
              f"(composition + face swap + review). Re-run with --confirm-cost <total budget USD>.")
        return 0
    results = autofix.autofix(lib, prod, ids, args.rounds, args.confirm_cost, args.min_score)
    for r in results:
        print(f"  {r['shot']:8} {r['start_score']:>2} → {r['best_score']:>2}  {r['verdict']:5} best {r['best']}  ({r['rounds']} round(s))")
    print(f"Report: {qa.write_report(prod, lib)}")
    return 0


def cmd_animatic(args) -> int:
    from . import animatic

    prod = Production.load(args.production)
    try:
        out = animatic.build(prod, args.part, args.beats, Path(args.voice) if args.voice else None, args.vo_start, args.best,
                             args.clips, args.ambience, args.dialogue, args.narration, args.sound, args.english)
    except (FileNotFoundError, KeyError) as err:
        print(f"Cannot build the animatic: {err}")
        return 1
    print(f"{'Rough cut' if args.clips else 'Animatic'}: {out}")
    return 0


def cmd_sound(args) -> int:
    from . import costs, sound

    prod = Production.load(args.production)
    kinds = set(args.only or ["bed", "sfx", "music"])
    try:
        cues = sound.plan(prod, args.part, kinds, args.shots, args.variants, args.cues)
    except (FileNotFoundError, KeyError) as err:
        print(f"Cannot plan the sound: {err}")
        return 1
    if not cues:
        print("Nothing to make (no 'sound' block in the shot list, no clips with an 'sfx' prompt, or all filtered out).")
        return 0
    print(f"{len(cues)} sound cue(s) for {args.part}:\n{sound.describe(cues)}")
    try:
        made = sound.run(prod, args.part, cues, args.confirm_cost)
    except costs.SpendingError as err:
        print(err)
        return 0 if args.confirm_cost is None else 1
    print(f"Made {len(made)} of {len(cues)} · review in the app: Sound")
    return 0


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_env()
    p = argparse.ArgumentParser(prog="mtower", description="MTower Studio production engine")
    p.add_argument("--production", default=DEFAULT_PRODUCTION, help="production key under productions/ (default: %(default)s)")
    sub = p.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="check setup: Python, .env keys (never printed), media folder, library, prices, limits")
    sub.add_parser("check", help="validate every shot against the library, casting, and the locked screenplay")

    sp = sub.add_parser("prompt", help="show the composed prompts for a shot or an actor reference")
    sp.add_argument("--shot")
    sp.add_argument("--actor")
    sp.add_argument("--variation", default="REF_ANCHOR")
    sp.add_argument("--chatgpt", action="store_true", help="with --shot: a paste-ready ChatGPT image prompt + reference photos to attach")

    sp = sub.add_parser("import", help="import images from media/inbox (e.g. made in ChatGPT) as keyframes, named by shot ID — free")
    sp.add_argument("ids", nargs="*", help="shot IDs to import (default: everything in the inbox)")

    sp = sub.add_parser("script", help="show the narration and dialogue of a beat from the screenplay")
    sp.add_argument("--part", required=True, help="e.g. 01_act_one")
    sp.add_argument("--beat", required=True, help="e.g. 1.4")

    sp = sub.add_parser("generate", help="plan (dry run) or run a paid generation batch")
    sp.add_argument("kind", choices=["anchors", "anchor-edit", "training-set", "lora", "lora-tests", "plates", "keyframes", "composition", "edit", "face-pass", "clips"])
    sp.add_argument("ids", nargs="*", help="actor/asset/shot IDs")
    sp.add_argument("--part", help="shot-list part for keyframes/clips, e.g. 02_act_two")
    sp.add_argument("--tier", choices=["draft", "final"])
    sp.add_argument("--variants", type=int, help="images per target")
    sp.add_argument("--model", help="override the model key from engine_config.json (e.g. image_ultra) — anchors only")
    sp.add_argument("--confirm-cost", type=float, help="authorize spending up to this many USD (required for a paid run)")
    sp.add_argument("--allow-similar", action="store_true", help="anchors only: generate even if cast-check finds a look-alike")
    sp.add_argument("--only", nargs="+", metavar="KEY", help="training-set only: re-roll just these variation keys")
    sp.add_argument("--steps", type=int, help="lora only: training steps (default from engine_config.json; price scales with steps)")
    sp.add_argument("--allow-weak-set", action="store_true", help="lora only: train even if the training-set gate fails")
    sp.add_argument("--lora-scale", type=float, help="keyframes only: face-model strength for this batch (default 1.0; lower = more freedom for pose and costume)")
    sp.add_argument("--lead-face", choices=["vision", "largest", "center", "smallest", "left", "right"], help="face-pass / composition: which detected face is the lead (default vision: the reviewer matches characters to faces from the shot design)")
    sp.add_argument("--quality", choices=["low", "medium", "high"], help="composition only: Azure gpt-image quality (default medium)")
    sp.add_argument("--no-face-pass", action="store_true", help="composition only: skip the chained face pass")
    sp.add_argument("--actor-refs", action="store_true", help="composition only: attach the lead's anchor portrait so gpt-image draws his face (no face pass)")
    sp.add_argument("--instruction", help="edit only: what to change, e.g. \"Remove the cross from the wall. Keep everything else the same.\"")
    sp.add_argument("--source", help="edit only: the image to edit (default: the shot's approved keyframe, else its newest)")
    sp.add_argument("--models", nargs="+", metavar="KEY", help="clips only: video model key(s) from engine_config.json, e.g. 'video_default video_kling_v3 video_premium' for a side-by-side bake-off")

    sp = sub.add_parser("cast-check", help="check that every virtual actor is clearly a different person")
    sp.add_argument("ids", nargs="*", help="actor IDs to report on (default: all)")
    sp.add_argument("--coverage", action="store_true", help="also list used and unused trait values for casting new actors")
    sp.add_argument("--visual", action="store_true", help="also compare the approved portraits by eye (vision reviewer, ~$0.10): "
                                                          "catches look-alikes whose written traits differ")
    sp.add_argument("--confirm-cost", type=float, help="with --visual: spend up to this many USD")

    sp = sub.add_parser("review", help="open the local review gallery to approve the best takes")
    sp.add_argument("path", nargs="?")
    sp.add_argument("--port", type=int, default=8765)
    sp.add_argument("--no-browser", action="store_true")

    sub.add_parser("ledger", help="show recorded spending")

    sp = sub.add_parser("qa", help="vision QA: an Azure reviewer checks images against their design (dry run first)")
    sp.add_argument("ids", nargs="*", help="shot IDs (keyframes) or actor IDs (anchors); default: everything in scope")
    sp.add_argument("--part", help="keyframes of one shot-list part, e.g. 02_act_two")
    sp.add_argument("--scope", choices=["current", "all"], default="current",
                    help="current = each shot's approved keyframe (else its newest batch); all = every keyframe ever made")
    sp.add_argument("--anchors", action="store_true", help="review the actors' approved anchor portraits instead of keyframes")
    sp.add_argument("--force", action="store_true", help="review again images that already have a verdict")
    sp.add_argument("--report", action="store_true", help="only rebuild the Markdown report from saved verdicts (free)")
    sp.add_argument("--confirm-cost", type=float, help="spend up to this many USD (required to run)")

    sp = sub.add_parser("voice", help="narration takes with Azure Speech for one beat's VO (dry run first)")
    sp.add_argument("--part", help="e.g. 02_act_two (required to make takes)")
    sp.add_argument("--beat", help="e.g. 2.5 (required to make takes)")
    sp.add_argument("--voices", nargs="+", help="Azure voice names (default: production_config narration.voices, else engine_config voice_azure.voices)")
    sp.add_argument("--rate", default="-6%", help="speaking rate, e.g. -6%% (slower) or +0%%")
    sp.add_argument("--script", help="read the VO from 03_production/voice/narration_<script>.md, e.g. 'egyptian' (default: production_config "
                                     "narration.script); 'formal' reads the screenplay")
    sp.add_argument("--confirm-cost", type=float, help="spend up to this many USD (required to run)")
    sp.add_argument("--tries", type=int, default=3, help="with a cast narrator: re-record until speech-to-text hears the text (default 3)")
    sp.add_argument("--check", action="store_true", help="listen-back check instead of new takes: speech-to-text on each beat's newest "
                                                         "takes vs. their script (all narrated beats, or --part / --beat); ~$0.0003/s")

    sp = sub.add_parser("dialogue", help="record a beat's dialogue in each character's cast voice, performed to the line's "
                                         "intensity/volume/pace/emotion and situation; speech-to-text retakes (dry run first)")
    sp.add_argument("--beat", help="e.g. T.3 (required unless --reel)")
    sp.add_argument("--reel", action="store_true", help="free: the whole episode's voices (narration + dialogue) in story order, "
                                                        "with a cue sheet, for one listen-through")
    sp.add_argument("--lines", nargs="+", type=int, help="only these line numbers of the beat")
    sp.add_argument("--tries", type=int, default=3, help="re-record until speech-to-text hears the line as written (default 3)")
    sp.add_argument("--confirm-cost", type=float, help="spend up to this many USD (required to run)")

    sp = sub.add_parser("audition", help="voice casting: each candidate voice reads the character's calmest and most intense line "
                                         "(no speakers: show the cast)")
    sp.add_argument("speakers", nargs="*", help="speaker IDs from voice_cast, e.g. C-02 N-01, or 'uncast' for everyone without a voice")
    sp.add_argument("--tries", type=int, default=3)
    sp.add_argument("--confirm-cost", type=float, help="spend up to this many USD (required to run)")

    sp = sub.add_parser("lipsync", help="talking shots of a beat: keyframe + the recorded lines → a lip-synced clip (fal; dry run first)")
    sp.add_argument("--beat", help="e.g. 1.4 (required unless --reel)")
    sp.add_argument("--reel", metavar="PART", help="free: join the lip-synced talking shots of a part (e.g. 01_act_one) in story order")
    sp.add_argument("--recover", nargs=2, metavar=("SHOT", "REQUEST_ID"), help="fetch a lip-sync fal finished after a time-out")
    sp.add_argument("--crop", nargs="+", metavar="SHOT", help="free: remove fake burned-in subtitles by keeping the top of the "
                                                               "frame (see --keep); the old clip is marked rejected")
    sp.add_argument("--keep", type=float, default=0.76, help="share of the frame height --crop keeps (default 0.76)")
    sp.add_argument("--fit", metavar="PART", help="free: size each talking shot of a part to its current takes (lead-in + "
                                                  "lines + 0.6 s); shows the changes, --apply writes them")
    sp.add_argument("--apply", action="store_true", help="with --fit: write the new durations into the shot list")
    sp.add_argument("--model", default="kling-avatar-v2-pro", choices=["kling-avatar-v2-pro", "omnihuman-1.5", "minimax-h3-max"])
    sp.add_argument("--shots", nargs="+", help="only these shot IDs")
    sp.add_argument("--confirm-cost", type=float, help="spend up to this many USD (required to run)")

    sp = sub.add_parser("autofix", help="QA loop: follow the reviewer's fix route on Azure and re-review, up to N rounds (never approves)")
    sp.add_argument("ids", nargs="*", help="shot IDs (default: every shot of --part whose current keyframe scored below --min-score)")
    sp.add_argument("--part", help="e.g. 02_act_two")
    sp.add_argument("--rounds", type=int, default=2)
    sp.add_argument("--min-score", type=int, default=8, help="stop when a candidate scores at least this (default 8)")
    sp.add_argument("--confirm-cost", type=float, help="total budget in USD for this run (required)")

    sp = sub.add_parser("script-qa", help="script board: an Azure reviewer scores every dialogue line of a screenplay file for "
                                          "Egyptian dialect, army register, intensity, character, drama, diacritics (dry run first)")
    sp.add_argument("file", help="screenplay file, e.g. 01_act_one or drafts/01_act_one_v2 (under 01_development/screenplay)")
    sp.add_argument("--beats", nargs="+", help="only these beats")
    sp.add_argument("--force", action="store_true", help="review again beats whose text has not changed")
    sp.add_argument("--report", action="store_true", help="only print and rebuild the report from saved verdicts (free)")
    sp.add_argument("--confirm-cost", type=float, help="spend up to this many USD (required to run)")

    sp = sub.add_parser("animatic", help="moving storyboard of one or more beats: keyframes with a slow push-in + a narration take (free)")
    sp.add_argument("--part", required=True, help="e.g. 02_act_two")
    sp.add_argument("--beats", nargs="+", required=True, help="e.g. 2.5")
    sp.add_argument("--voice", help="a narration WAV to lay under the picture (e.g. from 'voice')")
    sp.add_argument("--vo-start", type=float, default=1.0, help="seconds before the narration starts (default 1)")
    sp.add_argument("--best", action="store_true", help="use each shot's best-scoring QA candidate even if another take is approved (preview)")
    sp.add_argument("--clips", action="store_true", help="a rough cut: use each shot's video clip (approved, else newest), fitted to the "
                                                         "shot length; shots without a clip fall back to the keyframe")
    sp.add_argument("--ambience", action="store_true", help="lay a soft temporary wind bed under the picture")
    sp.add_argument("--dialogue", action="store_true", help="lay each line's take (approved, else newest) at its shot, timed like "
                                                           "lip-sync; lip-synced clips are not stretched")
    sp.add_argument("--narration", action="store_true", help="lay the narrator's take of each beat (approved, else newest) from the "
                                                            "beat's first shot (+ --vo-start)")
    sp.add_argument("--sound", action="store_true", help="mix the part's sound (beds, spot effects, music — see 'sound') under "
                                                        "the voices, ducked when someone speaks, loudness -16 LUFS")
    sp.add_argument("--english", action="store_true", help="burn in English subtitles: card lines_en, caption text_en and each "
                                                          "shot's dialogue_en, timed to the placed takes")

    sp = sub.add_parser("sound", help="sound for a part on fal: continuous beds, spot effects from each clip, music candidates "
                                      "(dry run first)")
    sp.add_argument("--part", required=True, help="e.g. 00_teaser")
    sp.add_argument("--only", nargs="+", choices=["bed", "sfx", "music"], help="only these kinds (default: all)")
    sp.add_argument("--shots", nargs="+", help="spot effects only for these shots")
    sp.add_argument("--cues", nargs="+", help="beds / music only for these cue ids, e.g. teaser_score")
    sp.add_argument("--variants", type=int, default=3, help="music candidates per cue (default 3)")
    sp.add_argument("--confirm-cost", type=float, help="spend up to this many USD (required to run)")

    args = p.parse_args(argv)
    handlers = {"doctor": cmd_doctor, "check": cmd_check, "prompt": cmd_prompt, "script": cmd_script, "import": cmd_import,
                "generate": cmd_generate, "review": cmd_review, "ledger": cmd_ledger, "cast-check": cmd_cast_check,
                "qa": cmd_qa, "voice": cmd_voice, "autofix": cmd_autofix, "animatic": cmd_animatic,
                "dialogue": cmd_dialogue, "audition": cmd_audition, "lipsync": cmd_lipsync, "script-qa": cmd_script_qa,
                "sound": cmd_sound}
    return handlers[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
