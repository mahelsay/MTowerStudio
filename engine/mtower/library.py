"""Studio library catalogs: actors, wardrobe, locations, vehicles, props, looks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .settings import LIBRARY_DIR, load_json, write_json

ID_PATTERN = re.compile(r"\b(ACT|WRD|LOC|VEH|PRP)-\d{4}\b")
TOKEN_PATTERN = re.compile(r"\{([A-Z0-9_]+)\}")
ACTORS_PATH = LIBRARY_DIR / "actors" / "actors.json"
PROPS_PATH = LIBRARY_DIR / "props" / "props.json"


def _update_card(path, list_key: str, item_id: str, changes: dict) -> dict:
    """Merge changes into one catalog card (nested dicts are merged one level deep)."""
    data = load_json(path)
    for item in data[list_key]:
        if item["id"] == item_id:
            for key, value in changes.items():
                if isinstance(value, dict) and isinstance(item.get(key), dict):
                    item[key].update(value)
                else:
                    item[key] = value
            write_json(path, data)
            return item
    raise KeyError(item_id)


def update_actor(actor_id: str, changes: dict) -> dict:
    """Merge changes into one actor card in actors.json."""
    return _update_card(ACTORS_PATH, "actors", actor_id, changes)


def update_prop(prop_id: str, changes: dict) -> dict:
    """Merge changes into one prop card in props.json."""
    return _update_card(PROPS_PATH, "props", prop_id, changes)


@dataclass
class Library:
    actors: dict = field(default_factory=dict)
    wardrobe: dict = field(default_factory=dict)
    wear_states: dict = field(default_factory=dict)
    off_duty_wear: list = field(default_factory=list)
    locations: dict = field(default_factory=dict)
    vehicles: dict = field(default_factory=dict)
    props: dict = field(default_factory=dict)
    looks: dict = field(default_factory=dict)

    @classmethod
    def load(cls) -> "Library":
        lib = cls()
        lib.actors = {a["id"]: a for a in load_json(LIBRARY_DIR / "actors" / "actors.json")["actors"]}
        wardrobe = load_json(LIBRARY_DIR / "wardrobe" / "wardrobe.json")
        lib.wardrobe = {w["id"]: w for w in wardrobe["wardrobe"]}
        lib.wear_states = wardrobe["wear_states"]
        lib.off_duty_wear = wardrobe.get("off_duty_wear_states", [])
        lib.locations = {x["id"]: x for x in load_json(LIBRARY_DIR / "locations" / "locations.json")["locations"]}
        lib.vehicles = {x["id"]: x for x in load_json(LIBRARY_DIR / "vehicles" / "vehicles.json")["vehicles"]}
        lib.props = {x["id"]: x for x in load_json(LIBRARY_DIR / "props" / "props.json")["props"]}
        lib.looks = load_json(LIBRARY_DIR / "looks" / "looks.json")
        return lib

    def asset(self, asset_id: str) -> dict | None:
        for catalog in (self.locations, self.vehicles, self.props, self.wardrobe, self.actors):
            if asset_id in catalog:
                return catalog[asset_id]
        return None

    def block(self, key: str) -> str | None:
        """Return a look/camera/reference block by key, or None."""
        for section in ("look", "camera", "reference_variations", "realism"):
            value = self.looks.get(section, {}).get(key)
            if value:
                return value
        return None

    def expand(self, text: str, extra: dict | None = None, depth: int = 0) -> str:
        """Replace {TOKEN} placeholders with look/camera blocks or extra values."""
        extra = extra or {}

        def repl(match: re.Match) -> str:
            key = match.group(1)
            if key in extra:
                return str(extra[key])
            value = self.block(key)
            return value if value is not None else match.group(0)

        result = TOKEN_PATTERN.sub(repl, text)
        if depth < 3 and TOKEN_PATTERN.search(result) and result != text:
            return self.expand(result, extra, depth + 1)
        return result
