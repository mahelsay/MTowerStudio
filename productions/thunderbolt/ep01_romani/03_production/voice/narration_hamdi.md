# Narration — Hamdi Shalabi remembering (حمدي شلبي بيحكي)

**Status:** drama-first narration (D-20, D-21), draft by the director, 2026-10-13. The series is carried by the characters and their dialogue; the narration is now **old Hamdi Shalabi, fifty years later, telling his grandchildren what happened**, in his own everyday Egyptian Arabic, first person, about a third of the earlier documentary version (`narration_egyptian.md`, kept for reference).

**Source of truth for facts:** the screenplay VO in `01_development/screenplay/` — every number, name and claim here must match it. Hamdi speaks only about what he lived and what is documented; he never narrates the families at home (he could not have seen them).

**How the engine reads this file** (`production_config.json` → `narration.script = "hamdi"`, `narration.cast = "N-01"`):
- one `## <beat>` section per narrated beat of the screenplay; every line up to the next `## ` belongs to it — do not add other `#` headings;
- a section that is only `—` is **deliberately silent** (the dialogue and the pictures carry that beat);
- an optional `<!-- intensity: 7; volume: low; pace: slow; emotion: ... -->` comment sets the performance of that beat (default: intensity 5, low, measured, remembering);
- `./mtower.ps1 voice --part <part> --beat <beat>` records it with the N-01 cast voice, re-recording until speech-to-text hears it as written.

**Writing rules:** first person («أنا»، «رِجَّالْتِي»، «إِحْنَا»); short sentences, the way an old man talks, not the way a documentary reads; «…» is a real pause. Write **numbers and «صاعقة» without diacritics** (the voices otherwise swallow them); keep «مَيَّة» (water) diacritized so it is never read as «مية» (a hundred).

**Length:** 22 of 42 beats narrated, about 300 words against about 1,000 before (≈ 30%). **Drama rewrite (2026-10-15):** Act One is down to one short line in 1.1, 1.4, 1.9 and 1.11 — the characters now say the rest; the other acts follow as they are rewritten.

## T.3

—

## 1.1

<!-- intensity: 4; volume: low; pace: measured; emotion: quiet pride in his old company -->
قَبْل الحَرْب بِشُهُور… كَانُوا بِيِعْمِلُوا مُسَابْقَات بَيْن سَرَايَا الصاعقة.

## 1.4

<!-- intensity: 5; volume: low; pace: slow; emotion: the weight of that evening -->
يُوم خمسة أُكْتُوبَر بِاللِّيل اِتْطَلَبْت… كُنْت قَائِد السَّرِيَّة الأُولَى، الكَتِيبَة مية تلاتة وتمانين صاعقة.

## 1.6

—

## 1.8

—

## 1.9

<!-- intensity: 6; volume: low; pace: measured; emotion: the moment the war began -->
يُوم ستة أُكْتُوبَر، السَّاعَة اتنين الضُّهْر… الحَرْب قَامِت.

## 1.11

<!-- intensity: 5; volume: low; pace: slow; emotion: plain fact, a little wonder at how young and bare they were -->
السَّاعَة ستة المِسَا طِلِعْنَا مِن مَطَار الصَّالْحِيَّة… فِي ست طَيَّارَات «مِي تمانية».

## 2.1

<!-- intensity: 6; volume: low; pace: measured; emotion: the shock of the cold mud, remembered -->
سَهْل الطِّينَة… طِين وِمِلْح وِمَيَّة. مَا تِشِيلْش طَيَّارَة.

## 2.2

<!-- intensity: 6; volume: low; pace: slow; emotion: grief and gratitude, quietly -->
وِالخَمْس طَيَّارَات التَّانْيِين… رِجْعُوا غَرْب القَنَاة.

## 2.3

—

## 2.4

—

## 2.5

<!-- intensity: 6; volume: low; pace: slow; emotion: the memory of the pain, said plainly -->
عشرين كِيلُو فِي المَيَّة المَالْحَة وِالطِّين… وِالمِلْح بِيَاكُل فِي رِجْلِينَا. وِالسِّلَاح فُوق رَاسْنَا، عَشَان وَلَا سِلَاح يِعَطَّل.

## 2.8

—

## 2.9

—

## 2.10

—

## 2.11

—

## 2.12

<!-- intensity: 5; volume: low; pace: measured; emotion: the dismay of seeing the flat ground -->
وِصِلْنَا آخِر اللِّيل… لَقِينَا الأَرْض مَفْرُودَة زَيّ السِّجَّادَة. مَافِيهَاش مَكَان تِسْتَخَبَّى فِيه.

## 2.13

—

## 2.14

—

## 2.15

<!-- intensity: 5; volume: low; pace: measured; emotion: a quiet, proud irony -->
العَدُوّ كَان عَارِف إِنّ فِيه صاعقة نِزْلِت وَرَا خُطُوطُه… بَسّ مِش عَارِف فِين. فَاللِّوَاء مَا اِتْحَرَّكْش فِي مِيعَادُه. وِالتَّلَات سَاعَات اِتْحَقَّقُوا… قَبْل مَا نِضْرَب طَلْقَة.

## 2.16

—

## 3.1

<!-- intensity: 5; volume: low; pace: measured; emotion: the held breath of that morning -->
السَّاعَة سبعة الصُّبْح… طَيَّارَة اسْتِطْلَاع.

## 3.3

—

## 3.4

<!-- intensity: 7; volume: low; pace: slow; emotion: the hardest patience of his life -->
وِعَدِّت كَتِيبِة دَبَّابَات كَامْلَة قُدَّام عِينِينَا. الصَّبْر سَاعِتْهَا… كَان أَصْعَب مِن القِتَال.

## 3.5

—

## 3.7

—

## 3.8

<!-- intensity: 6; volume: low; pace: measured; emotion: the long battle, counted -->
تلات سَاعَات… أربعة… خمسة. وِعَلَى حَسَب مَصَادِرْنَا، ضَرَبْنَا مَا بَيْن خمستاشر وتمنتاشر دَبَّابَة.

## 3.11

—

## 3.12

—

## 3.13

<!-- intensity: 7; volume: low; pace: slow; emotion: the moment the trap turned on them -->
وِبَعْدِين… بَعَتُوا مُشَاة عَلَى نُص جَنَازِير، لَفُّوا مِن وَرَانَا.

## 4.1

<!-- intensity: 7; volume: low; pace: slow; emotion: grief for the rear groups -->
وَرَا الكَمِين، الجَمَاعَات الصُّغَيَّرَة وِقْفِت قُصَاد المُشَاة اللِّي لَفُّوا عَلِينَا… وِكْتِير مِنْهُم مَا رِجْعُوش.

## 4.2

—

## 4.3

—

## 4.4

—

## 4.5

<!-- intensity: 8; volume: low; pace: slow; emotion: awe and grief for his men; the voice nearly breaks -->
القُنْبُلَة دِي مَا تِتْرِمِيش غِير مِن قُرَيِّب… فَرِجَّالْتِي طِلْعُوا مِن حُفَرْهُم، وِجِرْيُوا عَلَى الدَّبَّابَات.

## 4.7

—

## 4.9

<!-- intensity: 8; volume: low; pace: slow; emotion: the heaviest memory; quiet, almost a whisper at the end -->
فِي الضَّلْمَة، دَفَنَّا شُهَدَانَا فِي الرَّمْل… وِأَخَدْنَا سِلَاحْهُم.

## 5.1

—

## 5.2

<!-- intensity: 5; volume: low; pace: slow; emotion: exhaustion remembered -->
خمس أَيَّام مَشْي… نِسْتَخَبَّى فِي الكُثْبَان، وِنِمْشِي… وِنِمْشِي.

## 5.4

—

## 5.7

<!-- intensity: 5; volume: low; pace: measured; emotion: quiet pride, without boasting -->
المَطْلُوب كَان تلات سَاعَات أَوْ أربعة… وِالكَمِين عَطَّلْهُم تمانية وأربعين سَاعَة.

## 5.8

<!-- intensity: 7; volume: low; pace: slow; emotion: a dedication to his men; love and loss -->
لِرِجَّالِة السَّرِيَّة الأُولَى… اللِّي رِجْعُوا، وِاللِّي فِضْلُوا فِي الرِّمْلَة.
