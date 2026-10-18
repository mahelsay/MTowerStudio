"""One-off voice bake-off for the Dialogue Test: the same acted lines on four Azure engines. Run from engine."""
import base64, json, sys, urllib.request, urllib.error
from datetime import datetime
from mtower.providers.azure import AzureClient
from mtower.settings import load_env, media_root
from mtower import voice

load_env()
c = AzureClient()
OUT = media_root() / "productions/thunderbolt/ep01_romani/audio/voice_test" / datetime.now().strftime("%Y%m%d-%H%M%S")
OUT.mkdir(parents=True)

DIALECT = ("Speak in natural Egyptian Arabic (Cairo dialect, 1970s Egyptian army), never formal Arabic. "
           "Read the text exactly as written, word for word; do not add, translate or explain anything.")
LINES = [
    ("A_squadron_leader", "SQUADRON LEADER (T.3)", "ash",
     "يا حمدي… الرادار لاقط سرب فانتوم. هنضطر ننزّل القوة كلها في أقرب منطقة.",
     "A helicopter pilot in his thirties shouting over the roar of rotors into an intercom: urgent, tense, clipped, but in control."),
    ("B_sayed_mostafa", "SAYED (1.2)", "onyx",
     "خايف؟ … كدّاب… وأنا كمان خايف.",
     "A weathered sergeant in his forties talking quietly to a scared young soldier the night before battle: warm, dry, almost a smile; a pause after the first word."),
    ("C_shalabi_whisper", "SHALABI (3.4)", "echo",
     "محدش يشتبك. سيبوهم يعدّوا.",
     "A commando captain lying in a hole as enemy tanks pass a few metres away, whispering into a radio handset: barely audible, steely, absolutely calm."),
    ("D_sayed_letter", "SAYED letter (5.6)", "onyx",
     "فاطمة… لو الجواب ده وصلّك من إيد غير إيدي، يبقى ربنا اختارلي الخير. ما تعيّطيش قدّام علي. قولّيله إن أبوه راح عشان نرجع السويس.",
     "A soldier's farewell letter read in his own voice: soft, slow, loving, holding back tears; not theatrical."),
    ("E_narrator_hamdi", "NARRATOR — Hamdi Shalabi remembering (2.5)", "ash",
     "عشرين كيلو في الميّة المالحة والطين… الميّة كانت لحد نص السمانة، وساعات لحد الركبة. كل خطوة كانت خناقة مع الأرض. والملح… كان بياكل في كل جرح في رجلينا. بس محدش فينا نزّل سلاحه تحت الميّة. ولا واحد.",
     "An old Egyptian officer in his seventies remembering the war fifty years later, speaking to the camera: deep, grainy, quiet pride, the weight of memory; unhurried, with real pauses."),
]


def post(url, body, headers):
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Authorization": "Bearer " + c.token(), "Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code} {e.read().decode('utf-8', 'replace')[:300]}") from None


def mini_tts(key, text, direction, v):
    data = post(f"{c.endpoint}/openai/deployments/me-eus2-gpt-4o-mini-tts/audio/speech?api-version=2025-03-01-preview",
                {"model": "gpt-4o-mini-tts", "input": text, "voice": v, "response_format": "wav",
                 "instructions": DIALECT + " Delivery: " + direction}, {})
    (OUT / f"{key}__gpt-4o-mini-tts.wav").write_bytes(data)


def gpt_audio(key, text, direction, v):
    data = json.loads(post(f"{c.endpoint}/openai/deployments/me-eus2-gpt-audio-1-5/chat/completions?api-version=2025-04-01-preview",
                           {"modalities": ["text", "audio"], "audio": {"voice": v, "format": "wav"},
                            "messages": [{"role": "system", "content": "You are a voice actor. " + DIALECT + " Delivery: " + direction},
                                         {"role": "user", "content": "Perform this line exactly:\n" + text}]}, {}))
    (OUT / f"{key}__gpt-audio-1.5.wav").write_bytes(base64.b64decode(data["choices"][0]["message"]["audio"]["data"]))


def azure_voice(key, text, name, tag):
    voice.synthesize(c, name, text, OUT / f"{key}__{tag}.wav", rate="+0%")


results = []
for key, who, v, text, direction in LINES:
    for engine, fn in (("gpt-4o-mini-tts", lambda: mini_tts(key, text, direction, v)),
                       ("gpt-audio-1.5", lambda: gpt_audio(key, text, direction, v)),
                       ("azure-shakir", lambda: azure_voice(key, text, "ar-EG-ShakirNeural", "azure-shakir")),
                       ("azure-omni-andrew", lambda: azure_voice(key, text, "en-US-Andrew:DragonHDOmniLatestNeural", "azure-omni-andrew"))):
        try:
            fn(); results.append((key, engine, "ok"))
        except Exception as e:  # noqa: BLE001
            results.append((key, engine, str(e)[:160]))
        print(key, engine, results[-1][2], flush=True)

(OUT / "manifest.json").write_text(json.dumps({"kind": "narration", "target": "voice test — dialogue + Hamdi narrator",
    "model_id": "gpt-4o-mini-tts · gpt-audio-1.5 · Azure ar-EG-Shakir · Azure DragonHD Omni (Andrew)",
    "prompt": " || ".join(f"{k} {w}: {t}" for k, w, _, t, _ in LINES)}, ensure_ascii=False, indent=2), encoding="utf-8")
print(OUT)
