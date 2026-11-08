# Content style template
**Version 2.5 - 2026-11-01** = v2.3 + the entertainment fixes from the podcast review (fixed cast, story-first, short turns, used-material ledger). Implemented by `tools\brief_gen.py` (technical v1.13) as the **default for new briefs** (`brief.content_style` absent or `"v2.5"`). v2.3 stays selectable (`"content_style": "v2.3"` in the brief, or `--content_style v2.3`) and runs the old prompts unchanged. v2.4 (Fault Lines moderated debate) is a separate format and is not produced by brief_gen. v2.3 and v2.4 files are not edited.

## 1. Cast: fixed character bibles (`templates\cast_bible_v1.json`)
- **Carter is always the host.** Guests come from the bible, injected **verbatim** into the plan and every script prompt: who they are, expertise, lens, natural side, voice, quirk, flaw, how they concede, stake hint.
- **Roster (9 usable guests):** Clara (US builder-optimist), Lachlan (Australian failure-mode sceptic), Isla (Scottish moral philosopher / ex-hospice chaplain), Marcus (US incentives economist, ex-actuary), Willa (American ex-trust-and-safety insider-critic), Zara (South African historian of technology), Imogen (British evidence-hawk psychologist), Frank (US retired union electrician / councilman), Samuel (Indian-English scale engineer).
- **Not in the bible:** Elliot (out: monotone voice), Hugh (never with Carter, and Carter always hosts, so unusable), Maya / Declan / Alice / Mary (banned). brief_gen rejects Elliot, Hugh and the banned names.
- **Pairing guidance** (`pairings` in the bible): 10 curated pairs that clash well (e.g. Clara-Lachlan, Isla-Marcus, Zara-Samuel, Willa-Clara); avoid Frank+Marcus (three US men) and Frank alone with Carter. Weights from the handover still apply (Frank low, Samuel 0.25).
- The plan picks only **positions** (one per guest, true to their bible) and **one personal stake** each. No new professions, no bolt-on quirks. A quirk at most once per speaker per chapter.
- **Speaker labels are the real names** while writing (`Carter`, `Clara`, ...). brief_gen maps them back to `Host/Guest/Guest2` before `script_final.json` / `{ep}_script.json`, so renders are unchanged. Nobody says their own name.

## 2. Cold open (max ~90 s, about 200-230 words)
- Start **inside a scene**: a concrete case from the notes, an experiment, a bet, or Carter's week. The disagreement erupts within 4 lines.
- Carter's story is set up here. Then Carter names the question in **one** sentence, welcomes listeners, introduces the guests in one short line each, and says once that this is an AI-voiced discussion with fictional characters.
- No "welcome to the show" before the hook, no restated theses, no book titles.

## 3. Chapters: story first, rotating shapes
- Every chapter hinges on **one concrete case** (from the notes, with its source said out loud, or a labelled personal anecdote / hypothetical). The argument grows out of the case.
- At least **3 different shapes** per episode, at most 2 case files:
  - **case_file**: one story told in detail, then picked apart.
  - **hot_seat**: Carter grills one guest; the other heckles and gets one rebuttal.
  - **steelman_swap**: each guest argues the other side for about a minute, then reacts.
  - **rapid_fire**: 5-7 quick yes/no or this-or-that questions, then one longer exchange where they split.
  - **what_would_you_do**: a concrete scenario with a decision and a twist halfway.
- Each chapter ends on a short hook into the next, not a summary.

## 4. Turns
- **Average 25-40 words, hard max 90.** A long thought gets cut into by the others.
- At least a third of turns react directly to the line before. Reactions are **3-10 words** (never a single word: one-word lines are merged away by `clean()`).
- **Carter about 30%** of the words; two guests about 35% each (one guest: about 70%).
- Guests talk to each other in every chapter, not only to Carter.

## 5. Conflict
- The plan names the **crux**: the one point they truly disagree on. It stays **unresolved** at the end.
- Each guest **concedes exactly once**, on a side point (never the crux), with a concrete reason, in a planned chapter, in their own words (bible `concedes_like`).
- Both guests may not end a chapter agreeing.

## 6. Humour
- From character (Lachlan's deadpan, Clara's overselling, Carter's confusion), not inserted jokes.
- **One running gag** per episode (planned keyword): setup, escalation, payoff; **at most 3 uses**.
- **Banned phrases** (bible `banned_phrases`): hit the nail on the head; elephant in the room; intellectually lazy; my view?; spoken like true experts; at the end of the day; double-edged sword; game-changer; good point; you're absolutely right; I'll grant that; I'll concede. They are in the prompt and removed mechanically.

## 7. Facts and sources
- Verbatim quotes only from the verified quote list, **each quote at most once** per episode. **Each statistic at most twice.**
- Name sources the way people say them ("a Stanford study", "Wikipedia's article on ..."); never URLs, file names, page/section/chapter numbers.
- Topic-first episodes are built from web research + optional books (technical v1.13): only facts that pass the relevance gate reach the script.
- Meta lines (episode length, quiz count) come from the brief, not from the model.

## 8. Ending
- Quiz (if on): a **game** with banter; Carter keeps score; 3 questions (20 min) or 4 (30/40 min); one guest gets one wrong.
- **Takeaways are split**: each speaker gives ONE takeaway in their own voice, max 40 words, Carter last. The crux is said to be still open; running-gag payoff; Carter's story payoff; short warm sign-off. No numbered list.

## 9. Delivery tags
- Only `[laughs]` and `[sighs]` (the tags `tools\episode_qc.py` allows), **at most one per turn**, rarely. All other bracketed directions are removed. (The review's wider tag set needs renderer support first: not adopted.)

## 10. Used-material ledger (enforced in brief_gen v1.13)
Before every script part the model gets a ledger: quotes already used, statistics at their cap, gag uses vs budget, phrases already repeated (4-grams used twice), turn length and Carter share so far, banned phrases. After writing, `clean_v25` removes self-address vocatives, near-duplicate lines (similarity >= 0.85), banned phrases, over-cap quotes and statistics, URLs and file names, and extra delivery tags; it logs gag overuse and turns over 90 words.
