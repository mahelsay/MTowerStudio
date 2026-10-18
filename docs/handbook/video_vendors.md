# Video vendors — research (2026-10-12)

Why: Azure Foundry has only Sora 2 for video, and Microsoft says it "blocks all IP and photorealistic content". The user asked whether going direct to video vendors is more professional than fal.ai before paying for the Look Test (task 2.5).

Figures come from vendors' official pricing and docs pages, fetched 2026-10-12. "n/v" means not verified. Prices are USD per second of output video.

## Comparison

| Option | 720p | 1080p | Audio | Max clip | Realistic adults (image → video) | Children | vs fal |
|---|---|---|---|---|---|---|---|
| Google Vertex AI — Veo 3.1 | $0.40 with audio / $0.20 without | same | optional | 4/6/8 s (extension: +7 s at 720p, up to 148 s) | yes (`allow_adult`) | only with an allowlisted project and `allow_all` | same with audio; half price without |
| Vertex — Veo 3.1 Fast | $0.10 / $0.08 | $0.12 / $0.10 | optional | 4/6/8 s | yes | as above | 33% cheaper than fal ($0.15) |
| Vertex — Veo 3.1 Lite (preview) | $0.05 / $0.03 | $0.08 / $0.05 | optional | 4/6/8 s | yes | as above | same with audio |
| Gemini API — Veo 3.1 / Fast / Lite (preview) | $0.40 / $0.10 / $0.05 | $0.40 / $0.12 / $0.08 | always on | 4/6/8 s | yes | **no** (MENA, including the UAE: `allow_adult` only) | Fast cheaper |
| Runway — Gen-4.5 | $0.12 | — | none listed | 2–10 s | allowed | allowed in non-harmful scenes ("stricter standard") | not on fal |
| Kling direct — 3.0 | $0.084 / $0.126 with audio | $0.112 / $0.168 | optional | 3–15 s | n/v | n/v | cheaper at 720p |
| Kling direct — 2.5 Turbo | $0.042 | $0.07 | — | — | n/v | n/v | same at 1080p |
| BytePlus — Seedance 2.0 / 2.5 | $0.15 / $0.231 | $0.37 / $0.569 | n/v | n/v | n/v | n/v | — |
| MiniMax — H3 | $0.08 (768p) | $0.13 (2K) | n/v | n/v | n/v | n/v | — |
| fal.ai (today) | Veo 3.1 $0.40 · Fast $0.15 · Lite $0.05 · Kling v3 / O3 Pro $0.14 · Kling 2.5 Turbo $0.07 | | | | | | |

**Sora 2 is out.** Azure blocks photorealistic content. The research agent also reported that OpenAI shut down Sora 2 and its Videos API on 2026-09-24, and that the API rejected input images with human faces even before that; we didn't check either claim against the source ourselves.

## Notes

- **Veo:**
  - Clips stop at 8 s, so shots of 9–13 s need the extension feature or a different model.
  - Supports first/last frame and up to 3 reference images.
  - Vertex runs in us-central1 only, with a quota of 50 requests per minute; the model is generally available.
  - Gemini API: $5 minimum prepay; rate tiers based on spend (Tier 1: $10 per 10 minutes, $250 cap).
  - On the paid tier, Google says it doesn't use your content to improve its products.
  - Videos are kept for 2 days and carry an invisible SynthID watermark.
  - fal's Veo very likely runs on Google's backend, so the same rules on children likely apply there too (inference).
- **Runway:**
  - Image-to-video uses the first frame only; 1280:720 output; ProRes and HDR cost extra.
  - Bans graphic violence and gore, not war as a subject.
  - Tier 1: 1–2 jobs at a time and $100/month; Tier 3 after $100 purchased.
- **Kling direct:**
  - Resource packs are sold internationally; the API runs from Singapore; there is a trial pack and an SLA document.
  - Minimum pack size and content policy: n/v.
- **Our own sound:** the episode gets its own sound design, so prices without audio are the relevant ones for most shots.

## Higgsfield (checked 2026-10-12)

- **What it is:** an aggregator, like fal.
  - It resells the same models (Kling, Veo, Sora, Seedance, Wan, MiniMax), so the quality is the same for the same model.
  - It adds its own tools on the website: DoP camera presets, Cinema Studio, Soul ID and lip-sync.
- **API** (`api.higgsfield.ai`, Python SDK since Nov 2025):
  - Has Kling 3.0/O3, Seedance, Wan and MiniMax, but **no Veo 3.1, Sora or DoP**.
  - 4 jobs at once by default; output files kept for 7 days.
  - Kling 3.0 Pro image-to-video costs $0.112–0.168/s at list price, $0.056–0.084/s under a temporary 50% promotion.
- **Website plans:** credits expire monthly. "Unlimited" covers only some models, runs in a slow queue and forbids automation.
- **Terms:**
  - Inputs and outputs may be used to train Higgsfield's models unless you have an Enterprise Agreement.
  - Commercial use is allowed.
  - Trustpilot rating: 4.0, with complaints about refunds, auto-renewal and "unlimited".
- **Verdict:** no quality gain over fal or Kling direct. The cost advantage depends on the promotion, and its terms allow training on our content.
- **Sources:**
  - https://higgsfield.ai/pricing
  - https://docs.higgsfield.ai/docs
  - https://open.higgsfield.ai/explore/video
  - https://higgsfield.ai/terms-of-use-agreement
  - https://www.trustpilot.com/review/higgsfield.ai

## Our own test (2026-10-12, Beat 2.5 bake-off on fal)

- **Kling v3 Pro** and **Kling O3 Pro** both animated 2.5-05, Mostafa's close-up (Karim, ACT-0003). Each clip is 8 s at 1920×1080, 24 fps, no audio, $1.12.
- **Veo 3.1 Fast refused that same keyframe three times** with `no_media_generated`. It still refused with no negative prompt, `safety_tolerance` 5 and a neutral prompt ("A soldier at night slowly blinks").
- On an adult keyframe (2.8-04, Hassan) Veo worked: $0.60 for 4 s.
- Most likely Google's filter reads Karim's boyish 19-year-old face as possibly under 18. Veo therefore can't carry Mostafa, our lead, or the children.
- **Decision: Kling is the studio's default video model.** Veo stays available for adult-only shots.
- The user watched both Kling takes and chose **Kling O3 Pro** (more alive) as `video_default`.

## Sources

- https://cloud.google.com/vertex-ai/generative-ai/pricing
- https://cloud.google.com/vertex-ai/generative-ai/docs/models/veo/3-1-generate
- https://cloud.google.com/vertex-ai/generative-ai/docs/video/responsible-ai-and-usage-guidelines
- https://ai.google.dev/gemini-api/docs/veo · https://ai.google.dev/gemini-api/docs/pricing
- https://docs.dev.runwayml.com/guides/pricing/ · https://docs.dev.runwayml.com/guides/models/
- https://kling.ai/document-api/pricing/base/video · https://kling.ai/document-api/api/video/3-0-omni/image-to-video
- https://docs.byteplus.com/en/docs/modelark/model-pricing
- https://platform.minimax.io/docs/guides/pricing-paygo.md
- https://developers.openai.com/api/docs/guides/video-generation
- https://learn.microsoft.com/en-us/azure/foundry/openai/concepts/video-generation
