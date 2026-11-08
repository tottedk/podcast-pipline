# Content style template
**Version 2.6 - 2026-11-07** = v2.5 + a **humanity dial** and everyday/human rules (Thomas, 7 Nov: "more humanity - step away from the facts and nerd knowledge and bring it down to everyday life"). Implemented by `tools\brief_gen.py` (technical v1.14) as the **default for new briefs** (`brief.content_style` absent or `"v2.6"`). v2.5 and v2.3 stay selectable and run unchanged. Everything not listed here is exactly as in `content_style_v2.5.md` (cast bible, cold open, chapter shapes, crux + concessions, running gag, ledger, ending). v2.5 and older files are not edited.

## 0. The humanity dial (next to tone and depth)
`brief.humanity` = `low` | `medium` (default) | `high`; Episode desk field "Humanity". Only v2.6 uses it.
- **low:** mostly on the topic; an everyday moment every second chapter; nerd cap 3 turns.
- **medium:** every chapter touches ordinary life (Carter's everyday beat); each guest's own experience once or twice; one tangent; nerd cap 2 turns.
- **high:** the topic seen through ordinary lives; every chapter has an everyday beat plus a personal moment; more warmth and small talk; nerd cap 1 turn.

## 1. Everyday beat per chapter ("what does this mean for me")
- In **every chapter** Carter acts as the listener's stand-in and asks, in plain words, what this means for an ordinary person (my phone, my job, my kids, my money, my Tuesday).
- The guests answer with a **concrete daily-life picture**, not a principle.

## 2. Personal angle per guest
- Each guest tells something from their **own life as that character** (job, family, a mistake, something that happened this year), first person, consistent with the bible (`who`, `running_life`).
- Planned in the episode plan (`personal_angles`: 1-2 per guest with chapter and one-line experience). Invented and modest; always the fictional character's experience, never a real person's.

## 3. One tangent per episode
- Exactly **one 30-60 s detour** (about 80-150 words over several short turns), planned (`tangent`: chapter, who, story, point): an everyday off-topic story or hobby rant true to the character.
- Someone teases them for it; it **lands back with a point** tied to the chapter's case.

## 4. Analogies over jargon, nerd cap
- Every mechanism is explained with an everyday comparison first (kitchen, traffic, a pub quiz, a group chat); the technical term second, if at all.
- **Nerd cap:** never more than N turns in a row of pure technical detail (names, numbers, mechanisms, history), N by the dial (3/2/1). Then someone brings it back to daily life, reacts, jokes or asks "so what?".

## 5. Real conversation
- Light disagreement, teasing and small laughs; interruptions (a line may break off with "..." and the other jumps in); finishing each other's sentences now and then; admitting "I don't know". Warmth over cleverness.

## 6. Turns (shorter than v2.5)
- **Average 15-30 words, hard max 70** (v2.5: 25-40 / 90). brief_gen rejects part attempts with an average over 35 words or more than 10% of turns over 70 (v2.5: 50 / 20% over 90). The ledger reports the 15-30 target. Carter speaks in relaxed, complete sentences, not clipped rapid-fire (his clipped questions are what Drama 3 rushes).

## 7. Delivery tags
- Unchanged in the script: only `[laughs]` / `[sighs]` (episode_qc). Plain-language delivery **directions** are added at render time by `drama3_generate.py` v1.14 (technical_v1.14.md), not by the script writer.
