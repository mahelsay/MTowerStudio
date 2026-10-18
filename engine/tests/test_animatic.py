import unittest

from mtower.animatic import fit_filter


class FitFilterTests(unittest.TestCase):
    def test_short_clip_is_slowed_then_held(self):
        vf = fit_filter(8.0, 10.0)
        self.assertTrue(vf.startswith("setpts=1.2500*PTS"))
        self.assertIn("tpad=stop_mode=clone:stop_duration=10.000", vf)
        self.assertIn("trim=duration=10.000", vf)

    def test_stretch_is_capped(self):
        self.assertTrue(fit_filter(5.0, 10.0).startswith("setpts=1.3000*PTS"))

    def test_long_clip_is_only_trimmed(self):
        vf = fit_filter(13.04, 13.0)
        self.assertFalse(vf.startswith("setpts=1"))
        self.assertIn("trim=duration=13.000", vf)
        self.assertIn("scale=1920:1080", vf)


if __name__ == "__main__":
    unittest.main()


class CardTextTests(unittest.TestCase):
    def test_text_is_kept_in_reading_order_inside_a_right_to_left_isolate(self):
        from mtower.cards import PDI, RLI, visual
        self.assertEqual(visual(" أمرُ المهمّة: "), RLI + "أمرُ المهمّة:" + PDI)
        self.assertEqual(visual("سيناء — ٦ أكتوبر ١٩٧٣"), RLI + "سيناء — ٦ أكتوبر ١٩٧٣" + PDI)
        self.assertEqual(visual(" Mission order: "), "Mission order:")

    def _ink_runs(self, text: str, font: str = "Amiri-Regular.ttf") -> list[tuple[int, int]]:
        """Horizontal runs of ink (x from, x to) of the text drawn by drawtext as the cards draw it."""
        import shutil
        import subprocess
        from mtower.animatic import ffmpeg
        from mtower.cards import _workdir
        try:
            exe = ffmpeg()
        except Exception:  # noqa: BLE001
            self.skipTest("ffmpeg not available")
        work = _workdir(font, [text])
        try:
            w, h = 800, 200
            raw = subprocess.run([exe, "-v", "error", "-f", "lavfi", "-i", f"color=black:s={w}x{h}", "-frames:v", "1",
                                  "-vf", "drawtext=fontfile=font.ttf:textfile=t0.txt:fontsize=80:fontcolor=white:"
                                         "x=(w-tw)/2:y=50", "-f", "rawvideo", "-pix_fmt", "gray", "-"],
                                 cwd=work, capture_output=True, check=True).stdout
        finally:
            shutil.rmtree(work, ignore_errors=True)
        ink = [any(raw[y * w + x] > 128 for y in range(h)) for x in range(w)]
        runs, start = [], None
        for x, on in enumerate(ink + [False]):
            if on and start is None:
                start = x
            elif not on and start is not None:
                if runs and start - runs[-1][1] < 6:
                    runs[-1] = (runs[-1][0], x - 1)
                else:
                    runs.append((start, x - 1))
                start = None
        return runs

    def test_drawtext_puts_the_first_arabic_word_on_the_right(self):
        runs = self._ink_runs("ا ممممممم")
        self.assertEqual(len(runs), 2, runs)
        (l0, l1), (r0, r1) = runs
        self.assertGreater(l1 - l0, r1 - r0, "the long word must be on the left, the alif (first word) on the right")

    def test_trailing_punctuation_lands_on_the_left_of_an_arabic_line(self):
        for mark in (":", "."):
            runs = self._ink_runs("ممممممم" + mark)
            self.assertEqual(len(runs), 2, (mark, runs))
            (l0, l1), (r0, r1) = runs
            self.assertLess(l1 - l0, r1 - r0, f"'{mark}' ends the line, so it must be at the left end")


class PlaybackCheckTests(unittest.TestCase):
    def test_graded_shots_encode_as_playable_420(self):
        import subprocess
        import tempfile
        from pathlib import Path
        from mtower.animatic import ffmpeg, playback_problems
        from mtower.cards import X264
        try:
            exe = ffmpeg()
        except Exception:  # noqa: BLE001
            self.skipTest("ffmpeg not available")
        rgb_grade = "colorchannelmixer=rr=1.1,eq=gamma=1.3"
        with tempfile.TemporaryDirectory() as tmp:
            bad, good = Path(tmp) / "bad.mp4", Path(tmp) / "good.mp4"
            src = ["-f", "lavfi", "-i", "testsrc=s=320x180:d=0.5", "-vf", rgb_grade]
            subprocess.run([exe, "-v", "error", *src, "-c:v", "libx264", "-pix_fmt", "yuv444p", str(bad)], check=True)
            subprocess.run([exe, "-v", "error", *src, *X264, str(good)], check=True)
            self.assertIn("chroma_format_idc=3", playback_problems(exe, bad))
            self.assertEqual(playback_problems(exe, good), [])


class SoundPlanTests(unittest.TestCase):
    def test_teaser_rotor_bed_spans_from_the_first_card_to_the_smash_cut(self):
        from mtower.production import Production
        from mtower import sound
        prod = Production.load("thunderbolt/ep01_romani")
        start, end = sound.span(prod, "00_teaser", "T.1-01", "T.3-10")
        montage_start, montage_end = sound.span(prod, "00_teaser", "T.4-01", "T.4-08")
        title_start, title_end = sound.span(prod, "00_teaser", "T.5-01")
        self.assertEqual(start, 0.0)
        self.assertEqual(end, montage_start)  # the rotor bed stops exactly at the landing, where the montage starts
        self.assertEqual(montage_end, title_start)
        self.assertEqual(title_end - title_start, 22.0)
        beds = sound.plan(prod, "00_teaser", {"bed"})
        self.assertEqual([c.id for c in beds], ["rotor", "wind"])
        self.assertLessEqual(max(c.seconds for c in beds), 22)
        music = sound.plan(prod, "00_teaser", {"music"}, variants=2, cues_only=["main_title"])
        self.assertEqual(len(music), 2)
        self.assertAlmostEqual(sum(e.total for e in sound.estimates(music)), 2 * 27 / 60 * 0.6, places=3)
        score = sound.plan(prod, "00_teaser", {"music"}, variants=1, cues_only=["teaser_score"])
        self.assertEqual([c.id for c in score], ["teaser_score"])


class ByteRangeTests(unittest.TestCase):
    def test_ranges(self):
        from mtower.gallery import byte_range
        self.assertEqual(byte_range(None, 1000), (0, 999))
        self.assertEqual(byte_range("bytes=0-", 1000), (0, 999))
        self.assertEqual(byte_range("bytes=100-199", 1000), (100, 199))
        self.assertEqual(byte_range("bytes=900-5000", 1000), (900, 999))
        self.assertEqual(byte_range("bytes=-100", 1000), (900, 999))
        self.assertEqual(byte_range("bytes=1000-", 1000), (None, 0))
