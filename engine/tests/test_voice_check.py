import unittest

from mtower.voice import compare, normalize


class ListenCheckTests(unittest.TestCase):
    def test_normalize_drops_diacritics_and_spelling_variants(self):
        self.assertEqual(normalize("القَائِد لَفّ عَلَى رِجَّالْتُه، «مَالُوتْكَا»…"),
                         ["القائد", "لف", "علي", "رجالته", "مالوتكا"])

    def test_full_match(self):
        r = compare("حَمْدِي شَلَبِي قَفَل أَجْهِزِة اللَّاسِلْكِي", "حمدي شلبي قفل أجهزة اللاسلكي")
        self.assertEqual(r["match"], 1.0)
        self.assertEqual(r["missing"], [])

    def test_swallowed_phrase_is_reported(self):
        r = compare("مِن الكَتِيبَة مية تلاتة وتمانين صاعقة وِاسْتَلَم ظَرْف", "من الكتيبة واستلم ظرف")
        self.assertEqual(r["missing"], ["ميه تلاته وتمانين صاعقه"])

    def test_numbers_heard_as_digits_count(self):
        r = compare("مية تلاتة وتمانين صاعقة", "183 صاعقة")
        self.assertEqual(r["missing"], [])


if __name__ == "__main__":
    unittest.main()
