# Studio Library

The reusable "virtual world" of MTower Studio: actors, wardrobe, locations, vehicles, props, and looks. **Every production draws from this library, and every production adds to it.**

## Catalogs

| Catalog | File | ID format | What's in it |
|---|---|---|---|
| Actors | [`actors/actors.json`](actors/actors.json) | `ACT-0000` | Virtual actors — face and body only, plus their face model (LoRA) and the roles they've played. Training-set recipe: [`actors/training_set.json`](actors/training_set.json) |
| Wardrobe | [`wardrobe/wardrobe.json`](wardrobe/wardrobe.json) | `WRD-0000` | Uniforms and costumes by period, plus shared **wear states** (clean, mud, salt, sand, battle, gaunt…) |
| Locations | [`locations/locations.json`](locations/locations.json) | `LOC-0000` | Places, with the light variants each needs |
| Vehicles | [`vehicles/vehicles.json`](vehicles/vehicles.json) | `VEH-0000` | Vehicles and aircraft, with interiors and damage states |
| Props | [`props/props.json`](props/props.json) | `PRP-0000` | Weapons, equipment, everyday objects, with states; key weapons get a prop model (LoRA) trained from real reference photos. Recipe: [`props/training_set.json`](props/training_set.json) |
| Looks | [`looks/looks.json`](looks/looks.json) | named keys | Film looks, lighting, lenses, format defaults, review checklists, reference-sheet variations |

## Current roster (seeded by *Thunderbolt* Episode 1)

| ID | Actor | Age | Look (signature) | Range | Reuse | Status |
|---|---|---|---|---|---|---|
| ACT-0001 | Tarek Selim | 30 | Cairo · long narrow face, side-parted hair, thin handlebar mustache | Officers, leaders | 🔒 locked to role (real person) | ✅ locked 2026-10-12 |
| ACT-0002 | Hazem Abdallah | 35 | Suez coast · broad weathered face, receding greying hair, bushy mustache | Veterans, sergeants, fathers | open | ✅ locked 2026-10-12 |
| ACT-0003 | Karim Nour | 19 | Delta · boyish oval face, large almond eyes, tousled hair | Young soldiers, students, sons | open | ✅ locked 2026-10-12 |
| ACT-0004 | Sherif Mansour | 25 | Alexandria · wavy light-brown hair, freckles, green-grey eyes | Technicians, clerks, radio operators | open | ✅ locked 2026-10-12 |
| ACT-0005 | Yasser Hamdan | 32 | Upper Egypt · shaved head, full beard, square jaw | Specialists, engineers, craftsmen | open | 🧪 face model trained — free (recast out of C-05 Hassan) |
| ACT-0006 | Amr Fahmy | 22 | Aswan (Nubian) · tall and very thin, high sharp cheekbones | Marksmen, athletes, young professionals | open | ✅ locked 2026-10-12 |
| ACT-0007 | Souad Roshdy | 45 | Delta · deeply lined face, hazel eyes, blue dot tattoos | Mothers, village women | open | ✅ locked 2026-10-12 |
| ACT-0008 | Malak Samy | 12 | Delta · round face, large dark eyes, long black hair | Daughters, schoolgirls | open | ✅ locked 2026-10-12 |
| ACT-0009 | Nadia Fouad | 30 | Suez · hazel almond eyes, thick straight brows | Wives, working women | open | ✅ locked 2026-10-12 |
| ACT-0010 | Youssef Mamdouh | 8 | Suez · small round face, large dark eyes | Sons, schoolboys | open | ✅ locked 2026-10-12 |
| ACT-0011 | Farouk El-Desouky | 50 | Cairo · wide jowly face, grey hair combed back, grey mustache | Senior officers | 🔒 locked to role (real role) | ✅ anchor approved |
| ACT-0012 | Magdy Riad | 38 | Tanta · angular face, messy hair, squinting hazel eyes | Pilots, officers | 🔒 locked to role (real role) | ✅ anchor approved |
| ACT-0013 | Mahmoud Abdel-Rahim | 32 | Sohag (Sa'idi) · aquiline nose, high cheekbones, shaved head, short trimmed beard | Engineers, craftsmen, farmers, sergeants | open | ✅ locked 2026-10-12 |

All actors are fictional. Their names were chosen as common Egyptian names and do not refer to real people.

## Rules

1. **Actors are not characters.** An actor is a reusable face; a character is a role in one story. Productions cast characters from actors in their own `casting.json`.
2. **One role per actor per series.** Viewers would notice the same face as two people. Across different series, recasting is fine.
3. **Real people are never open library actors.** A stand-in for a real person (or a real unnamed role) is marked `locked_to_role` and never recast.
4. **Grow on demand.** Add an asset when a production needs it, built to library standard, then reuse it. Don't build assets nobody needs yet.
5. **Descriptions stay clean.** Actor cards describe face and body only; costume goes in wardrobe; story details go in the production's casting.
6. **Record usage.** When a production uses an asset, add it to the asset's `used_in` (or `roles` for actors).
7. **Every actor is a different person.** Each actor card has structured `traits`; `mtower cast-check` must pass before new anchors are generated (see the engine README, "Keeping virtual actors distinct"). Only family members may resemble each other.

## Card status

`concept` (description only) → `anchor_approved` (one approved image defines it) → `lora_trained` (actors and key props) → `locked` (approved for production). The engine refuses new anchors, training images or face-model training for a `locked` actor; to change one, set the status back to `lora_trained` and note why.

## Where media live

Git holds only the cards (text). Images, training sets, face models, and test renders live in cloud storage, mirroring the library structure:

```
MTower-Studio/                        ← cloud storage root (Google Drive to start)
└── library/
    ├── actors/ACT-0003_karim-nour/
    │   ├── anchor/                   ← the approved anchor portrait + rejected candidates
    │   ├── training_set/             ← the curated 15–20 images (KEEP FOREVER — used to retrain)
    │   ├── lora/                     ← trained face model files, by base-model version
    │   └── tests/                    ← approval test renders
    ├── props/PRP-0003_malyutka-at3-sagger/
    │   ├── references/               ← real photos: ground truth for shape, size, colour (KEEP FOREVER)
    │   ├── training_set/  lora/
    ├── locations/LOC-0003_tina-plain-salt-marsh/
    ├── vehicles/…  wardrobe/…
```

**Keep the training sets forever.** A face model only works with the image model it was trained on. When a better image model arrives, the actor is retrained from the same training set and keeps the same face.

## Adding a new asset

1. Pick the next free ID in the catalog.
2. Write the card: name, description prompt (clean, reusable wording), period, states/variants, `status: concept`. For actors, run `mtower cast-check --coverage` first and pick traits nobody else uses yet.
3. Generate references through the engine; approve the anchor; update `status`.
4. Record the production in `used_in`.
