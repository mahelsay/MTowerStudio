"""Engine tests (standard library unittest). Run:  ./mtower.ps1 is not needed —
    python -m unittest discover -s engine/tests   (with PYTHONPATH=engine)
"""

import os
import tempfile
import unittest
from pathlib import Path

from mtower import casting, costs, faces, jobs
from mtower.library import Library
from mtower.production import Production
from mtower.prompts import PromptComposer

PROD = "thunderbolt/ep01_romani"


class ScreenplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prod = Production.load(PROD)

    def beat(self, part, beat):
        return self.prod.screenplay(self.prod.shot_list(part))[beat]

    def test_dialogue_lines_split_on_stage_directions(self):
        b = self.beat("01_act_one", "1.4")
        self.assertEqual(len(b.dialogue), 9)
        self.assertEqual([d.speaker for d in b.dialogue], ["COMMANDER", "SHALABI", "COMMANDER", "COMMANDER", "SHALABI",
                                                           "SAYED", "SHALABI", "SAYED", "SHALABI"])
        self.assertTrue(b.vo)

    def test_hebrew_lines_carry_arabic_subtitles(self):
        b = self.beat("03_act_three", "3.12")
        self.assertEqual(len(b.dialogue), 2)
        self.assertTrue(all(d.subtitle for d in b.dialogue))

    def test_letters_and_final_dedication(self):
        self.assertEqual(len(self.beat("05_act_five", "5.6").dialogue), 5)
        self.assertTrue(self.beat("05_act_five", "5.8").vo)


class PromptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = Library.load()
        cls.prod = Production.load(PROD)
        cls.composer = PromptComposer(cls.lib, cls.prod)

    def test_every_shot_composes_without_leftover_tokens(self):
        count = 0
        for _, beat, shot in self.prod.all_shots():
            c = self.composer.shot(beat, shot)
            self.assertNotIn("{", c.image_prompt, shot["shot_id"])
            count += 1
        self.assertEqual(count, 472)

    def test_shared_wardrobe_described_once(self):
        _, beat, shot = self.prod.find_shot("1.2-06")
        prompt = self.composer.shot(beat, shot).image_prompt
        self.assertEqual(prompt.count("sand-khaki cotton field uniform"), 1)
        self.assertIn("greying at the temples", prompt)
        self.assertIn("boyish clean-shaven face", prompt)

    def test_wear_state_and_location_included(self):
        _, beat, shot = self.prod.find_shot("2.5-05")
        prompt = self.composer.shot(beat, shot).image_prompt
        self.assertIn("dried white salt crust", prompt)
        self.assertIn("vast flat salt marsh", prompt)
        self.assertIn("1973", prompt)

    def test_one_hair_description_per_character(self):
        _, beat, shot = self.prod.find_shot("2.6-02")
        prompt = self.composer.shot(beat, shot).image_prompt
        self.assertIn("short military haircut", prompt)
        self.assertNotIn("tousled", prompt)
        self.assertNotIn("with short black hair", prompt)
        _, beat, shot = self.prod.find_shot("1.2-04")
        prompt = self.composer.shot(beat, shot).image_prompt
        self.assertIn("greying at the temples", prompt)
        self.assertNotIn("with short black hair", prompt)

    def test_role_hair_overrides_actor_hair(self):
        from mtower.prompts import resolve_hair
        face, wardrobe = resolve_hair("Egyptian village girl, 12, round face, long straight loose black hair",
                                      "faded blue cotton dress", "hair in two long black braids")
        self.assertNotIn("loose", face)
        face, _ = resolve_hair("village woman, wrinkles, hair always covered by a headscarf", "", "two long braids")
        self.assertIn("covered", face)

    def test_shot_kit_and_off_duty_wear(self):
        _, beat, shot = self.prod.find_shot("4.5-03")
        prompt = self.composer.chatgpt_prompt(beat, shot)
        self.assertIn("RKG-3 anti-tank grenade raised in his right hand", prompt)
        self.assertNotIn("periscope sight", prompt)
        _, beat, shot = self.prod.find_shot("5.5-01")
        prompt = self.composer.chatgpt_prompt(beat, shot)
        self.assertNotIn("chest rig", prompt)
        self.assertNotIn("RPG-7 rocket carrier", prompt)
        self.assertIn("kit bag", prompt)
        _, beat, shot = self.prod.find_shot("2.6-02")
        self.assertIn("chest rig", self.composer.chatgpt_prompt(beat, shot))

    def test_insert_shots_ask_for_no_faces(self):
        _, beat, shot = self.prod.find_shot("2.5-06")
        prompt = self.composer.chatgpt_prompt(beat, shot)
        self.assertIn("no faces", prompt)
        self.assertNotIn("Every person", prompt)
        self.assertNotIn("central band", prompt)
        _, beat, shot = self.prod.find_shot("2.5-07")
        self.assertIn("Every person", self.composer.chatgpt_prompt(beat, shot))

    def test_realism_blocks_follow_the_shot(self):
        _, beat, shot = self.prod.find_shot("2.5-07")  # the captain and the file of men behind him
        prompt = self.composer.chatgpt_prompt(beat, shot)
        self.assertIn("seven and a half heads tall", prompt)
        self.assertIn("no merged, floating or duplicated bodies", prompt)
        self.assertIn("true real-world scale", prompt)
        self.assertIn("no morphing", self.composer.shot(beat, shot).motion_prompt)
        _, beat, shot = self.prod.find_shot("2.5-06")  # an insert: no people blocks
        prompt = self.composer.chatgpt_prompt(beat, shot)
        self.assertNotIn("heads tall", prompt)
        self.assertNotIn("real-world scale", prompt)
        self.assertTrue(self.composer.triggered("NATURAL_ANIMAL", "two camels at the well"))
        self.assertTrue(self.composer.triggered("NATURAL_BIRD", "a hawk circling"))
        self.assertFalse(self.composer.triggered("NATURAL_BIRD", "a boy flying a kite"))

    def test_qa_brief_carries_the_design_and_location_rules(self):
        from mtower import qa
        _, beat, shot = self.prod.find_shot("2.5-07")
        brief, _ = qa.shot_brief(self.lib, self.prod, self.composer, beat, shot)
        self.assertIn("Shot 2.5-07", brief)
        self.assertIn("Character C-01", brief)
        self.assertIn("Location rule: The marsh is shallow", brief)
        self.assertIn("moonlight", brief)
        self.assertNotIn("act0001tarek", brief)  # the reviewer gets plain words, not trigger tokens
        self.assertEqual(qa.SCHEMA["properties"]["checks"]["required"], qa.CATEGORIES)
        self.assertIn("rules", self.prod.config["qa"])

    def test_rank_insignia_drawings_go_to_compositions_but_not_inserts(self):
        from mtower import jobs
        plan = jobs.plan_compositions(self.lib, self.prod, ["1.4-01"])
        refs = [p.rsplit("\\", 1)[-1].rsplit("/", 1)[-1] for p in plan[0].payload["_references"]]
        self.assertEqual(refs[-2:], ["eg-army-captain-OF02.png", "eg-army-major-general-OF07.png"])
        self.assertIn("Commander of Sa'iqa Forces wears the insignia in the", plan[0].prompt)
        self.assertNotIn("(unnamed", plan[0].prompt)
        insert = jobs.plan_compositions(self.lib, self.prod, ["1.4-04"])[0]
        self.assertFalse(any("insignia" in p for p in insert.payload["_references"]))

    def test_child_shots_compose_on_flux_without_references(self):
        from unittest import mock
        from mtower import jobs
        with mock.patch.object(jobs, "anchor_path", side_effect=FileNotFoundError("no anchor")):
            plan = jobs.plan_compositions(self.lib, self.prod, ["5.5-02"])
        self.assertEqual(plan[0].model_key, "image_compose_flux")
        self.assertEqual(plan[0].payload["_references"], [])
        self.assertNotIn("_input_image", plan[0].payload)
        self.assertAlmostEqual(jobs.estimates(plan[:1])[0].total, 0.04)
        self.assertEqual(plan[1].kind, "face_pass")
        self.assertEqual(jobs.plan_compositions(self.lib, self.prod, ["2.4-02"])[0].model_key, "image_compose")
        # FLUX gets the short prompt: no ChatGPT boilerplate, no location setting, no face-model trigger
        self.assertNotIn("Create one photorealistic", plan[0].prompt)
        self.assertNotIn("setting:", plan[0].prompt)
        self.assertNotIn("act0008malak", plan[0].prompt)
        self.assertIn("terracotta water jar", plan[0].prompt)

    def test_child_shot_uses_the_casting_photo_when_approved(self):
        from unittest import mock
        from mtower import jobs
        with tempfile.TemporaryDirectory() as tmp:
            anchor = Path(tmp) / "anchor.png"
            anchor.write_bytes(b"x")
            with mock.patch.object(jobs, "anchor_path", return_value=anchor):
                plan = jobs.plan_compositions(self.lib, self.prod, ["5.5-02"])
        self.assertEqual(len(plan), 1)  # Kontext keeps the face: no face pass
        self.assertEqual(plan[0].payload["_input_image"], str(anchor))
        self.assertTrue(plan[0].prompt.startswith(jobs.FLUX_ACTOR_NOTE))
        self.assertNotIn("_edit", plan[0].payload)  # keeps the 16:9 aspect ratio, not the portrait's

    def test_clip_bake_off_plans_one_take_per_model_with_each_models_duration(self):
        from unittest import mock
        with mock.patch.object(jobs, "approved_keyframe", return_value=Path("k.png")):
            plan = jobs.plan_clips(self.lib, self.prod, None, ["2.5-05"],
                                   ["video_kling_v3", "video_default", "video_premium"])
            long_shot = jobs.plan_clips(self.lib, self.prod, None, ["2.5-07"], ["video_premium"])
        self.assertEqual([j.model_key for j in plan], ["video_kling_v3", "video_default", "video_premium"])
        self.assertEqual(len({j.out_dir for j in plan}), 3)  # side by side, not one folder
        self.assertEqual([j.payload["duration"] for j in plan], ["5", "5", "6s"])  # 5 s shot; Veo rounds up to 6s
        self.assertEqual(plan[1].negative, "")  # Kling O3 (the default) has no negative prompt
        self.assertIn("salt crystals", plan[0].prompt)  # the scene, not just the motion
        self.assertEqual(long_shot[0].payload["duration"], "8s")  # 13 s shot: Veo's longest
        self.assertAlmostEqual(jobs.estimates(plan[:1])[0].total, 5 * 0.14)

    def test_edit_plans_one_flux_job_on_the_source_image(self):
        from mtower import jobs
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "k.png"
            src.write_bytes(b"x")
            plan = jobs.plan_edit(self.prod, "4.8-03", "Remove the cross. Keep everything else the same.", src)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0].model_key, "image_compose_flux")
        self.assertEqual(plan[0].payload["_input_image"], str(src))
        self.assertTrue(plan[0].payload["_edit"])
        self.assertEqual(plan[0].prompt, "Remove the cross. Keep everything else the same.")
        with self.assertRaisesRegex(ValueError, "instruction"):
            jobs.plan_edit(self.prod, "4.8-03", "  ", src)

    def test_no_lora_trigger_before_training(self):
        lib = Library.load()
        lib.actors["ACT-0003"]["status"] = "anchor_approved"
        composer = PromptComposer(lib, self.prod)
        _, beat, shot = self.prod.find_shot("2.5-05")
        self.assertNotIn("act0003karim", composer.shot(beat, shot).image_prompt)


class CastingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = Library.load()

    def _fake(self, **actors):
        lib = Library()
        lib.actors = {aid: {"id": aid, **card} for aid, card in actors.items()}
        return lib

    def _card(self, age, gender="male", **overrides):
        traits = dict(self.lib.actors["ACT-0001"]["traits"])
        traits.update(overrides)
        text = " ".join(v.replace("-", " ") for v in traits.values())
        return {"gender": gender, "apparent_age": age, "traits": traits, "face_and_body": text}

    def test_real_roster_is_distinct(self):
        report = casting.check(self.lib)
        self.assertEqual(report.card_problems, [])
        self.assertEqual([p for p in report.pairs if p.level == "block"], [])

    def test_lookalikes_block_anchor_generation(self):
        lib = self._fake(**{"ACT-9001": self._card(30), "ACT-9002": self._card(33, hair="thick-tousled")})
        self.assertTrue(casting.check(lib).blocking_for(["ACT-9002"]))

    def test_family_children_and_other_gender_not_compared(self):
        mother = self._card(30, "female")
        son = self._card(8)
        son["family_resemblance"] = "Son of ACT-9001"
        lib = self._fake(**{"ACT-9001": mother, "ACT-9002": self._card(30), "ACT-9003": son,
                            "ACT-9004": dict(self._card(31, "female"), family_resemblance="Sister of ACT-9001")})
        self.assertEqual(casting.check(lib).pairs, [])

    def test_trait_missing_from_prompt_text_is_flagged(self):
        card = self._card(30)
        card["face_and_body"] = "an Egyptian man"
        problems = casting.card_problems(dict(card, id="ACT-9001"), {})
        self.assertTrue(any("not described" in p for p in problems))

    def test_anchor_prompt_guards_against_paint_insignia_and_text(self):
        prompt = PromptComposer(self.lib, Production.load(PROD)).actor_reference("ACT-0006")
        self.assertIn("no badges or insignia", prompt)
        self.assertIn("no text or lettering", prompt)


class LoraPipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = Library.load()
        cls.prod = Production.load(PROD)
        for actor in cls.lib.actors.values():  # these tests exercise (re)training; the lock has its own test
            if actor.get("status") == "locked":
                actor["status"] = "lora_trained"

    def test_locked_actors_cannot_be_reshot_or_retrained(self):
        lib = Library.load()
        lib.actors["ACT-0003"]["status"] = "locked"
        for plan in (lambda: jobs.plan_anchors(lib, self.prod, ["ACT-0003"], 4, "final"),
                     lambda: jobs.plan_training_set(lib, ["ACT-0003"]),
                     lambda: jobs.plan_lora(lib, ["ACT-0003"], 1000)):
            with self.assertRaisesRegex(ValueError, "locked"):
                plan()

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        os.environ["MTOWER_MEDIA_ROOT"] = self.tmp.name
        self.addCleanup(os.environ.pop, "MTOWER_MEDIA_ROOT", None)

    def _fake_anchor(self, aid):
        from pathlib import Path
        path = Path(self.tmp.name) / self.lib.actors[aid]["anchor"]["media_path"]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"png")
        return path

    def test_training_set_plan_uses_anchor_and_captions_with_trigger(self):
        self._fake_anchor("ACT-0003")
        plan = jobs.plan_training_set(self.lib, ["ACT-0003"])
        self.assertEqual(len(plan), len(jobs.training_recipe()["variations"]))
        self.assertTrue(all(j.model_key == "image_edit" and j.payload["image_path"].endswith("act-0003_02.png") for j in plan))
        self.assertTrue(all(j.payload["_caption"].startswith("photo of act0003karim, ") for j in plan))
        self.assertIn("same face", plan[0].prompt)
        self.assertAlmostEqual(sum(e.total for e in jobs.estimates(plan)), 0.04 * len(plan))

    def test_training_text_adapts_to_gender_and_names_the_anchor_outfit(self):
        recipe = {v["key"]: v for v in jobs.training_recipe()["variations"]}
        edit, caption = jobs.training_text(self.lib.actors["ACT-0003"], recipe["headwear"])
        self.assertIn("cloth cap", edit)
        self.assertNotIn("headscarf", edit + caption)
        self.assertNotIn("wearing a beige", caption)
        edit, caption = jobs.training_text(self.lib.actors["ACT-0009"], recipe["headwear"])
        self.assertIn("headscarf", edit)
        _, caption = jobs.training_text(self.lib.actors["ACT-0003"], recipe["front-closeup"])
        self.assertTrue(caption.endswith("wearing a beige collared cotton shirt and a brown-and-beige cotton scarf"))
        edit, caption = jobs.training_text(self.lib.actors["ACT-0003"], recipe["smile"])
        self.assertIn("now wearing a dark knitted wool sweater", edit)
        self.assertTrue(caption.endswith("wearing a dark knitted wool sweater"))
        edit, _ = jobs.training_text(self.lib.actors["ACT-0007"], recipe["smile"])
        self.assertIn("cardigan", edit)

    def test_training_text_keeps_headscarf_on_covered_hair_actors(self):
        recipe = {v["key"]: v for v in jobs.training_recipe()["variations"]}
        edit, caption = jobs.training_text(self.lib.actors["ACT-0009"], recipe["smile"])
        self.assertIn("still wearing a headscarf", edit)
        self.assertTrue(caption.endswith("and a headscarf"))
        edit, _ = jobs.training_text(self.lib.actors["ACT-0009"], recipe["headwear"])
        self.assertNotIn("still wearing", edit)
        edit, _ = jobs.training_text(self.lib.actors["ACT-0003"], recipe["smile"])
        self.assertNotIn("headscarf", edit)

    def test_recipe_mostly_changes_outfit_and_includes_action(self):
        variations = jobs.training_recipe()["variations"]
        changed = [v for v in variations if v.get("outfit") or v.get("changes_outfit")]
        self.assertGreaterEqual(len(changed) * 4, len(variations) * 3)
        self.assertTrue({"walking", "kneeling", "carrying", "soaking-wet"} <= {v["key"] for v in variations})

    def test_lora_needs_reviewed_training_images(self):
        self._fake_anchor("ACT-0003")
        with self.assertRaisesRegex(ValueError, "kept training images"):
            jobs.plan_lora(self.lib, ["ACT-0003"], 1000)

    def test_lora_plan_skips_rejected_images_and_prices_by_steps(self):
        anchor = self._fake_anchor("ACT-0003")
        batch = jobs.actor_dir(self.lib, "ACT-0003") / "training_set" / "20260101-000000"
        batch.mkdir(parents=True)
        for n in range(12):
            (batch / f"img_{n:02d}.png").write_bytes(b"png")
        (batch / "rejected.json").write_text('{"files": ["img_00.png", "img_01.png"]}', encoding="utf-8")
        job = jobs.plan_lora(self.lib, ["ACT-0003"], 1500, allow_weak_set=True)[0]
        self.assertEqual(len(job.payload["_files"]), 11)  # 10 kept + anchor
        self.assertIn(str(anchor), job.payload["_captions"])
        self.assertAlmostEqual(jobs.estimates([job])[0].total, 3.0)

    def test_training_gate_blocks_sets_that_keep_the_anchor_outfit(self):
        self._fake_anchor("ACT-0003")
        batch = jobs.actor_dir(self.lib, "ACT-0003") / "training_set" / "20260101-000000"
        batch.mkdir(parents=True)
        outfit = self.lib.actors["ACT-0003"]["anchor"]["outfit"]
        keys = ["walking", "kneeling", "carrying"] + [f"pose{n}" for n in range(13)]
        for n, key in enumerate(keys):
            img = batch / f"act-0003-{key}_01.png"
            img.write_bytes(b"png")
            img.with_suffix(".txt").write_text(f"photo of act0003karim, {key}, wearing {outfit if n >= 3 else 'a grey shirt'}", encoding="utf-8")
        problems = jobs.check_training_set(self.lib, "ACT-0003")
        self.assertEqual(len(problems), 1)
        self.assertIn("change the outfit", problems[0])
        with self.assertRaisesRegex(ValueError, "not ready"):
            jobs.plan_lora(self.lib, ["ACT-0003"], 1000)
        for n, key in enumerate(keys[3:13], 3):
            (batch / f"act-0003-{key}_01.txt").write_text(f"photo of act0003karim, {key}, wearing a striped shirt", encoding="utf-8")
        self.assertEqual(jobs.check_training_set(self.lib, "ACT-0003"), [])

    def test_training_needs_a_trigger_word_and_matching_captions(self):
        import copy
        actor = copy.deepcopy(self.lib.actors["ACT-0003"])
        actor["lora"]["trigger"] = None
        recipe = jobs.training_recipe()["variations"]
        with self.assertRaisesRegex(ValueError, "no lora.trigger"):
            jobs.training_text(actor, recipe[0])
        self._fake_anchor("ACT-0003")
        batch = jobs.actor_dir(self.lib, "ACT-0003") / "training_set" / "20260101-000000"
        batch.mkdir(parents=True)
        img = batch / "act-0003-walking_01.png"
        img.write_bytes(b"png")
        img.with_suffix(".txt").write_text("photo of None, walking, wearing a grey shirt", encoding="utf-8")
        self.assertTrue(any("trigger word" in p for p in jobs.check_training_set(self.lib, "ACT-0003")))

    def test_lora_tests_use_real_solo_shots_from_the_production(self):
        lib = Library.load()
        lib.actors["ACT-0003"].update(status="lora_trained", lora={**lib.actors["ACT-0003"]["lora"], "url": "https://example.invalid/x"})
        plan = jobs.plan_lora_tests(lib, self.prod, ["ACT-0003"])
        self.assertEqual(len(plan), 3)
        self.assertTrue(all(j.kind == "keyframe" and j.payload.get("loras") for j in plan))
        self.assertEqual(len({j.target.split("-")[0] for j in plan}), 3)  # spread across different beats

    def test_training_zip_pairs_images_with_captions(self):
        import io
        import zipfile
        from pathlib import Path
        img = Path(self.tmp.name) / "a.png"
        img.write_bytes(b"png")
        img.with_suffix(".txt").write_text("photo of x, smiling", encoding="utf-8")
        other = Path(self.tmp.name) / "b.png"
        other.write_bytes(b"png")
        zf = zipfile.ZipFile(io.BytesIO(jobs._training_zip([str(img), str(other)], {str(other): "photo of x, profile"})))
        self.assertEqual(sorted(zf.namelist()), ["001.png", "001.txt", "002.png", "002.txt"])
        self.assertEqual(zf.read("002.txt").decode(), "photo of x, profile")

    def test_keyframes_attach_face_models_only_when_trained(self):
        untrained = Library.load()
        untrained.actors["ACT-0003"]["status"] = "anchor_approved"
        plan = jobs.plan_keyframes(untrained, self.prod, "02_act_two", ["2.5-05"], "draft", 1)
        self.assertNotIn("loras", plan[0].payload)
        lib = Library.load()
        actor = lib.actors["ACT-0003"]
        actor["status"] = "lora_trained"
        actor["lora"] = {**actor["lora"], "url": "https://example.invalid/act0003.safetensors"}
        plan = jobs.plan_keyframes(lib, self.prod, "02_act_two", ["2.5-05"], "draft", 1)
        self.assertEqual(plan[0].model_key, "image_lora")
        self.assertEqual(plan[0].payload["loras"][0]["path"], "https://example.invalid/act0003.safetensors")
        self.assertIn("act0003karim", plan[0].prompt)

    def _lib_without_prop_models(self):
        import copy
        lib = copy.deepcopy(self.lib)
        for p in lib.props.values():
            p["status"] = "concept"
        return lib

    def test_group_shot_renders_extras_without_face_model_then_repaints_lead(self):
        # T.2-01 was the example until 2026-10-17, when Shalabi became an uncast distant figure there
        plan = jobs.plan_keyframes(self._lib_without_prop_models(), self.prod, None, ["2.3-04"], "draft", 2)
        self.assertEqual([j.kind for j in plan], ["keyframe", "face_pass"])
        base, face = plan
        self.assertNotIn("loras", base.payload)
        self.assertEqual(base.model_key, "image_draft")
        self.assertNotIn("act0001tarek", base.prompt)
        self.assertEqual(face.model_key, "face_swap")  # Azure masked edit with the anchor portrait
        self.assertEqual(face.out_dir, base.out_dir)
        self.assertEqual(face.payload["_strategy"], "vision")  # the reviewer finds the background captain by role and action
        self.assertEqual(face.payload["_who"]["chars"][0]["char"], "C-01")
        self.assertIn("captain", face.payload["_who"]["chars"][0]["role"].lower())
        char = face.payload["_chars"][0]
        self.assertEqual(char["char"], "C-01")
        self.assertTrue(char["anchor"].replace("\\", "/").endswith("ACT-0001_tarek-selim/anchor/20261011-155514/act-0001_04.png"))
        self.assertTrue(char["prompt"].startswith("Image 1 is a still frame"))
        self.assertIn("same head size relative to the shoulders", char["prompt"])
        for word in ("helmet", "beret", "headset", "cap,"):  # naming them made gpt-image add them (2026-10-15)
            self.assertNotIn(word, char["prompt"])
        self.assertNotIn("act0001tarek", char["prompt"])  # no trigger words: gpt-image sees the portrait
        self.assertEqual(face.extra, [("face_detect", 2)])  # detect before (the after-check is off: QA measures it)
        self.assertAlmostEqual(jobs.estimates([face])[0].total, 2 * 0.06 + 2 * 0.02)

    def test_fal_face_pass_on_request(self):
        from unittest import mock
        cfg = {**jobs.engine_config(), "face_pass": {"method": "fal"}}
        with mock.patch.object(jobs, "engine_config", return_value=cfg):
            plan = jobs.plan_keyframes(self._lib_without_prop_models(), self.prod, None, ["2.3-04"], "draft", 2)
        face = plan[1]
        self.assertEqual(face.model_key, "image_inpaint")
        prompt = face.payload["_chars"][0]["prompt"]
        self.assertTrue(prompt.startswith("close-up photo of the face of act0001tarek"))
        self.assertNotIn("boots", prompt)  # the crop shows a head: no clothes or kit in the face prompt
        self.assertEqual(face.extra, [("face_detect", 2), ("face_detect_fallback", 2)])
        self.assertAlmostEqual(jobs.estimates([face])[0].total, 2 * 0.035 + 2 * 0.02 + 2 * 0.005)

    def test_face_check_flags_grown_or_moved_faces(self):
        before = {"x": 100, "y": 100, "w": 100, "h": 120}
        self.assertTrue(faces.check_face(before, [{"x": 105, "y": 98, "w": 104, "h": 122}])["ok"])
        grown = faces.check_face(before, [{"x": 80, "y": 80, "w": 140, "h": 170}])
        self.assertFalse(grown["ok"])
        self.assertIn("grew", grown["reason"])
        self.assertFalse(faces.check_face(before, [{"x": 300, "y": 100, "w": 100, "h": 120}])["ok"])
        self.assertFalse(faces.check_face(before, [])["ok"])

    def test_alpha_mask_is_transparent_on_the_face_only(self):
        png = faces.alpha_mask_png(64, 36, {"x": 24, "y": 10, "w": 16, "h": 16})
        self.assertEqual(png[25], 6)  # colour type RGBA
        import zlib
        raw = zlib.decompress(png[png.index(b"IDAT") + 4:png.index(b"IEND") - 8])
        row = raw[18 * (1 + 64 * 4) + 1:19 * (1 + 64 * 4)]
        self.assertEqual(row[32 * 4 + 3], 0)    # centre of the face: repaint
        self.assertEqual(row[2 * 4 + 3], 255)   # far left: keep

    def test_solo_shot_keeps_single_pass_with_face_model(self):
        plan = jobs.plan_keyframes(self.lib, self.prod, "02_act_two", ["2.5-05"], "draft", 1)
        self.assertEqual([j.kind for j in plan], ["keyframe"])
        self.assertEqual(plan[0].model_key, "image_lora")

    def test_trained_prop_adds_its_model_and_trigger(self):
        lib = self._lib_without_prop_models()
        lib.props["PRP-0002"].update({"status": "lora_trained",
                                      "lora": {"trigger": "prp0002rpg7", "url": "https://example.invalid/rpg.safetensors"}})
        plan = jobs.plan_keyframes(lib, self.prod, None, ["T.2-01"], "draft", 1)
        self.assertEqual(plan[0].model_key, "image_lora")
        self.assertEqual([w["path"] for w in plan[0].payload["loras"]], ["https://example.invalid/rpg.safetensors"])
        self.assertIn("prp0002rpg7, Soviet RPG-7", plan[0].prompt)

    def test_prop_training_set_needs_reference_photos(self):
        with self.assertRaisesRegex(FileNotFoundError, "reference photos"):
            jobs.plan_prop_training_set(self.lib, ["PRP-0003"])
        from pathlib import Path
        refs = jobs.prop_dir(self.lib, "PRP-0003") / "references"
        refs.mkdir(parents=True)
        (refs / "a.png").write_bytes(b"png")
        (refs / "b.jpg").write_bytes(b"jpg")
        plan = jobs.plan_prop_training_set(self.lib, ["PRP-0003"])
        recipe = jobs.prop_recipe()
        self.assertEqual(len(plan), len(recipe["variations"]) + len(self.lib.props["PRP-0003"]["training_actions"]))
        self.assertEqual({Path(j.payload["image_path"]).name for j in plan}, {"a.png", "b.jpg"})
        self.assertTrue(all(j.payload["_caption"].startswith("photo of prp0003malyutka, ") for j in plan))
        self.assertIn("Do not redesign", plan[0].prompt)


    def test_import_from_inbox_then_plan_face_pass(self):
        from mtower import faces
        inbox = jobs.inbox_dir()
        inbox.mkdir(parents=True)
        mask = faces.ellipse_mask_png(300, 200, {"x": 100, "y": 50, "w": 40, "h": 50})  # any valid PNG will do
        (inbox / "2.6-02.png").write_bytes(mask)
        (inbox / "2.6-02 take2.png").write_bytes(mask)
        (inbox / "notes.png").write_bytes(mask)
        found = jobs.inbox_files()
        self.assertEqual(list(found), ["2.6-02"])
        out = jobs.import_keyframes(self.prod, "2.6-02", found["2.6-02"])
        self.assertEqual(faces.image_size(out / "2-6-02_01.png"), (1280, 720))
        self.assertTrue((out / "original" / "2.6-02.png").exists())
        self.assertFalse((inbox / "2.6-02.png").exists())
        plan = jobs.plan_face_pass(self.lib, self.prod, ["2.6-02"])
        self.assertEqual(len(plan), 1)
        self.assertEqual((plan[0].units, plan[0].extra), (2, [("face_detect", 2)]))
        prompt = plan[0].payload["_chars"][0]["prompt"]
        self.assertTrue(prompt.startswith("Image 1 is a still frame"))
        self.assertNotIn("RPG", prompt)

    def test_chatgpt_prompt_has_no_trigger_words(self):
        composer = PromptComposer(self.lib, self.prod)
        _, beat, shot = self.prod.find_shot("T.2-01")
        text = composer.chatgpt_prompt(beat, shot)
        self.assertNotRegex(text, r"act\d{4}|prp\d{4}")
        self.assertIn("16:9", text)
        self.assertIn("RPG-7", text)

    def test_composition_plan_attaches_prop_references_and_chains_face_pass(self):
        refs = jobs.prop_dir(self.lib, "PRP-0003") / "references"
        refs.mkdir(parents=True)
        (refs / "ref_01_silver.png").write_bytes(b"png")
        (refs / "ref_02_launcher_on_case.png").write_bytes(b"png")
        plan = jobs.plan_compositions(self.lib, self.prod, ["1.6-03"], variants=2)
        compose, face = plan
        self.assertEqual((compose.kind, compose.model_key, compose.units, compose.price_usd), ("composition", "image_compose", 2, 0.08))
        self.assertEqual([os.path.basename(r) for r in compose.payload["_references"]], ["ref_02_launcher_on_case.png"])
        self.assertNotRegex(compose.prompt, r"act\d{4}|prp\d{4}")
        self.assertIn("attached photos", compose.prompt)
        self.assertEqual((face.kind, face.out_dir, face.units), ("face_pass", compose.out_dir, 2))
        est = jobs.estimates(plan)
        self.assertEqual(est[0].provider, "azure")
        self.assertAlmostEqual(est[0].total, 2 * 0.08 + 2 * 0.03)
        self.assertEqual(jobs.plan_compositions(self.lib, self.prod, ["3.13-01"], quality="high", face_pass=False)[0].price_usd, 0.3)
        with self.assertRaises(ValueError):
            jobs.plan_compositions(self.lib, self.prod, ["1.6-03"], quality="ultra")


class AzureTests(unittest.TestCase):
    def test_actual_cost_from_token_usage(self):
        from mtower.providers.azure import usage_cost
        pricing = {"text_input_per_m": 5, "image_input_per_m": 8, "output_per_m": 30}
        usage = {"input_tokens": 1200, "input_tokens_details": {"text_tokens": 200, "image_tokens": 1000}, "output_tokens": 2000}
        self.assertAlmostEqual(usage_cost(usage, pricing), (200 * 5 + 1000 * 8 + 2000 * 30) / 1e6)

    def test_multipart_carries_every_reference_photo(self):
        import tempfile
        from pathlib import Path
        from mtower.providers.azure import _multipart
        with tempfile.TemporaryDirectory() as tmp:
            files = [Path(tmp) / "a.png", Path(tmp) / "b.jpg"]
            for f in files:
                f.write_bytes(b"\x89PNG")
            body, ctype = _multipart({"prompt": "x", "n": "1"}, [("image[]", f) for f in files])
        self.assertTrue(ctype.startswith("multipart/form-data; boundary="))
        self.assertEqual(body.count(b'name="image[]"'), 2)
        self.assertIn(b"Content-Type: image/jpeg", body)

    def test_azure_spending_has_its_own_monthly_limit(self):
        os.environ["MTOWER_BATCH_LIMIT_USD"] = "5"
        os.environ["MTOWER_MONTHLY_LIMIT_USD"] = "0.0001"  # fal/ElevenLabs budget already used up
        os.environ["MTOWER_AZURE_MONTHLY_LIMIT_USD"] = "1000"
        self.addCleanup(os.environ.pop, "MTOWER_AZURE_MONTHLY_LIMIT_USD", None)
        self.addCleanup(os.environ.__setitem__, "MTOWER_MONTHLY_LIMIT_USD", "1000")
        azure = costs.estimate("image_compose", 1)
        self.assertEqual(costs.budget_group(azure.provider), "azure")
        self.assertAlmostEqual(costs.authorize([azure], 0.08), 0.08)
        with self.assertRaisesRegex(costs.SpendingError, "fal/ElevenLabs monthly limit"):
            costs.authorize([costs.estimate("image_draft", 1)], 1)
        os.environ["MTOWER_AZURE_MONTHLY_LIMIT_USD"] = "0.01"
        with self.assertRaisesRegex(costs.SpendingError, "Azure monthly limit"):
            costs.authorize([azure], 0.08)


class FaceTests(unittest.TestCase):
    BOXES = [{"x": 900, "y": 120, "w": 100, "h": 120, "label": "human face"},
             {"x": 200, "y": 130, "w": 90, "h": 110, "label": "human face"},
             {"x": 610, "y": 180, "w": 40, "h": 50, "label": "human face"},
             {"x": 50, "y": 100, "w": 400, "h": 600, "label": "man"}]

    def test_pick_faces(self):
        from mtower import faces
        found = faces.faces_from_detection({"results": {"bboxes": self.BOXES}})
        self.assertEqual(len(found), 3)
        self.assertEqual(faces.pick_faces(found, 1280, 1)[0]["x"], 900)
        self.assertEqual(faces.pick_faces(found, 1280, 1, "center")[0]["x"], 610)
        self.assertEqual([b["x"] for b in faces.pick_faces(found, 1280, 2)], [200, 900])
        with self.assertRaises(ValueError):
            faces.pick_faces(found, 1280, 1, "nearest")

    def test_moondream_boxes_are_scaled_to_pixels(self):
        from mtower import faces
        result = {"objects": [{"x_min": 0.25, "y_min": 0.5, "x_max": 0.5, "y_max": 0.75}]}
        self.assertEqual(faces.faces_from_detection(result, 1280, 720),
                         [{"x": 320.0, "y": 360.0, "w": 320.0, "h": 180.0, "label": "face"}])
        with self.assertRaises(ValueError):
            faces.faces_from_detection(result)

    def test_merge_boxes(self):
        from mtower import faces
        found = faces.faces_from_detection({"results": {"bboxes": self.BOXES}})
        extra = [{"x": 905, "y": 125, "w": 90, "h": 110}, {"x": 1100, "y": 300, "w": 40, "h": 40}]
        self.assertEqual([b["x"] for b in faces.merge_boxes(found, extra)], [900, 200, 610, 1100])

    def test_patch_rect_stays_inside_picture(self):
        from mtower import faces
        self.assertEqual(faces.patch_rect({"x": 600, "y": 300, "w": 100, "h": 100}, 1280, 720), (520, 220, 260))
        self.assertEqual(faces.patch_rect({"x": 5, "y": 5, "w": 30, "h": 40}, 1280, 720), (0, 0, 104))
        self.assertEqual(faces.patch_rect({"x": 1200, "y": 600, "w": 400, "h": 400}, 1280, 720)[2], 720)
        local = faces.scale_box({"x": 600, "y": 300, "w": 100, "h": 100}, 520, 220, 960 / 260)
        self.assertAlmostEqual(local["x"] + local["w"] / 2, 480)

    def test_mask_png_matches_image_size(self):
        import tempfile
        from pathlib import Path
        from mtower import faces
        data = faces.ellipse_mask_png(64, 36, {"x": 20, "y": 10, "w": 10, "h": 12})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "m.png"
            path.write_bytes(data)
            self.assertEqual(faces.image_size(path), (64, 36))
        import zlib
        raw = zlib.decompress(data[data.index(b"IDAT") + 4:data.index(b"IEND") - 8])
        row = 15  # face centre row (with the upward nudge)
        line = raw[row * 65 + 1:(row + 1) * 65]
        self.assertEqual(line[25], 255)
        self.assertEqual(line[0], 0)


class CostTests(unittest.TestCase):
    def setUp(self):
        os.environ["MTOWER_BATCH_LIMIT_USD"] = "5"
        os.environ["MTOWER_MONTHLY_LIMIT_USD"] = "1000"

    def test_unverified_price_blocks_run(self):
        with self.assertRaises(costs.SpendingError):
            costs.authorize([costs.Estimate("image_draft", 8, "image", None)], 10)

    def test_dry_run_without_confirmation(self):
        with self.assertRaisesRegex(costs.SpendingError, "Dry run"):
            costs.authorize([costs.Estimate("image_draft", 8, "image", 0.03)], None)

    def test_confirmation_must_cover_estimate(self):
        with self.assertRaises(costs.SpendingError):
            costs.authorize([costs.Estimate("image_draft", 8, "image", 0.25)], 1.0)

    def test_batch_limit(self):
        with self.assertRaisesRegex(costs.SpendingError, "batch limit"):
            costs.authorize([costs.Estimate("video_default", 100, "second", 0.1)], 100)

    def test_authorized(self):
        self.assertAlmostEqual(costs.authorize([costs.Estimate("image_draft", 8, "image", 0.03)], 0.24), 0.24)

    def test_image_sizes_stay_within_the_one_megapixel_price(self):
        from mtower.settings import engine_config
        for key, m in engine_config()["models"].items():
            size = m.get("payload", {}).get("image_size")
            if isinstance(size, dict):
                self.assertLessEqual(size["width"] * size["height"], 1_000_000, key)


class GalleryTests(unittest.TestCase):
    def _batch(self, root: Path, rel: str, kind: str, target: str, score: int | None) -> Path:
        import json
        folder = root / rel
        folder.mkdir(parents=True)
        (folder / "manifest.json").write_text(json.dumps({"kind": kind, "target": target}), encoding="utf-8")
        (folder / "x_01.png").write_bytes(b"\x89PNG")
        if score is not None:
            (folder / "x_01.qa.json").write_text(json.dumps({"verdict": "fail", "score": score}), encoding="utf-8")
        return folder

    def test_gate_follows_the_agreed_scores(self):
        from mtower import gallery
        cfg = {"min_score": {"keyframe": 8, "clip": 8, "default": 7}, "reviewed_kinds": ["keyframe", "anchor", "poster"]}
        self.assertEqual(gallery.min_score("keyframe", cfg), 8)
        self.assertEqual(gallery.min_score("poster", cfg), 7)
        self.assertIsNone(gallery.min_score("narration", cfg))
        self.assertTrue(gallery.gate_check("keyframe", {"score": 8}, cfg)[0])
        self.assertFalse(gallery.gate_check("keyframe", {"score": 7}, cfg)[0])
        self.assertTrue(gallery.gate_check("anchor", {"score": 7}, cfg)[0])
        self.assertFalse(gallery.gate_check("keyframe", None, cfg)[0])  # not reviewed
        self.assertTrue(gallery.gate_check("narration", None, cfg)[0])

    def test_approve_below_gate_needs_a_reason_and_records_it(self):
        import json
        from mtower import gallery
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            folder = self._batch(root, "keyframes/02_act_two/2.5-01/20261013-100000", "keyframe", "2.5-01", 6)
            refused = gallery.approve(root, "keyframes/02_act_two/2.5-01/20261013-100000", "x_01.png")
            self.assertFalse(refused["ok"])
            self.assertTrue(refused["gate"])
            self.assertFalse((folder / "approved.json").exists())
            self.assertTrue(gallery.approve(root, "keyframes/02_act_two/2.5-01/20261013-100000", "x_01.png", "best we have")["ok"])
            record = json.loads((folder / "approved.json").read_text(encoding="utf-8"))
            self.assertEqual((record["file"], record["override"], record["qa_score"]), ("x_01.png", "best we have", 6))
            data = gallery.collect(root)
            g = data["groups"][0]
            self.assertEqual((g["section"], g["sub"], g["status"], g["override"]), ("keyframe", "02_act_two", "ok", "best we have"))
            self.assertFalse(gallery.approve(root, "../outside", "x_01.png")["ok"])

    def test_approving_a_take_supersedes_other_approvals_of_the_shot(self):
        from mtower import gallery
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            old = self._batch(root, "keyframes/02_act_two/2.5-01/20261013-100000", "keyframe", "2.5-01", 9)
            new = self._batch(root, "keyframes/02_act_two/2.5-01/20261013-110000", "keyframe", "2.5-01", 9)
            other = self._batch(root, "keyframes/02_act_two/2.5-02/20261013-100000", "keyframe", "2.5-02", 9)
            self.assertTrue(gallery.approve(root, "keyframes/02_act_two/2.5-01/20261013-110000", "x_01.png")["ok"])
            self.assertTrue(gallery.approve(root, "keyframes/02_act_two/2.5-02/20261013-100000", "x_01.png")["ok"])
            self.assertTrue(gallery.approve(root, "keyframes/02_act_two/2.5-01/20261013-100000", "x_01.png")["ok"])
            self.assertTrue((old / "approved.json").exists())
            self.assertFalse((new / "approved.json").exists())
            self.assertTrue((new / "approved.superseded.json").exists())
            self.assertTrue((other / "approved.json").exists())
            undone = gallery.unapprove(root, "keyframes/02_act_two/2.5-01/20261013-100000", "x_01.png")
            self.assertEqual(undone, {"ok": True, "restored": "20261013-110000/x_01.png"})
            self.assertTrue((new / "approved.json").exists())
            self.assertFalse((old / "approved.json").exists())
            self.assertFalse(gallery.unapprove(root, "keyframes/02_act_two/2.5-01/20261013-100000", "x_01.png")["ok"])

    def test_newer_candidates_and_below_gate_status(self):
        import json
        from mtower import gallery
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            old = self._batch(root, "keyframes/01_act_one/1.3-02/20261012-100000", "keyframe", "1.3-02", 7)
            (old / "approved.json").write_text(json.dumps({"file": "x_01.png"}), encoding="utf-8")
            g = gallery.collect(root)["groups"][0]
            self.assertEqual(g["status"], "below_gate")
            self._batch(root, "keyframes/01_act_one/1.3-02/20261013-100000", "keyframe", "1.3-02", 9)
            g = gallery.collect(root)["groups"][0]
            self.assertEqual((g["best"], g["approved_score"], g["newer"]), (9, 7, 1))


if __name__ == "__main__":
    unittest.main()
