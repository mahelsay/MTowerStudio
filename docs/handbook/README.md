# MTower Studio Handbook

How the studio works: the pipeline, the rules, and the words you'll meet along the way. Written for a first-time filmmaker.

---

## 1. The studio in one picture

```
studio/library  ──►  productions/<series or film>/<episode>  ──►  studio/engine  ──►  finished episode
(reusable world)      (story, casting, shot lists)                (makes the media)
```

- **The library** is the studio's virtual world: actors, costumes, places, vehicles, props, and film looks. It grows with every production.
- **A production** is a series episode or a film. It has its own story, characters, and shot lists, and it *casts* its characters from library actors.
- **The engine** reads a production's shot lists and calls the AI tools to make images, video, and voice, asking for approval before spending money.

## 2. The pipeline (every production)

| Phase | What happens | Main outputs | Folder |
|---|---|---|---|
| **1. Development** | Research, story, characters, screenplay → executive sign-off | Episode plan, characters, screenplay | `01_development/` |
| **2. Pre-production** | Visual guide, casting, shot lists; build and test references and face models; look test; animatic | Casting, shot lists, approved references, animatic | `02_preproduction/` |
| **3. Production & post** | Voice, video in batches, music and sound, edit, color, upscale, subtitles | The finished episode | `03_production/` |

Rule: **never generate final media before the script and shot list are locked.**

## 3. Casting and face models

<a id="casting-and-face-models"></a>

How a library actor's face is locked (done once per actor, then reused forever):

| Step | What happens | Who | Output |
|---|---|---|---|
| 1. Anchor | The engine generates **8 candidate portraits** from the actor's description (`REF_ANCHOR`) | Engine | 8 images |
| 2. Pick | **You choose the one face** that *is* this actor | **You** | 1 anchor image |
| 3. Training set | From the anchor, a reference-editing model creates **~25 images of the same face** in different angles, lights, and expressions | Engine | ~25 images |
| 4. Curate | **You remove** any image where the face drifted | **You** | 15–20 images |
| 5. Train | The engine trains the actor's **LoRA** with its trigger word (e.g., `act0003karim`) | Engine | 1 face model |
| 6. Test | 6 test images (`REF_*` variations: day, night, profile, full body, expression) | Engine → **You approve** | Actor `locked` |

About 40 images and one training run per actor. The engine estimates the cost before running.

Then, for each production: **cast** the character (actor + wardrobe + character additions) in `casting.json`. Costumes and wear states are added by the prompt, so the same face can wear a 1973 uniform in one film and a 2010 suit in another.

## 4. Studio rules

1. **Real people:** shown only through sourced actions; no invented private lives; their stand-in actors are `locked_to_role`.
2. **Disputed facts:** stay neutral, or are attributed ("according to Egyptian sources…").
3. **Violence:** restrained — implied, never graphic.
4. **Write to AI's strengths:** narration, letters in voiceover, short dialogue, faces in profile or shadow when speaking.
5. **Images first, motion second. Animatic before video. Cheap drafts before premium finals.**
6. **Spending:** every platform has a cap; the engine estimates and asks before every batch.
7. **Secrets:** API keys only in a local `.env` file — never in chat, never in git.
8. **Media in the cloud, text in git.**

## 5. Glossary

| Term | Plain meaning |
|---|---|
| **Act** | A big section of an episode. Our episodes: a teaser + five acts. |
| **Act-out** | The strong moment that ends an act and pulls you into the next one. |
| **Anchor image** | The one approved picture that defines what an actor, place, or object looks like. |
| **Animatic** | The whole episode cut together from still images, narration, and temporary sound — watched before paying for video. |
| **API** | A programmable connection that lets our scripts use an AI tool instead of clicking on its website. |
| **Aspect ratio** | The frame's shape. We deliver 2.39:1 (wide cinema frame). |
| **Beat** | One small moment in a scene. Each beat becomes a few shots. |
| **Casting** | Choosing which library actor plays which character in a production. |
| **Character** | A role in one story (e.g., Private Mostafa). |
| **Actor (virtual)** | A reusable face and body in the library (e.g., Karim Nour). |
| **Clip** | One generated video shot, usually 5–10 seconds. |
| **Keyframe** | The still image a video clip starts from. |
| **LoRA** | A small custom add-on model trained on one face, so the image model draws that person every time. |
| **Lock** | Approve and freeze something, so later work can build on it safely. |
| **Plate** | A reference image of a place with no main characters in it. |
| **Prompt** | The text instruction given to an AI tool. |
| **Shot** | One continuous camera view, from cut to cut. |
| **Shot list** | The table of every shot, with framing, lens, light, motion, and prompts — the engine's recipe. |
| **Teaser / cold open** | The gripping minutes before the main title. |
| **Trigger word** | The special word that activates an actor's LoRA in a prompt. |
| **VO (voiceover)** | A voice heard but not seen — the narrator, or a letter being read. |
| **Wear state** | How worn a costume looks at that moment in the story (clean, muddy, salt-crusted…). |
