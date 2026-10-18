"""Local review app: one shot (or actor, poster, narration…) at a time, its candidates in a filmstrip, QA verdicts beside
the picture, and an approval gate on the QA score.

Runs on http://localhost:<port> using only the standard library. Approving writes approved.json next to the chosen file's
manifest; notes go to notes.json; training-set rejections to rejected.json. Nothing is uploaded anywhere.
"""

from __future__ import annotations

import json
import mimetypes
import re
import urllib.parse
import webbrowser
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

IMAGES = {".png", ".jpg", ".jpeg", ".webp"}
MEDIA = IMAGES | {".mp4", ".wav", ".mp3"}

CHECKLISTS = {
    "anchor": ["Looks like an ordinary real person, not a model", "Clearly different from everyone in the approved roster",
               "Matches the card: age, region, face shape, hair, facial hair", "No insignia, badges, face paint, forehead dots, or text"],
    "training_set": ["Same face as the anchor in every image — reject any drift", "Clothes really changed where the caption says so",
                     "No wrong-gender items (e.g. a headscarf on a man)", "Face visible enough to learn (reject too dark or hidden)",
                     "No text, watermarks, or extra people"],
    "lora_test": ["Same person as the anchor at a glance", "Right age", "Clothes follow the prompt, not the anchor outfit"],
    "keyframe": ["Face matches the actor; age right; head natural size for the body", "Costume, rank, and gear match the shot",
                 "Props and weapons correct for 1973", "Action and framing match the shot, not a posed portrait",
                 "Light and time of day match the scene; no modern objects or text"],
    "clip": ["Motion matches the shot; no warping of faces or hands", "Continuity with the approved keyframe"],
    "cut": ["Shots flow in story order; light and water depth stay continuous", "Narration lands on the right images",
            "No warping faces, hands or weapons in any shot"],
    "narration": ["Every word clear and as written", "Sounds like old Hamdi remembering — intimate, not a documentary reader",
                  "Feeling fits the moment (intensity in the take's notes)"],
    "dialogue": ["Words exactly as written, in Egyptian Arabic (no English-sounding or garbled syllables)",
                 "Intensity, volume and pace fit the moment — see the [n/10 · volume · pace] line under the text",
                 "Same voice as the character's other lines"],
    "audition": ["Sounds like this person: age, origin, temperament", "Holds both samples: the calm line and the intense line",
                 "Clearly different from the characters they share scenes with"],
    "poster": ["Reads at thumbnail size", "Room for the title; no AI lettering", "Faces natural and on-model"],
    "music": ["Fits the moment and the period: orchestral, restrained, no religious chant or singing",
              "Builds and lands cleanly at the end (no abrupt stop)", "No modern genre sounds (EDM, trap, pop drums)"],
    "bed": ["Sounds like the place (rotors, wind) without obvious repetition", "No voices or music in it"],
    "sfx": ["Lands on the action in the clip", "No voices, music or odd synthetic sounds"],
}

SECTIONS = [("keyframe", "Keyframes"), ("clip", "Clips"), ("dialogue", "Dialogue"), ("audition", "Voice casting"),
            ("narration", "Narration"), ("music", "Music"), ("bed", "Sound beds"), ("sfx", "Sound effects"),
            ("animatic", "Animatics"),
            ("cut", "Cuts"), ("poster", "Posters"), ("anchor", "Casting"), ("training_set", "Training sets"),
            ("lora_test", "Face-model tests")]


# ---- the approval gate ------------------------------------------------------------------
def gate_config() -> dict:
    try:
        from .settings import engine_config
        return engine_config().get("qa_gate", {})
    except Exception:  # noqa: BLE001 — the gallery must run even without the engine config
        return {}


def min_score(kind: str, cfg: dict | None = None) -> int | None:
    """The QA score an image of this kind needs for a plain approval (None: no QA for this kind)."""
    cfg = gate_config() if cfg is None else cfg
    if kind not in cfg.get("reviewed_kinds", ["keyframe", "anchor", "poster"]):
        return None
    scores = cfg.get("min_score", {})
    return int(scores.get(kind, scores.get("default", 7)))


def gate_check(kind: str, qa: dict | None, cfg: dict | None = None) -> tuple[bool, str]:
    """(passes, reason) for approving a file of this kind with this QA verdict."""
    need = min_score(kind, cfg)
    if need is None:
        return True, ""
    if not qa:
        return False, f"not reviewed yet (gate {need}/10) — run 'qa' first or give a reason"
    if int(qa.get("score", 0)) < need:
        return False, f"QA {qa.get('score')}/10 is below the {need}/10 gate"
    return True, ""


# ---- data ---------------------------------------------------------------------------------
def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except ValueError:
        return default


def _qa(f: Path) -> dict | None:
    data = _load(f.with_suffix(".qa.json"), None)
    if not data:
        return None
    return {k: data.get(k) for k in ("verdict", "score", "summary", "issues", "fix_route", "edit_instruction", "people")}


def _training_gate(target: str) -> str:
    try:
        from .jobs import check_training_set
        from .library import Library
        problems = check_training_set(Library.load(), target)
    except Exception as err:  # noqa: BLE001 — the gallery must never fail because of a check
        return f"Training gate not available: {err}"
    return "✓ Ready to train — the kept set passes the training gate" if not problems else "✗ Not ready to train: " + "; ".join(problems)


def _place(rel: str, kind: str) -> tuple[str, str]:
    """(section, sub-group) of a batch folder for the sidebar."""
    parts = rel.split("/")
    if kind == "keyframe" and "keyframes" in parts:
        i = parts.index("keyframes")
        return "keyframe", parts[i + 1] if len(parts) > i + 1 else ""
    if kind == "clip" and "clips" in parts:
        i = parts.index("clips")
        return "clip", parts[i + 1] if len(parts) > i + 1 else ""
    return kind, ""


def collect(root: Path) -> dict:
    cfg = gate_config()
    groups: dict[tuple, dict] = {}
    for manifest in sorted(root.rglob("manifest.json")):
        folder = manifest.parent
        data = _load(manifest, {})
        kind = data.get("kind", "other")
        rel = folder.relative_to(root).as_posix()
        approval = _load(folder / "approved.json", None)
        rejected = set(_load(folder / "rejected.json", {}).get("files", []))
        notes = _load(folder / "notes.json", {})
        files = []
        for f in sorted(p for p in folder.iterdir() if p.suffix.lower() in MEDIA):
            media = "image" if f.suffix.lower() in IMAGES else "video" if f.suffix == ".mp4" else "audio"
            files.append({"name": f.name, "url": "/file/" + urllib.parse.quote(f"{rel}/{f.name}"), "media": media,
                          "qa": _qa(f) if media == "image" else None, "note": notes.get(f.name, ""),
                          "rejected": f.name in rejected,
                          "approved": bool(approval and approval.get("file") == f.name)})
        if not files:
            continue
        curate = kind == "training_set"
        section, sub = _place(rel, kind)
        key = (kind, rel) if curate else (kind, str(data.get("target", rel)))
        g = groups.setdefault(key, {"kind": kind, "section": section, "sub": sub, "target": str(data.get("target", rel)),
                                    "curate": curate, "checklist": CHECKLISTS.get(kind, []), "versions": [],
                                    "gate": min_score(kind, cfg)})
        g["versions"].append({"folder": rel, "batch": folder.name, "model": str(data.get("model_id", "")),
                              "prompt": data.get("prompt", ""), "files": files,
                              "approval": approval})
        if curate:
            g["training_gate"] = _training_gate(g["target"])
    out = []
    for g in groups.values():
        g["versions"].sort(key=lambda v: v["batch"])
        approved = [(v, f) for v in g["versions"] for f in v["files"] if f["approved"]]
        approved_at = max((v["batch"] for v, _ in approved), default="")
        newer = [f for v in g["versions"] if v["batch"] > approved_at for f in v["files"] if not f["rejected"]]
        scores = [f["qa"]["score"] for v in g["versions"] for f in v["files"] if f["qa"]]
        cur = approved[-1][1] if approved else None
        ok, why = gate_check(g["kind"], cur["qa"] if cur else None, cfg) if cur else (False, "")
        override = (approved[-1][0]["approval"] or {}).get("override") if approved else None
        if g["curate"]:
            status = "curate"
        elif not cur:
            status = "pending"
        elif not ok and not override:
            status = "below_gate"
        elif newer and approved_at:
            status = "newer"
        else:
            status = "ok"
        g.update({"status": status, "best": max(scores, default=None), "approved_score": cur["qa"]["score"] if cur and cur["qa"] else None,
                  "newer": len(newer) if approved else 0, "gate_reason": why, "override": override,
                  "count": sum(len(v["files"]) for v in g["versions"])})
        out.append(g)
    out.sort(key=lambda g: ([s for s, _ in SECTIONS].index(g["section"]) if g["section"] in [s for s, _ in SECTIONS] else 99,
                            g["sub"], _natural(g["target"])))
    roster = [{"target": g["target"], "url": f["url"]} for g in out if g["kind"] == "anchor"
              for v in g["versions"] for f in v["files"] if f["approved"]]
    return {"root": str(root), "sections": SECTIONS, "groups": out, "roster": roster, "gate": cfg.get("min_score", {})}


def _natural(text: str) -> list:
    import re
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", text)]


# ---- actions -----------------------------------------------------------------------------
def approve(root: Path, folder: str, name: str, reason: str = "") -> dict:
    path = (root / folder).resolve()
    if root not in path.parents and path != root:
        return {"ok": False, "error": "outside the gallery folder"}
    f = path / Path(name).name
    if not f.exists():
        return {"ok": False, "error": "file not found"}
    kind = _load(path / "manifest.json", {}).get("kind", "")
    qa = _qa(f) if f.suffix.lower() in IMAGES else None
    ok, why = gate_check(kind, qa)
    if not ok and not reason.strip():
        return {"ok": False, "gate": True, "error": why}
    record = {"file": f.name, "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    if qa:
        record["qa_score"] = qa.get("score")
    if not ok:
        record["override"] = reason.strip()
    (path / "approved.json").write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
    supersede_siblings(path)
    return {"ok": True}


def _same_target(a: dict, b: dict) -> bool:
    strip = lambda t: re.sub(r"\s*\([^)]*\)\s*$", "", str(t or ""))  # noqa: E731 — 'beat 2.5 (egyptian)' = 'beat 2.5'
    return a.get("kind") == b.get("kind") and strip(a.get("target")) == strip(b.get("target"))


def supersede_siblings(path: Path) -> list[Path]:
    """One approved take per target: other batches of the same kind and target in the same parent folder lose their
    approval (kept as approved.superseded.json for the record)."""
    mine = _load(path / "manifest.json", {})
    moved = []
    for other in path.parent.iterdir():
        flag = other / "approved.json"
        if other == path or not flag.exists() or not _same_target(mine, _load(other / "manifest.json", {})):
            continue
        flag.replace(other / "approved.superseded.json")
        moved.append(other)
    return moved


def unapprove(root: Path, folder: str, name: str) -> dict:
    """Undo an approval (kept as approved.reverted.json). If approving it had superseded another take of the same
    target, the most recently superseded one is approved again."""
    path = (root / folder).resolve()
    if root not in path.parents and path != root:
        return {"ok": False, "error": "outside the gallery folder"}
    flag = path / "approved.json"
    if _load(flag, {}).get("file") != Path(name).name:
        return {"ok": False, "error": "this take is not the approved one"}
    flag.replace(path / "approved.reverted.json")
    mine = _load(path / "manifest.json", {})
    previous = sorted((p for p in path.parent.glob("*/approved.superseded.json")
                       if p.parent != path and _same_target(mine, _load(p.parent / "manifest.json", {}))),
                      key=lambda p: p.stat().st_mtime)
    if previous:
        restored = previous[-1]
        restored.replace(restored.with_name("approved.json"))
        return {"ok": True, "restored": f"{restored.parent.name}/{_load(restored.with_name('approved.json'), {}).get('file', '')}"}
    return {"ok": True, "restored": None}


def note(root: Path, folder: str, name: str, text: str) -> dict:
    path = (root / folder).resolve()
    if root not in path.parents and path != root:
        return {"ok": False, "error": "outside the gallery folder"}
    notes = _load(path / "notes.json", {})
    if text.strip():
        notes[Path(name).name] = text.strip()
    else:
        notes.pop(Path(name).name, None)
    (path / "notes.json").write_text(json.dumps(notes, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}


def toggle(root: Path, folder: str, name: str) -> dict:
    path = (root / folder).resolve()
    if root not in path.parents and path != root:
        return {"ok": False, "error": "outside the gallery folder"}
    files = set(_load(path / "rejected.json", {}).get("files", []))
    files ^= {Path(name).name}
    (path / "rejected.json").write_text(json.dumps({"files": sorted(files)}), encoding="utf-8")
    return {"ok": True}


# ---- page -------------------------------------------------------------------------------
PAGE = r"""<!doctype html><html><head><meta charset="utf-8"><title>MTower review</title>
<style>
*{box-sizing:border-box}body{margin:0;font-family:Segoe UI,Arial,sans-serif;background:#0f1012;color:#e6e6e6;height:100vh;display:grid;
grid-template-rows:auto 1fr;grid-template-columns:290px 1fr;grid-template-areas:"top top" "side main"}
header{grid-area:top;display:flex;gap:14px;align-items:center;padding:8px 14px;background:#17181b;border-bottom:1px solid #2a2b30;flex-wrap:wrap}
header h1{font-size:16px;font-weight:600;margin:0 8px 0 0}.tabs button,.filters button{background:#24252a;color:#ccc;border:0;padding:6px 10px;
border-radius:6px;cursor:pointer;font-size:13px}.tabs button.on,.filters button.on{background:#3b5bdb;color:#fff}.tabs,.filters{display:flex;gap:4px;flex-wrap:wrap}
.count{opacity:.7;font-size:11px;margin-left:4px}#search{background:#24252a;border:0;color:#eee;padding:6px 8px;border-radius:6px;width:150px}
.help{margin-left:auto;font-size:12px;color:#888}
aside{grid-area:side;overflow:auto;border-right:1px solid #2a2b30;background:#131417}
aside .sub{font-size:11px;text-transform:uppercase;color:#777;padding:10px 12px 4px}
aside .item{display:flex;align-items:center;gap:8px;padding:7px 12px;cursor:pointer;border-left:3px solid transparent;font-size:13px}
aside .item:hover{background:#1c1d21}aside .item.sel{background:#1f2a4d;border-left-color:#5c7cfa}
.dot{width:9px;height:9px;border-radius:50%;flex:none}.st-ok{background:#2f9e44}.st-newer{background:#f59f00}.st-pending{background:#868e96}
.st-below_gate{background:#e03131}.st-curate{background:#7048e8}.chip{font-size:11px;padding:1px 6px;border-radius:9px;background:#2a2b30;color:#ccc}
.chip.g{background:#1e4620;color:#8ce99a}.chip.y{background:#4a3a0f;color:#ffd43b}.chip.r{background:#4d1a1a;color:#ffa8a8}
.item .t{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
main{grid-area:main;overflow:auto;padding:14px 18px}
.head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}.head h2{margin:0;font-size:20px}.head .nav{margin-left:auto;display:flex;gap:6px}
button.act{background:#2b2d33;color:#eee;border:0;padding:8px 12px;border-radius:6px;cursor:pointer;font-size:13px}button.act:hover{background:#3a3d45}
button.primary{background:#2f9e44}button.primary:hover{background:#37b24d}button.warn{background:#a61e4d}
.stage{display:grid;gap:12px;margin-top:10px}.stage.two{grid-template-columns:1fr 1fr}.pane{background:#16171a;border-radius:8px;padding:8px;position:relative}
.pane .lbl{font-size:12px;color:#aaa;margin-bottom:6px;display:flex;gap:8px;align-items:center}
.pane img,.pane video{width:100%;max-height:62vh;object-fit:contain;display:block;background:#000;border-radius:4px;cursor:zoom-in}
.pane audio{width:100%}.qa{font-size:13px;line-height:1.45;margin-top:8px}.qa ul{margin:4px 0;padding-left:18px}.qa li{margin-bottom:3px}
.sev-critical,.sev-major{color:#ffa8a8}.sev-minor{color:#adb5bd}.actions{display:flex;gap:8px;align-items:center;margin-top:10px;flex-wrap:wrap}
.actions input{flex:1;min-width:220px;background:#24252a;border:0;color:#eee;padding:8px;border-radius:6px}
.gate{font-size:12px;padding:6px 10px;border-radius:6px;background:#2a2b30}.gate.bad{background:#4d1a1a;color:#ffc9c9}.gate.good{background:#1e4620;color:#b2f2bb}
.strip{display:flex;gap:8px;overflow-x:auto;padding:10px 0;margin-top:8px;border-top:1px solid #2a2b30}
.thumb{flex:none;width:170px;cursor:pointer;border:2px solid transparent;border-radius:6px;background:#16171a;padding:4px;position:relative}
.thumb img,.thumb video{width:100%;height:92px;object-fit:cover;border-radius:3px;display:block}.thumb .audio{height:92px;display:flex;align-items:center;
justify-content:center;font-size:12px;text-align:center;padding:4px;color:#ccc}.thumb.sel{border-color:#5c7cfa}.thumb.appr{box-shadow:0 0 0 2px #2f9e44 inset}
.thumb.rej{opacity:.35}.thumb .meta{font-size:11px;color:#aaa;display:flex;justify-content:space-between;margin-top:3px}
.badge{position:absolute;top:6px;left:6px;font-size:11px;background:#2f9e44;color:#fff;border-radius:4px;padding:0 5px}
details{margin-top:8px;font-size:13px;color:#aaa}details p{white-space:pre-wrap}.checks{font-size:12px;color:#fcc419;margin:6px 0 0;padding-left:18px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:10px;margin-top:10px}.grid .card{background:#16171a;padding:6px;border-radius:6px;border:2px solid #2f9e44}
.grid .card.rej{border-color:#e03131;opacity:.5}.grid img{width:100%;display:block;border-radius:3px}.grid .cap{font-size:11px;color:#aaa;margin:4px 0}
.roster{display:flex;gap:6px;overflow-x:auto;margin:8px 0}.roster figure{margin:0;text-align:center;font-size:10px;color:#aaa}.roster img{height:90px;display:block}
#zoom{position:fixed;inset:0;background:rgba(0,0,0,.92);display:none;align-items:center;justify-content:center;z-index:9;cursor:zoom-out}
#zoom img{max-width:96vw;max-height:96vh}.empty{color:#888;padding:40px;text-align:center}
</style></head><body>
<header><h1>MTower review</h1><div class="tabs" id="tabs"></div><div class="filters" id="filters"></div>
<input id="search" placeholder="Filter, e.g. 2.5"><span class="help">↑↓ shot · ←→ candidate · A approve · C compare · N note · Z zoom</span></header>
<aside id="side"></aside><main id="main"></main><div id="zoom" onclick="this.style.display='none'"><img></div>
<script>
let D=null,S={section:"keyframe",filter:"todo",sel:null,file:null,compare:true,q:""};
const FILTERS=[["todo","Needs decision"],["below_gate","Approved below gate"],["newer","Newer candidates"],["pending","Not approved"],["ok","Approved ✓"],["all","All"]];
const $=s=>document.querySelector(s);
function esc(t){return (t??"").toString().replace(/[&<>"]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]))}
function chip(s,gate){if(s==null)return '<span class="chip">–</span>';const c=gate==null?"":s>=gate?"g":s>=gate-2?"y":"r";return `<span class="chip ${c}">${s}/10</span>`}
function match(g){if(g.section!==S.section)return false;if(S.q&&!g.target.toLowerCase().includes(S.q.toLowerCase()))return false;
 return inF(g,S.filter)}
function inF(g,k){if(k==="all")return true;if(k==="todo")return ["pending","newer","below_gate","curate"].includes(g.status);if(k==="newer")return g.newer>0;return g.status===k}
function files(g){const out=[];g.versions.slice().reverse().forEach(v=>v.files.forEach(f=>out.push({...f,v})));return out}
async function load(keep){const r=await fetch("/api/data");D=await r.json();render(keep)}
function render(keep){if(!D)return;
 const counts={};D.groups.forEach(g=>{counts[g.section]=(counts[g.section]||0)+(["pending","newer","below_gate","curate"].includes(g.status)?1:0)});
 $("#tabs").innerHTML=D.sections.filter(([k])=>D.groups.some(g=>g.section===k)).map(([k,n])=>`<button class="${S.section===k?"on":""}" onclick="S.section='${k}';S.sel=null;render()">${n}<span class="count">${counts[k]||""}</span></button>`).join("");
 $("#filters").innerHTML=FILTERS.map(([k,n])=>{const c=D.groups.filter(g=>g.section===S.section&&inF(g,k)).length;
   return `<button class="${S.filter===k?"on":""}" onclick="S.filter='${k}';S.sel=null;render()">${n}<span class="count">${c}</span></button>`}).join("");
 const list=D.groups.filter(match);
 if(!keep||!list.some(g=>key(g)===S.sel)){if(!list.some(g=>key(g)===S.sel)){S.sel=list.length?key(list[0]):null;S.file=null}}
 let html="",sub=null;list.forEach(g=>{if(g.sub!==sub){sub=g.sub;if(sub)html+=`<div class="sub">${esc(sub)}</div>`}
   const extra=g.newer?`<span class="chip y" title="newer candidates">+${g.newer}</span>`:"";
   html+=`<div class="item ${key(g)===S.sel?"sel":""}" onclick="pick('${esc(key(g))}')"><span class="dot st-${g.status}"></span><span class="t">${esc(g.target)}</span>${extra}${chip(g.best,g.gate)}</div>`});
 $("#side").innerHTML=html||'<div class="empty">Nothing here 🎉</div>';
 const g=list.find(g=>key(g)===S.sel);$("#main").innerHTML=g?view(g):'<div class="empty">Nothing to review with this filter.</div>';
 const s=$("#side .sel");if(s)s.scrollIntoView({block:"nearest"})}
function key(g){return g.kind+"|"+(g.curate?g.versions[0].folder:g.target)}
function pick(k){S.sel=k;S.file=null;render(true)}
function current(g){const fs=files(g);if(S.file){const f=fs.find(f=>f.v.folder+"/"+f.name===S.file);if(f)return f}
 const ap=fs.find(x=>x.approved);const newer=fs.filter(f=>!f.rejected&&f.v.batch>(ap?ap.v.batch:""));
 const pool=ap?(newer.length?newer:[ap]):fs;return pool.slice().sort((a,b)=>((b.qa?.score??-1)-(a.qa?.score??-1)))[0]}
function mediaTag(f,big){if(f.media==="image")return `<img src="${f.url}" ${big?`onclick="zoom('${f.url}')"`:'loading="lazy"'}>`;
 if(f.media==="video")return `<video src="${f.url}" ${big?"controls":"muted"} loop></video>`;
 return big?`<audio src="${f.url}" controls preload="none"></audio>`:`<div class="audio">♪ ${esc(f.name.replace(/\.(wav|mp3)$/,""))}</div>`}
function qaBlock(f){if(!f.qa)return f.media==="image"?'<div class="qa"><i>Not reviewed by QA yet.</i></div>':"";const q=f.qa;
 const issues=(q.issues||[]).map(i=>`<li class="sev-${i.severity}"><b>${i.severity}</b> · ${esc(i.category)} — ${esc(i.description)}<br><span style="color:#888">fix: ${esc(i.fix)}</span></li>`).join("");
 return `<div class="qa"><b>QA ${esc(q.verdict)} ${q.score}/10</b> · route <b>${esc(q.fix_route)}</b><div>${esc(q.summary)}</div><ul>${issues}</ul>${q.edit_instruction?`<div style="color:#888">edit: ${esc(q.edit_instruction)}</div>`:""}</div>`}
function view(g){
 if(g.curate)return curateView(g);
 const fs=files(g),f=current(g),ap=fs.find(x=>x.approved);
 const two=S.compare&&ap&&f&&ap!==f;
 const gateOk=g.gate==null||(f.qa&&f.qa.score>=g.gate);
 const gateTxt=g.gate==null?"":f.qa?(gateOk?`✓ passes the ${g.gate}/10 gate`:`✗ ${f.qa.score}/10 is below the ${g.gate}/10 gate — approving needs a reason`):`✗ not reviewed — approving needs a reason (or run qa)`;
 const pane=(x,label)=>`<div class="pane"><div class="lbl">${label} ${chip(x.qa?.score,g.gate)} <span>${esc(x.v.batch)}/${esc(x.name)}</span></div>${mediaTag(x,true)}${qaBlock(x)}</div>`;
 const strip=fs.map(x=>`<div class="thumb ${x===f?"sel":""} ${x.approved?"appr":""} ${x.rejected?"rej":""}" onclick="S.file='${esc(x.v.folder+"/"+x.name)}';render(true)">${x.approved?'<span class="badge">✓ approved</span>':""}${mediaTag(x,false)}<div class="meta"><span>${esc(x.v.batch.slice(4,13))}</span>${chip(x.qa?.score,g.gate)}${x.note?"✎":""}</div></div>`).join("");
 const ov=g.override?`<div class="gate bad">Approved by override: ${esc(g.override)}</div>`:"";
 const passing=fs.filter(x=>!x.approved&&!x.rejected&&x.qa&&g.gate!=null&&x.qa.score>=g.gate).sort((a,b)=>b.qa.score-a.qa.score)[0];
 let todo="";
 if(g.status==="pending")todo=passing?`<b>To do:</b> nothing is approved yet. The best take scores ${passing.qa.score}/10 and passes the gate — look at it and press <b>Approve</b>.`
   :`<b>To do:</b> nothing is approved yet and no take passes the ${g.gate??""}/10 gate. Approve the best one with a reason, or write in the note what is wrong and the director will redo the shot.`;
 else if(g.status==="below_gate")todo=passing?`<b>To do:</b> the approved take scores ${g.approved_score??"–"}/10 (below the ${g.gate}/10 gate). A newer take passes with ${passing.qa.score}/10 — it is shown on the right. If you agree it is better, press <b>Approve</b>.`
   :`<b>To do:</b> the approved take scores ${g.approved_score??"–"}/10 (below the ${g.gate}/10 gate) and no newer take passes yet. Either press <b>Keep approved take</b> and give a reason (a director's override), or write in the note what is wrong — the director will rework the shot design.`;
 else if(g.status==="newer")todo=`<b>Optional:</b> the approved take passes the gate. ${g.newer} newer take(s) exist — approve one only if you prefer it.`;
 else if(g.status==="ok")todo=`<b>Done ✓</b> — nothing to do for this one.`;
 const todoBox=todo?`<div class="gate ${g.status==="ok"?"good":""}" style="margin-top:8px;font-size:13px">${todo}</div>`:"";
 const keep=(g.status==="below_gate"&&ap)?`<button class="act warn" onclick="doKeep()">Keep approved take (give a reason)</button>`:"";
 const roster=g.kind==="anchor"?`<div class="roster">${D.roster.map(r=>`<figure><img src="${r.url}"><figcaption>${esc(r.target)}</figcaption></figure>`).join("")}</div>`:"";
 return `<div class="head"><h2>${esc(g.target)}</h2><span class="chip">${esc(g.kind)}</span>${chip(g.approved_score,g.gate)}
  ${g.newer?`<span class="chip y">${g.newer} newer candidate(s)</span>`:""}${g.status==="below_gate"?'<span class="chip r">approved below gate</span>':""}
  <div class="nav"><button class="act" onclick="S.compare=!S.compare;render(true)">${S.compare?"Single view":"Compare with approved"}</button>
  <button class="act" onclick="move(-1)">◀ Prev</button><button class="act" onclick="move(1)">Next ▶</button></div></div>${todoBox}${ov}${roster}
  <div class="stage ${two?"two":""}">${two?pane(ap,"Approved"):""}${pane(f,f.approved?"Approved":"Candidate")}</div>
  <div class="actions">${f.approved?'<span class="gate good">This is the approved take</span><button class="act warn" onclick="doUnapprove()">Undo approval</button>':`<button class="act primary" onclick="doApprove()">✓ Approve this (A)</button>`}${keep}
   ${gateTxt?`<span class="gate ${gateOk?"good":"bad"}">${gateTxt}</span>`:""}
   <input id="note" value="${esc(f.note)}" placeholder="What is wrong? (saved automatically)" onkeydown="if(event.key==='Enter')this.blur()" onchange="doNote('${esc(f.v.folder)}','${esc(f.name)}',this.value)"><span id="noteok" class="gate good" style="display:none">✓ note saved</span></div>
  <div class="strip">${strip}</div>
  ${g.checklist.length?`<ul class="checks">${g.checklist.map(c=>`<li>${esc(c)}</li>`).join("")}</ul>`:""}
  <details><summary>Prompt & model (${esc(f.v.model)})</summary><p>${esc(f.v.prompt)}</p></details>`}
function curateView(g){const v=g.versions[0];const kept=v.files.filter(f=>!f.rejected).length;
 return `<div class="head"><h2>${esc(g.target)}</h2><span class="chip">training set · ${esc(v.batch)}</span><span class="chip">kept ${kept} of ${v.files.length}</span>
 <div class="nav"><button class="act" onclick="move(-1)">◀ Prev</button><button class="act" onclick="move(1)">Next ▶</button></div></div>
 <div class="gate ${g.training_gate.startsWith("✓")?"good":"bad"}" style="margin-top:8px">${esc(g.training_gate)}</div>
 <ul class="checks">${g.checklist.map(c=>`<li>${esc(c)}</li>`).join("")}</ul>
 <div class="grid">${v.files.map(f=>`<div class="card ${f.rejected?"rej":""}"><img src="${f.url}" loading="lazy" onclick="zoom('${f.url}')"><button class="act ${f.rejected?"":"warn"}" style="width:100%;margin-top:4px" onclick="doToggle('${esc(v.folder)}','${esc(f.name)}')">${f.rejected?"✗ Rejected — keep":"✓ Kept — reject"}</button></div>`).join("")}</div>`}
function move(d){const list=D.groups.filter(match);const i=list.findIndex(g=>key(g)===S.sel);const n=list[Math.min(list.length-1,Math.max(0,i+d))];if(n)pick(key(n))}
function moveFile(d){const g=D.groups.find(g=>key(g)===S.sel);if(!g||g.curate)return;const fs=files(g),f=current(g);const i=fs.indexOf(f);const n=fs[Math.min(fs.length-1,Math.max(0,i+d))];S.file=n.v.folder+"/"+n.name;render(true)}
async function post(url,body){const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});return r.json()}
async function doKeep(){const g=D.groups.find(g=>key(g)===S.sel),ap=files(g).find(x=>x.approved);if(!ap)return;
 const why=prompt("Keep the approved take although it scores below the gate.\nDirector's override — type the reason (e.g. 'good enough for a 2-second cut'):");if(!why)return;
 const res=await post("/api/approve",{folder:ap.v.folder,file:ap.name,reason:why});if(!res.ok){alert(res.error);return}await load(true)}
async function doApprove(){const g=D.groups.find(g=>key(g)===S.sel),f=current(g);let res=await post("/api/approve",{folder:f.v.folder,file:f.name});
 if(!res.ok&&res.gate){const why=prompt(res.error+"\n\nDirector's override — type the reason to approve anyway:");if(!why)return;res=await post("/api/approve",{folder:f.v.folder,file:f.name,reason:why})}
 if(!res.ok){alert(res.error);return}S.file=null;await load(true)}
async function doNote(folder,file,val){const res=await post("/api/note",{folder,file,note:val});if(!res.ok){alert(res.error);return}
 for(const g of D.groups)for(const v of g.versions)if(v.folder===folder)for(const x of v.files)if(x.name===file)x.note=val.trim();
 const ok=$("#noteok");if(ok&&$("#note")?.value===val){ok.style.display="inline-block";setTimeout(()=>{ok.style.display="none"},1500)}else render(true)}
async function doUnapprove(){const g=D.groups.find(g=>key(g)===S.sel),f=current(g);if(!confirm("Undo the approval of "+f.name+"?"))return;
 const res=await post("/api/unapprove",{folder:f.v.folder,file:f.name});if(!res.ok){alert(res.error);return}
 if(res.restored)alert("Approval removed. The previously approved take is approved again: "+res.restored);S.file=f.v.folder+"/"+f.name;await load(true)}
async function doToggle(folder,file){await post("/api/toggle",{folder,file});await load(true)}
function zoom(u){const z=$("#zoom");z.querySelector("img").src=u;z.style.display="flex"}
$("#search").oninput=e=>{S.q=e.target.value;S.sel=null;render()};
document.addEventListener("keydown",e=>{if(e.target.tagName==="INPUT")return;const k=e.key.toLowerCase();
 if(k==="arrowdown"||k==="j"){move(1);e.preventDefault()}else if(k==="arrowup"||k==="k"){move(-1);e.preventDefault()}
 else if(k==="arrowright"){moveFile(1)}else if(k==="arrowleft"){moveFile(-1)}else if(k==="a"){doApprove()}
 else if(k==="c"){S.compare=!S.compare;render(true)}else if(k==="n"){e.preventDefault();$("#note")?.focus()}
 else if(k==="z"){const i=$(".pane img:last-of-type");if(i)zoom(i.src)}else if(k==="escape"){$("#zoom").style.display="none"}});
load();
</script></body></html>"""


def byte_range(header: str | None, size: int) -> tuple[int | None, int]:
    """(start, end) inclusive for an HTTP Range header; (None, 0) when unsatisfiable; the whole file when absent."""
    if size == 0:
        return (0, -1) if not header else (None, 0)
    m = re.fullmatch(r"\s*bytes=(\d*)-(\d*)\s*", header or "")
    if not m or (not m.group(1) and not m.group(2)):
        return (0, size - 1) if not header or not m else (None, 0)
    if not m.group(1):
        n = int(m.group(2))
        return (max(0, size - n), size - 1) if n else (None, 0)
    start = int(m.group(1))
    end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
    return (start, end) if start <= end else (None, 0)


def serve(root: Path, port: int = 8765, open_browser: bool = True) -> None:
    root = root.resolve()

    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store" if not ctype.startswith(("image", "video", "audio")) else "max-age=3600")
            self.end_headers()
            self.wfile.write(body)

        def _send_file(self, target: Path, ctype: str) -> None:
            # Browsers play long videos through byte-range requests; without 206 answers they stall partway.
            size = target.stat().st_size
            start, end = byte_range(self.headers.get("Range"), size)
            if start is None:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            partial = (start, end) != (0, size - 1) or self.headers.get("Range") is not None
            self.send_response(206 if partial else 200)
            self.send_header("Content-Type", ctype)
            self.send_header("Accept-Ranges", "bytes")
            self.send_header("Content-Length", str(end - start + 1))
            if partial:
                self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            self.send_header("Cache-Control", "max-age=3600")
            self.end_headers()
            try:
                with target.open("rb") as fh:
                    fh.seek(start)
                    left = end - start + 1
                    while left > 0:
                        chunk = fh.read(min(1 << 20, left))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        left -= len(chunk)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass  # the player cancelled this range to ask for another one

        def _json(self, data: dict) -> None:
            self._send(200, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def do_GET(self):  # noqa: N802
            if self.path.startswith("/file/"):
                target = (root / urllib.parse.unquote(self.path[6:])).resolve()
                if root not in target.parents or not target.is_file():
                    return self._send(404, b"not found", "text/plain")
                ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                return self._send_file(target, ctype)
            if self.path.startswith("/api/data"):
                return self._json(collect(root))
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")

        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", 0))
            try:
                body = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
            except ValueError:
                return self._json({"ok": False, "error": "bad request"})
            folder, name = body.get("folder", ""), body.get("file", "")
            if self.path == "/api/approve":
                return self._json(approve(root, folder, name, body.get("reason", "")))
            if self.path == "/api/unapprove":
                return self._json(unapprove(root, folder, name))
            if self.path == "/api/note":
                return self._json(note(root, folder, name, body.get("note", "")))
            if self.path == "/api/toggle":
                return self._json(toggle(root, folder, name))
            self._json({"ok": False, "error": "unknown action"})

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://localhost:{port}/"
    print(f"Review gallery running at {url} — press Ctrl+C to stop.")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
