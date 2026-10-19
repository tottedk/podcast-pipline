# Content & style template
**Version 2.4 - 2026-10-19** (v2.3 + new format 'moderated debate (politics series)': no fixed chapters, host as moderator with an evolving question set, randomised human guest traits, uncensored tone). Never edit; copy to v2.5 for changes.

## Why 2.0
v1.0 episodes felt like a re-reading of the book with a few critiques added, and the tone was cold. 2.0 makes each episode a **real argument between two guests**, with a warm, funny host who mediates and gives his own view.

## Purpose and audience
Same as 1.0: Thomas's private study podcast, ~40-45 min, for an educated non-specialist. But the core is now **a conflict of views about the book**, not a guided tour of it.

## Sources
Same as 1.0: books in `C:\grok\books\`, **read once** into `notes\<book>.md` (now also with a section of the **antagonist's** arguments and sources), script built from the note. 1-2 episodes per book.

## Voices (3)
- **Host: Carter** (always). **Average Joe on the outside, sharp mind on the inside.** Relaxed, self-ironic, humorous; uses everyday examples (Netflix, the gym, LinkedIn, the commute, the work canteen). **Mediator:** keeps the argument on track, summarises the disagreement in plain words, stops a runaway argument. **Gives his own view regularly** (about every 3-5 min), sometimes sides with one guest, and now and then asks the one sharp question that cuts through both.
- **Guest A: the advocate.** Knows the book inside out and defends its strongest version.
- **Guest B: the antagonist.** Speaks from a named critical tradition (e.g. das Man: Adorno, *Jargon of Authenticity*, or a modern tech/liberal optimist). Attacks the book's premises, not just details.
- Both guests are random from **Frank / Alice / Maya / Samuel** (two different voices; never Mary). Assign the advocate/antagonist roles at random and keep them for the whole episode or series.

## Discussion format
- **Built around disputed questions**, not chapters. Example for das Man: "Is the crowd really the enemy, or is that just elitism?"; "Is burnout a philosophical problem or just a bad boss?"
- Each chapter = one question: a short framing by Carter -> the advocate's case -> the antagonist's attack -> real back-and-forth -> Carter's own view / verdict.
- **Heated is allowed:** interruptions, irritation, sarcasm and scored points are fine. It adds humanity.
- **But fair:** each guest must **concede a real point at least once** in the episode; no straw men; no personal insults; Carter steps in if it turns into a shouting match.
- Humour comes mainly from Carter (dry, self-ironic, everyday comparisons), occasionally from the guests' clashes. Never at the expense of accuracy.
- **Cut the summaries:** the book's content comes out through the argument, not through separate recap sections.

## Script rules
- Cold open (~1-2 min): ideally a live clash between the guests, then Carter's welcome.
- **7-10 chapters** with real titles (phrased as questions or conflicts where it fits) -> **5-point takeaways**, where Carter gives the final word and each guest gets one closing line -> short wrap-up.
- Named real critics woven in (the antagonist carries most of them, but the advocate also cites defenders).
- **No invented quotes**; direct quotes only from the note with their location. The **fact-check covers both sides**' claims.
- Filler filter as in 1.0. **Few one-word interjections**, but short interruptions ("No, wait-", "Hold on.") are allowed in heated passages; merge them into full lines where possible (TTS).
- Speaking-time balance: roughly Carter 30%, each guest 35%.
- **HARD length 40-45 min** = 6,000-6,400 words. **Fact-check before rendering.**

## Vibe / tone
**Warm, lively, human**: like three smart friends who really disagree, at a kitchen table after dinner. Curious and funny, sometimes heated, never cold or lecturing. Still serious about the ideas.

## Music, visual style, video layout, learning materials, outputs
Same as 1.0, except: the **speaker indicator now has three colours** (host amber, guest A blue, guest B red/crimson), and the **subtitles are a separate `.srt` only**, not burned in. Technical production is owned by **Tech Lab** (see technical templates).

## Principle
Improve from episode to episode; no re-renders. 1.0 stays available as the single-guest format.

## First episode with 2.0
**"das Man"**: Heidegger, *Being and Time* §§25-27 and §§35-38, plus Byung-Chul Han, *The Burnout Society*. The advocate defends Heidegger and Han; the antagonist uses Adorno's *Jargon of Authenticity* and/or the modern tech/liberal optimist. **Before production, Tech Lab must test that VibeVoice handles 3 voices well.**

## Changes in v2.1 (2026-10-15, from Thomas's feedback; v2.0 stays unedited)
1. **Book references.** Carter names only the book and the author. Never exact sections, chapters, translators or editions in the spoken script. All of that goes into a separate file `learn\<episode>_details_meta.md`, which is the YouTube description: sources, editions, chapters with timestamp placeholders, further reading, a content warning if needed, and the CC BY attribution for any CC BY voices (see `voices_extra\LICENSES.md`).
2. **No stock concessions.** Guests must not use "I'll concede that one", "I'll grant that" or similar formulas. Concessions are human and varied: hesitation, irritation at being right, laughter, a half-concession, a change of tone, silence. Each guest still concedes a real point at least once.
3. **Passion.** Guests are visibly passionate about their field, with room for real emotion and anger, and with a genuine faith or commitment where the character calls for it. The episode still stays fair: the counter-guest gets strong arguments.
4. **Carter** is an average Joe outside, sharp inside, humorous, a mediator who gives his own verdict, about 30% of speaking time.
5. **No glossary respellings.** Write terms normally; do not touch `glossary.json`.
6. **Content sensitivity.** For books with hateful or violent content: describe analytically, no slurs, no gratuitous detail, a short content note at the start, and a content warning in the details meta file.

## v2.2 additions (Thomas, 15 Oct 2026)
**Problem:** the conversation comes out serial and sequential: one speaks, the next answers, then Carter moves on. It needs to feel like real people.
- **Branching and tangents:** an idea from one guest may pull the talk down a new, fun path. Allow 1-2 short tangents per chapter (a story, an everyday comparison, a side question) before Carter steers back.
- **Live reactions:** the other speakers react while someone is talking: laughing, groaning, short interruptions ('Wait, what?', 'No, no, no-', 'Oh, come on'), finishing each other's sentences, callbacks to something said earlier. Write them as part of full lines or as interruptions inside the line, not as isolated one-word lines (TTS).
- **Not strictly turn-by-turn:** vary the rhythm. Sometimes three quick short lines, sometimes one long passionate speech that others cut into. Guests may address each other directly without waiting for Carter. Avoid the pattern 'Host asks, Guest A answers, Guest B answers, Host summarises' repeating in every chapter.
- **Cross-talk and callbacks:** reuse running jokes and earlier points across chapters. One guest's remark can change the other's argument mid-episode.
- **Humour:** more of it. Carter drops a **bad dad joke** every chapter or two (and the guests groan or roast him), plus dry self-irony. The guests can be funny too, but never at the expense of accuracy or when talking about victims or suffering.
- **Keep:** the 40-45 min length, fairness, fact-check, the varied human concessions and the emotions from v2.1.

## v2.3 changes (Thomas, 16 Oct 2026) - these override conflicting v2.2 rules
- **Drop the scheduled dad jokes.** No joke quota. Humour is welcome but must arise naturally from the conversation (a slip, an absurd comparison, teasing, irony). A dad joke is allowed only if it truly fits the moment.
- **Less rigid, less tied to the source.** The script follows the source material too closely. The guests are experts who draw on a deeper pool than the books they were given: other authors, history, examples, cases, personal experience. The source material is the starting point, not the script. Never invent quotes or false facts (no made-up citations); use only well-known, verifiable material for the extra knowledge, and fact-check it.
- **Wander on purpose to keep the audience awake.** Mix the topic with everyday life (food, work, family, small stories), literature and other fields, and with the expertise itself. Vary the register in every chapter so the listener never drifts or falls asleep. Tangents may run longer than in v2.2 before Carter steers back.
- **More emotion from everyone.** Guests (and Carter) may get angry, laugh, be hurt, sarcastic, moved, embarrassed or impatient in response to what is said. Allow an odd, rare chance of a guest storming off, hanging up, or refusing to continue a line of argument (they may come back later, e.g. after a break or a callback).
- **More conflict between the guests, less nodding.** The three must not constantly agree. Guests really disagree, interrupt, call each other out and stay unconvinced; not every point ends in a reconciliation or a concession. Carter should also disagree sometimes rather than just mediate. Avoid 'you're right' / 'good point' reflexes; let disagreements remain unresolved when it is natural.
- **Keep:** 40-45 min, fairness and fact-check, human varied concessions only when they truly happen, only book and author named, details in the meta file, no respellings.

## v2.4 additions (Thomas, 19 Oct 2026) - format: moderated debate (politics series)
**Applies to the politics series** (working name **"Fault Lines"**, episodes numbered `#1`, `#2`, ...; file stem `faultlines_NN`). All other formats keep v2.3 unchanged. Where this section conflicts with v2.0-v2.3, **this section wins for the politics series**.

### Concept
Each episode mixes three layers: **(a) classic political theory** (Schmitt, Mouffe, Burke, Marx, Mill, Hobbes, Tocqueville, Rousseau, Madison, ...), **(b) real-world practice** (research, data, cases, Denmark/Nordics/Europe/US), and **(c) one object of focus**: a concrete event, document or artifact that anchors the episode and that the conversation keeps returning to. Research + upload list per episode in `notes\faultlines_NN_research.md`.

### No fixed chapters
- **No chapters, no chapter titles, no 'Chapter five' lines.** The conversation unfolds naturally. Carter moderates; he never announces structure beyond the opening and the takeaways.
- **Carter's question set:** before writing, prepare 8-12 questions in `notes\faultlines_NN_questions.md`. In the script he uses roughly 6-9 of them, in any order. **At least 2-3 questions must evolve unexpectedly** from a guest outburst, slip, bias or personal story (Carter drops his plan and follows it). Mark used / dropped / evolved questions in the questions file afterwards.
- Fixed only: **cold open** (a live clash, 1-2 min) -> Carter's welcome + the object of focus -> free conversation -> **5 takeaways** (Carter's final word; each guest one closing line, which may be bitter, unreconciled or a parting shot) -> short wrap-up.

### Guests
- **Two guests, from opposite poles** (episode 1: far right vs far left). Both are **fictional** characters (voice names from the pool + an invented surname and bio); never impersonate a real person.
- **Experts in their fields** (credentials, a real body of knowledge, real authors and cases they know well), and **very human**: emotions show from time to time (anger, hurt, laughter, contempt, embarrassment, being moved).
- **Randomised traits:** run `python pick_traits.py --cast <Dir>\cast.json --sides Guest=right,Guest2=left --out <Dir>\cast_traits.json` after `pick_cast.py`. Library: `templates\guest_traits_v1.json` (quirks, debate tactics, emotional triggers/displays, blind spots, backstory hooks; seeds in `guest_traits_seed_v1.json`, expanded with `tools\expand_traits.py`). Default per guest: 1-2 quirks, 2 tactics, 1-2 emotional, 1 blind spot, 1 backstory hook; seeded, no contradictory combos, the two guests never share a trait. Paste `prompt_block` into the script prompt. **Show the traits, never announce them**; let them surface 2-4 times each, not every line.
- Traits may include unfair moves (**strawmanning, whataboutism, going personal**). These are allowed here: the other guest or Carter may catch them, or they may slip through. The v2.0 rules "no straw men / no personal insults / each guest must concede once" **do not apply** to this format. A concession happens only if it truly would.

### Host: Carter (fixed personality, NO random traits)
Carter is never given traits from the library. His personality is the one Thomas defined (content_style v2.0/v2.1): **"Average Joe on the outside, sharp mind on the inside."** Relaxed, self-ironic, humorous; everyday examples (Netflix, the gym, LinkedIn, the commute, the work canteen). Mediator who keeps the argument on track, summarises the disagreement in plain words, stops a runaway argument, **gives his own view regularly** and now and then asks the one sharp question that cuts through both. In this format: he is a **moderator, not a referee** - **no 'both-sides' smoothing**, no "you both make good points"; he pushes the guest who dodges, calls out a dodge or a bias by name, and can be annoyed, amused or shaken himself. Speaking time ~25-30%.

### Tone: unhinged / uncensored
- Raw, heated, rude, sincere. **Real ideological conviction** on both sides, stated in the guest's own voice and at full strength. Swearing, contempt, mockery between the guests, interruptions, walk-out attempts (rare, see the trait library), unresolved fights and nobody winning are all allowed.
- **End goal: show the guests and the host as humans** (unless Thomas instructs otherwise): the person behind the ideology - fear, pride, family, wounds, humour.
- **Sensible guardrails only:** (1) guests are fictional; (2) **no invented quotes** attributed to real people; direct quotes only from notes with their location; (3) real-world facts and statistics are **sourced in the notes or clearly framed as the guest's own claim** ("the way I read the numbers..."); a guest may be wrong, but then the other guest or Carter challenges it, or it is flagged in the details meta file; (4) the v2.1 content-sensitivity rule still applies (no slurs against groups, no calls to violence against real people, no operational detail); the details meta file carries a content warning for strong language and extreme views.

### Chapters / video without script chapters
The script has no chapters, but YouTube/MP4 chapters still work: **after the script is final and after `prep_script.py` merging**, the writer derives `<Ep>.chapters.in.json` (`{"title", "sections":[{"start": <line index>, "title"}]}`, same format as before) from the **actual topic shifts** in the finished conversation: 6-10 sections, first at line 0 ("Cold open"), roughly >= 3 min apart, titles describing the fight at that point (e.g. "Is it already a war?"). The titles are **never spoken**. `make_video.py`/`post_episode.ps1` are unchanged and use the file as before (corner label + `.chapters.txt` + MP4 chapter metadata).

### Unchanged from v2.3 (keep)
40-45 min (~6,200 words at drama3 tempo 1.05), cold open, 5 takeaways at the end, speaker labels **Host / Guest / Guest2**, no invented quotes, fact-check both sides, only book + author named aloud, details in `learn\<episode>_details_meta.md`, separate `.srt` (not burned in), no glossary respellings, natural humour, tangents into everyday life, live reactions and cross-talk as in v2.2/v2.3.

### Cast rule reminder
Host **Carter**. Guests via `pick_cast.py` from Clara, Isla, Marcus, Willa, Zara, Imogen, Elliot, Lachlan, Frank (low weight; F0 clashes with Carter), Samuel (weight 0.25); Hugh not with Carter (F0 gap); **never Maya, Declan, Alice, Mary**.
