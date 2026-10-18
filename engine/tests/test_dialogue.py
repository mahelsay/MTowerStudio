import unittest
from pathlib import Path

from mtower import dialogue
from mtower.production import Production, parse_screenplay

PROD = "thunderbolt/ep01_romani"


class PerformanceTests(unittest.TestCase):
    def test_every_line_has_a_valid_performance_and_a_cast_entry(self):
        prod = Production.load(PROD)
        self.assertEqual(dialogue.check_performance(prod), [])
        self.assertGreaterEqual(len(dialogue.lines(prod)), 49)

    def test_situation_is_the_action_before_the_line(self):
        prod = Production.load(PROD)
        t3 = {ln.n: ln for ln in dialogue.lines(prod, "T.3")}
        self.assertIn("Phantoms", t3[1].situation)
        self.assertNotIn("20 faces", t3[1].situation)
        self.assertIn("20 faces", t3[4].situation)

    def test_direction_carries_intensity_volume_and_language(self):
        entry = {"engine": "gpt-audio-1.5", "voice": "echo", "persona": "a commando captain"}
        perf = {"intensity": 9, "volume": "whisper", "pace": "quick", "emotion": "urgent restraint", "delivery": "into the handset"}
        text = dialogue.direction(entry, perf, "The battalion passes", "Tanks roll past.")
        for part in ("Egyptian Arabic", "Intensity 9/10", "whispered", "quick and clipped", "never relaxed", "Tanks roll past."):
            self.assertIn(part, text)
        calm = dialogue.direction(entry, {**perf, "intensity": 3}, "", "")
        self.assertNotIn("never relaxed", calm)
        self.assertIn("Hebrew", dialogue.direction({**entry, "language": "hebrew"}, perf))

    def test_speakable_keeps_shadda_and_drops_vowels_and_quotes(self):
        self.assertEqual(dialogue.speakable("«نَزِّلْنَا.»"), "نزّلنا.")
        self.assertEqual(dialogue.speakable("הַצִּיר נָקִי", "hebrew"), "הַצִּיר נָקִי")

    def test_audition_file_names_round_trip(self):
        entry = {"engine": "gpt-audio-1.5", "voice": "shimmer", "pitch": 1.2}
        self.assertEqual(dialogue.file_tag(entry), "gpt-audio-1.5__shimmer__p1.20")
        self.assertEqual(dialogue.parse_tag("gpt-audio-1.5__shimmer__p1.20"), entry)
        self.assertEqual(dialogue.parse_tag("azure-speech__he-IL-AvriNeural"), {"engine": "azure-speech", "voice": "he-IL-AvriNeural"})

    def test_louder_volume_is_louder(self):
        levels = [dialogue.VOLUMES[v][1] for v in ("whisper", "low", "normal", "raised", "shout")]
        self.assertEqual(levels, sorted(levels))

    def test_approved_cast_resolves_and_uncast_does_not(self):
        prod = Production.load(PROD)
        self.assertEqual(dialogue.resolve(prod, "C-01")["voice"], "echo")
        self.assertEqual(dialogue.resolve(prod, "COMMANDOS")["engine"], "group")
        self.assertIsNone(dialogue.resolve(prod, "NOBODY"))

    def test_subtitle_crop_refuses_to_cut_away_too_much(self):
        prod = Production.load(PROD)
        for keep in (0.5, 1.0):
            with self.assertRaises(ValueError):
                dialogue.crop_subtitles(prod, "2.4-02", keep)


class NarrationScriptTests(unittest.TestCase):
    def test_no_quran_anywhere_in_the_script(self):
        import re
        from mtower.__main__ import script_rule_problems
        prod = Production.load(PROD)
        self.assertEqual(script_rule_problems(prod), [])
        verse = "«كَمْ مِنْ فِئَةٍ قَلِيلَةٍ غَلَبَتْ فِئَةً كَثِيرَةً»"
        plain = re.sub(r"[\u064B-\u0652\u0670\u0640]", "", verse)
        self.assertTrue(any(re.search(r["pattern"], plain) for r in prod.config["script_rules"]["forbidden"]))

    def test_silent_beats_and_performance_comments(self):
        prod = Production.load(PROD)
        text, perf = dialogue.narration(prod, "2.5", "hamdi")
        self.assertTrue(text.startswith("عشرين"))
        self.assertNotIn("<!--", text)
        self.assertEqual(perf["intensity"], 6)
        self.assertEqual(dialogue.narration(prod, "2.4", "hamdi")[0], "")


class ParserTests(unittest.TestCase):
    def test_heading_environment_and_action_positions(self):
        import tempfile
        md = ("### Beat 9.1 — Test\n\n**INT. ROOM — NIGHT**\n\n**Environment:** Dark.\n\nHe enters.\n\n**ALI**\n> one\n\n"
              "She turns.\n\n**BOB**\n> two\n\n**SFX:** wind\n")
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "s.md"
            p.write_text(md, encoding="utf-8")
            beat = parse_screenplay(p)["9.1"]
        self.assertEqual(beat.title, "Test")
        self.assertEqual(beat.situation(1), "INT. ROOM — NIGHT Environment: Dark. He enters.")
        self.assertEqual(beat.situation(2), "INT. ROOM — NIGHT Environment: Dark. He enters. She turns.")


if __name__ == "__main__":
    unittest.main()
