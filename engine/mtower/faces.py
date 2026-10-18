"""Face pass helpers: choose the lead's face among detected faces and build an inpainting mask (stdlib only).

Why: an actor's face model (LoRA) paints its face on every person in the frame. Group shots are therefore
rendered without face models first, then only the lead's face is repainted with the actor's face model.
"""

from __future__ import annotations

import struct
import zlib
from pathlib import Path

STRATEGIES = ("largest", "center", "smallest", "left", "right")


def image_size(path: Path) -> tuple[int, int]:
    """(width, height) of a PNG or JPEG file."""
    data = Path(path).read_bytes()
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return struct.unpack(">II", data[16:24])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i < len(data):
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                h, w = struct.unpack(">HH", data[i + 5:i + 9])
                return w, h
            i += 2 + struct.unpack(">H", data[i + 2:i + 4])[0]
    raise ValueError(f"Unsupported image format: {path}")


def faces_from_detection(result: dict, width: int | None = None, height: int | None = None) -> list[dict]:
    """Face boxes {x, y, w, h} in pixels from a detector result: Florence-2 ('results.bboxes' labelled '... face', pixels)
    or Moondream ('objects' with normalised x_min/y_min/x_max/y_max; needs the image width and height)."""
    if "objects" in result:
        if not width or not height:
            raise ValueError("Moondream boxes are normalised: pass the image width and height")
        return [{"x": o["x_min"] * width, "y": o["y_min"] * height, "w": (o["x_max"] - o["x_min"]) * width,
                 "h": (o["y_max"] - o["y_min"]) * height, "label": "face"} for o in result.get("objects") or []]
    boxes = (result.get("results") or {}).get("bboxes") or []
    return [b for b in boxes if "face" in str(b.get("label", "")).lower()]


def merge_boxes(boxes: list[dict], extra: list[dict]) -> list[dict]:
    """boxes plus the extra boxes whose centre is not already inside one of them."""
    def inside(b: dict, o: dict) -> bool:
        cx, cy = b["x"] + b["w"] / 2, b["y"] + b["h"] / 2
        return o["x"] <= cx <= o["x"] + o["w"] and o["y"] <= cy <= o["y"] + o["h"]
    return boxes + [b for b in extra if not any(inside(b, o) for o in boxes)]


def pick_faces(boxes: list[dict], width: int, count: int, strategy: str = "largest") -> list[dict]:
    """The `count` faces to repaint, ordered left to right (characters are matched in the shot's listed order).

    largest: the biggest faces (foreground leads) · center: nearest the frame's vertical centre line ·
    smallest: the most distant faces · left / right: from that side of the frame.
    """
    if strategy not in STRATEGIES:
        raise ValueError(f"Unknown face strategy '{strategy}'. Use one of: {', '.join(STRATEGIES)}")
    area = lambda b: b["w"] * b["h"]  # noqa: E731
    keys = {
        "largest": lambda b: -area(b),
        "smallest": area,
        "center": lambda b: abs(b["x"] + b["w"] / 2 - width / 2),
        "left": lambda b: b["x"],
        "right": lambda b: -(b["x"] + b["w"]),
    }
    chosen = sorted(boxes, key=keys[strategy])[:count]
    return sorted(chosen, key=lambda b: b["x"])


def ellipse(box: dict, pad_w: float = 1.5, pad_h: float = 1.7) -> tuple[float, float, float, float]:
    """(cx, cy, rx, ry) of the repaint ellipse around a face box: enlarged and nudged up so it covers the hairline
    and ears; the face model then repaints the whole head shape, not just the features, which blends better."""
    return (box["x"] + box["w"] / 2, box["y"] + box["h"] / 2 - 0.08 * box["h"],
            max(4.0, box["w"] * pad_w / 2), max(4.0, box["h"] * pad_h / 2))


def patch_rect(box: dict, width: int, height: int, factor: float = 2.6, minimum: int = 96) -> tuple[int, int, int]:
    """(x, y, side) of the square around a face that the face pass enlarges, repaints and blends back.

    Repainting a 40-100 px face inside the full frame gives the model too few pixels (it invents blobs or
    re-poses the head); a close-up crop gives it a portrait to work on. The square keeps some context
    (hair, collar, light) and is shifted to stay inside the picture."""
    side = int(min(width, height, max(minimum, round(max(box["w"], box["h"]) * factor))))
    cx, cy = box["x"] + box["w"] / 2, box["y"] + box["h"] / 2
    x = int(min(max(0, round(cx - side / 2)), width - side))
    y = int(min(max(0, round(cy - side / 2)), height - side))
    return x, y, side


def scale_box(box: dict, x: int, y: int, k: float) -> dict:
    """The face box in the coordinates of a crop at (x, y) enlarged k times."""
    return {"x": (box["x"] - x) * k, "y": (box["y"] - y) * k, "w": box["w"] * k, "h": box["h"] * k}


def ellipse_mask_png(width: int, height: int, box: dict, pad_w: float = 1.5, pad_h: float = 1.7) -> bytes:
    """Grayscale PNG, white ellipse (area to repaint, see ellipse()) around a face box, black elsewhere."""
    return _ellipse_png(width, height, box, pad_w, pad_h, alpha=False)


def alpha_mask_png(width: int, height: int, box: dict, pad_w: float = 1.25, pad_h: float = 1.35) -> bytes:
    """OpenAI-style edit mask: RGBA PNG, transparent ellipse (area to repaint) around a face box, opaque black elsewhere.
    Tighter than the fal mask: the head can't grow beyond the face's own outline."""
    return _ellipse_png(width, height, box, pad_w, pad_h, alpha=True)


def check_face(before: dict, after: list[dict], min_area: float = 0.65, max_area: float = 1.45,
               max_shift: float = 0.5) -> dict:
    """Did the face pass keep the face's size and place? Compares the face box before the pass with the nearest box
    detected after it. area = after/before area; shift = centre distance in face widths. ok is False when it grew,
    shrank or moved too much, or when no face is found."""
    cx, cy = before["x"] + before["w"] / 2, before["y"] + before["h"] / 2
    if not after:
        return {"ok": False, "reason": "no face found after the face pass"}
    dist = lambda b: ((b["x"] + b["w"] / 2 - cx) ** 2 + (b["y"] + b["h"] / 2 - cy) ** 2) ** 0.5  # noqa: E731
    near = min(after, key=dist)
    area = (near["w"] * near["h"]) / max(1.0, before["w"] * before["h"])
    shift = dist(near) / max(1.0, before["w"])
    reasons = []
    if area > max_area:
        reasons.append(f"face grew {area:.2f}x")
    if area < min_area:
        reasons.append(f"face shrank to {area:.2f}x")
    if shift > max_shift:
        reasons.append(f"face moved {shift:.2f} face-widths")
    return {"ok": not reasons, "area_ratio": round(area, 3), "shift": round(shift, 3), "reason": "; ".join(reasons)}


def _ellipse_png(width: int, height: int, box: dict, pad_w: float, pad_h: float, alpha: bool) -> bytes:
    cx, cy, rx, ry = ellipse(box, pad_w, pad_h)
    rows = []
    for y in range(height):
        dy = (y + 0.5 - cy) / ry
        row = bytearray(b"\x00\x00\x00\xff" * width) if alpha else bytearray(width)
        if abs(dy) < 1:
            half = rx * (1 - dy * dy) ** 0.5
            x0, x1 = max(0, int(cx - half)), min(width, int(cx + half) + 1)
            if alpha:
                for x in range(x0, x1):
                    row[4 * x + 3] = 0
            else:
                row[x0:x1] = b"\xff" * (x1 - x0)
        rows.append(b"\x00" + bytes(row))

    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    header = struct.pack(">IIBBBBB", width, height, 8, 6 if alpha else 0, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(b"".join(rows), 9)) + chunk(b"IEND", b"")
