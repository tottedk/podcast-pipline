# Content & style template
**Version 1.0 - 2026-10-14** (state as used for *The Dark Enlightenment* ep1). Never edit; copy to v1.1 for changes.

## Purpose and audience
Thomas's private study podcast: one demanding book of philosophy or political theory turned into a ~40-45 min critical conversation. The listener is an educated non-specialist who wants the argument, its context and its strongest critics, not a summary or a fan piece.

## Sources
- Books in `C:\grok\books\` (EPUB/PDF), mostly philosophy / political theory (Land, Moldbug/Patchwork, Heidegger next).
- **Read once** -> structured note `notes\<book>.md`: structure table (part/chapter, date or page, core), key points by theme, short quotes with locations (Part+date where an EPUB has no pages), critics section with full references. **The script is built from the note only.**
- **1-2 episodes per book**, critics included in the same episodes (no separate "critics episode").

## Voices
- **Host: Carter** (always). Active, sceptical, pushes back, asks for evidence, states his own objections; not a cheerleader.
- **Guest: random from Frank / Alice / Maya / Samuel.** Never **Mary** (her reference has background music). Keep the guest once chosen for an episode (and for multi-episode books if already chosen).

## Script rules
- **Thematic structure**, not a linear walk through the book.
- **Cold open** (~1-2 min hook) -> **7-10 chapters** with real titles -> **5-point takeaways** at the end -> short wrap-up.
- **Named real critics woven in** where relevant (e.g. DE: Elizabeth Sandifer *Neoreaction a Basilisk*; Scott Alexander *Anti-Reactionary FAQ*; Benjamin Noys *Malign Velocities*; also Hirschman, Saini, Slobodian, Beckett).
- **No invented quotes.** Paraphrase by default; a direct quote only if it is in the note with its location. Cited works must exist (verify).
- **Filler filter:** no "great question", "absolutely", "fascinating", "that's so interesting", no throat-clearing. **Few one-word interjections** (they are also TTS failure points).
- **HARD length 40-45 min final** = 6,000-6,400 words at ~150 wpm (after atempo 0.93). Check the word count before rendering.
- **Fact-check before rendering**: every claim against note/source -> `learn\factcheck_<ep>.md` (table: claim | source | status, with FIXED/REMOVED entries). Fix the script, then render.

## Vibe / tone
Serious, curious, unhurried, slightly noir; respectful of the text's power while being clearly critical of its weak points (e.g. race material in DE). No moralising lectures, no sensationalism.

## Music
Deliberate, self-made (synth.py, numpy synthesis: drone + plucks): **intro** (~18 s), short **stings** between sections (~7 s, volume 0.35), **outro** (~28 s). No stock music.

## Visual style (backgrounds)
- ~20 images per episode (~1 per chapter, 2-3 for long chapters), FLUX.1 schnell.
- Style text (FLUX style C, strengthened): `cyber-gothic cinematic concept art, semi-realistic, visible brush strokes, rich warm amber glow against teal shadows, moody volumetric light, wide low-angle cinematic shot, film grain, no text`
- Composition: **one subject in the lower third, empty space above** (room for overlays). The word **'dark' at most once** per prompt (style + prompt). No real faces or text.

## Video layout
- Speaker indicator: **name + pulsing waveform** (host amber, guest blue); **chapter title in a corner**; title card + chapter cards; Ken Burns backgrounds with crossfades.
- **NO big centre quotes** (old layout kept as `--layout quote` / backups).
- **Subtitles: from the next episode a separate `.srt` only, not burned in.** (DE ep1 still had burned-in + soft track.)
- 2-3 frame screenshots per episode for review.

## Learning materials (`learn\`)
`<ep>_takeaways.md`, `<ep>_quiz.md`, `<ep>_anki.csv` (front;back), `<ep>_read_for_yourself.md` (further reading), `factcheck_<ep>.md`; optional `<ep>_summary.pdf` (made for Fanged/Patchwork, not for DE ep1).

## Outputs
`episodes\<book>_epN.mp3 / .mp4 / .srt / .chapters.txt (+ .chapters.json, _64k.mp3 mono <25 MB)`.

## Principle
**Improve from episode to episode; no re-renders** of finished episodes. Bugs found go into the next version of these templates.

## Episode log
| Episode | Book | Length | Guest |
|---|---|---|---|
| Fanged Noumena ep1 | Land, *Fanged Noumena* | 42.6 min | unknown (not recorded) |
| Fanged Noumena ep2 | Land, *Fanged Noumena* | 43.4 min | unknown (not recorded) |
| Fanged Noumena ep3 | Land, *Fanged Noumena* | 43.2 min | Alice |
| Patchwork ep1 | Moldbug, *Patchwork* | 47.8 min (over the limit) | Samuel |
| Dark Enlightenment ep1 | Land, *The Dark Enlightenment* | 41.9 min, 6,024 words | Frank |

## Planned next episode
**"das Man"**: Heidegger, *Being and Time* §§25-27 (the "they", everydayness) and §§35-38 (idle talk, curiosity, ambiguity, falling), plus Byung-Chul Han, *The Burnout Society*. Antagonist voice: Adorno, *The Jargon of Authenticity* (woven in as named critic). Guest: random from Frank/Alice/Maya/Samuel.