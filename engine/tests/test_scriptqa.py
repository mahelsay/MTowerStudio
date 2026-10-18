import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mtower import scriptqa

SCRIPT = """# Title

## SEQUENCE A

### Beat 1.1 — One

**EXT. PLACE — DAY**

**SAYED** *(low)*
> خَايِفْ؟

**MOSTAFA**
> لَأْ.

### Beat 1.2 — Two

Nobody speaks.

## Beat Map

| a | b |
"""


class ScriptQaTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.path = root / "01_development" / "screenplay" / "01_act.md"
        self.path.parent.mkdir(parents=True)
        self.path.write_text(SCRIPT, encoding="utf-8")
        self.prod = SimpleNamespace(root=root, config={"speakers": {"SAYED": "C-02"}, "voice_cast": {}},
                                    casting={"cast": {"C-02": {"character": "Sergeant Sayed"}}})

    def tearDown(self):
        self.tmp.cleanup()

    def test_beat_sections_stop_at_the_next_section(self):
        sections = scriptqa.beat_sections(self.path)
        self.assertEqual(list(sections), ["1.1", "1.2"])
        self.assertIn("خَايِفْ؟", sections["1.1"])
        self.assertNotIn("Beat Map", sections["1.2"])

    def test_plan_skips_beats_without_dialogue_and_unchanged_beats(self):
        items = scriptqa.plan(self.prod, self.path)
        self.assertEqual([i["beat"] for i in items], ["1.1"])
        self.assertEqual(len(items[0]["lines"]), 2)
        out = items[0]["out"]
        out.parent.mkdir(parents=True)
        out.write_text(json.dumps({"beat": "1.1", "hash": items[0]["hash"]}), encoding="utf-8")
        self.assertEqual(scriptqa.plan(self.prod, self.path), [])
        self.assertEqual(len(scriptqa.plan(self.prod, self.path, force=True)), 1)

    def test_cast_brief_maps_speaker_names(self):
        brief = scriptqa.cast_brief(self.prod, {"SAYED", "MOSTAFA"})
        self.assertIn("SAYED (C-02, Sergeant Sayed)", brief)
        self.assertIn("MOSTAFA (MOSTAFA", brief)

    def test_summary_shows_failing_lines_with_rewrite(self):
        line = {"n": 1, "speaker": "SAYED", "text": "x", "score": 6, "issues": ["stiff"], "rewrite": "y",
                "scores": {a: (5 if a == "dialect" else 9) for a in scriptqa.AXES}}
        rows = scriptqa.summary_lines([{"beat": "1.1", "beat_score": 7, "verdict": "fail", "lines": [line],
                                        "scene_issues": [], "history_issues": [], "rule_issues": []}])
        self.assertTrue(rows[0].startswith("✗ Beat 1.1"))
        self.assertIn("dialect 5", rows[1])
        self.assertIn("→ y", rows[-1])


if __name__ == "__main__":
    unittest.main()
