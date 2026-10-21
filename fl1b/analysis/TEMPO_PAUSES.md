# Fault Lines #1 (v1.11 re-render) - tempo, pauses, monotony

Analysis only, 2026-10-21. Nothing re-rendered, no code changed. Final mp3 `episodes\faultlines_01.mp3` is the same file as `fl1b\faultlines_01.mp3` (41,496,284 bytes, 2593.4 s).
Data: `faultlines_01.timings.json` (whisper large-v3-turbo word times, 97.4 % matched), an energy envelope of the final mp3 (10 ms frames; a silence is a run of frames more than 30 dB below the line's speech level), librosa pyin (venv_vv, 16 kHz, 55-500 Hz), and the per-chunk `chunks.json` / `c*.wav` raw Drama 3 audio.
Scripts and outputs are in this folder: `ana.py`, `chk.py`, `metrics.json` (every line), `ana_out.txt`, `chk_out.txt`, `code.txt`.

## 1. Per-speaker pace and pauses (final mp3, pauses inside lines only)

| Speaker | lines | words | speech s | wpm incl. pauses | wpm excl. pauses >0.5 s | articulation wpm (excl. >=0.25 s) | pauses >0.5 s (n / s) | pauses >1.0 s (n / s) | >0.5 s per 100 words |
|---|---|---|---|---|---|---|---|---|---|
| Carter (host) | 59 | 2304 | 834.6 | **165.6** | 181.0 | 190.9 | 105 / 71.0 | **0 / 0** | 4.6 |
| Elliot (guest) | 50 | 1865 | 825.1 | **135.6** | 160.8 | 170.0 | 123 / 129.2 | **50 / 77.9** | 6.6 |
| Clara (guest2) | 53 | 2012 | 825.0 | **146.3** | 153.8 | 163.1 | 60 / 40.1 | **1 / 1.1** | 3.0 |

Speech time = first word to last word of each line. Pause-length histogram (internal, s): Carter 0.5-0.7: 72, 0.7-1.0: 37, >1.0: 0. Elliot 0.5-0.7: 42, 0.7-1.0: 35, 1.0-1.5: 36, **>1.5: 15**. Clara 0.5-0.7: 44, 0.7-1.0: 21, >1.0: 1.
The whisper word gaps agree: gaps >1.0 s are Carter 2, Elliot 37, Clara 0.
Target was about 155 wpm. Only Carter is above it. Clara is about 9 wpm under, and Elliot is about 20 wpm under, with his pauses making most of that gap.

### Elliot's 10 slowest lines (lines with >= 10 words; line = 0-based index in timings/mixqc)

| mm:ss | line | words | span s | wpm | wpm excl. >0.5 s | longest internal pause | text |
|---|---|---|---|---|---|---|---|
| 38:44 | 143 | 11 | 10.1 | 65 | 83 | 1.33 s @ 38:52 | [sighs] That's... I'm sorry, Clara. I mean it. |
| 17:34 | 63 | 16 | 11.9 | 81 | 129 | 3.04 s @ 17:36 | I'm the danger. Marvellous. I've been called worse... |
| 14:28 | 51 | 11 | 7.6 | 87 | 102 | 1.14 s @ 14:32 | [sighs] Sick. I felt sick. I said so at the time... |
| 07:28 | 26 | 20 | 10.9 | 110 | 126 | 0.75 s @ 07:31 | [sighs] My side grieved. Genuinely... |
| 39:05 | 148 | 57 | 30.3 | 113 | 153 | 1.20 s @ 39:33 | My brother. Younger brother. He lives in Aarhus... |
| 00:22 | 1 | 31 | 16.3 | 114 | 135 | 0.68 s @ 00:35 | Oh, come on. Teachers, firefighters, soldiers... |
| 36:25 | 132 | 29 | 15.0 | 116 | 144 | 1.76 s @ 36:28 | That's a fair hit, and I don't like it... |
| 01:57 | 7 | 14 | 7.2 | 116 | 146 | 0.93 s @ 01:59 | Thank you, Carter. For the record, nobody reads enough Schmitt... |
| 28:09 | 103 | 47 | 24.0 | 118 | 144 | 2.39 s @ 28:23 | It means I'm tired, Carter... |
| 27:08 | 96 | 23 | 11.7 | 118 | 129 | 0.99 s @ 27:12 | [laughs] Oh, now numbers are allowed?... |

Elliot's longest dead-air pauses inside a line: 13:37 3.8 s, 13:28 3.6 s, 13:06 2.7 s, 13:11 1.7 s (all line 47, which has 8 pauses >0.5 s), 26:06 3.3 s and 26:18 3.1 s (line 93), 17:36 3.0 s (63), 15:38 2.5 s (57), 28:23 2.4 s (103), 31:47 2.3 s (114), 32:52 2.0 s (117), 36:28 1.8 s (132).
Carter's longest internal pause is 0.96 s, and Clara's is 1.13 s.
qc_mix had already flagged this. All 9 `SILENCE` flags and all 4 `RATE` flags in mixqc.txt are Elliot lines (47, 51, 57, 63, 93, 103, 114, 143, 148), but `MIXQC ISSUES` does not block.
Three of the four slowest lines begin with `[sighs]`. Elliot has 8 tags (`[sighs]`, `[laughs]`, `[whispers]`), Carter has 3 and Clara has 4.

## 2. Pitch variation (monotony), pyin on the final mp3

| Speaker | F0 median | F0 std (semitones) | P5-P95 range (st) | mean within-line std (st) |
|---|---|---|---|---|
| Carter | 130.8 Hz | **4.26** | 14.0 | 4.20 |
| Elliot | 115.2 Hz | **2.92** | 8.4 | 2.59 |
| Clara | 217.5 Hz | **3.33** | 10.8 | 3.20 |

This confirms Thomas's impression. Elliot is the flattest of the three: his pitch spread is about 30 % smaller than Carter's (std), and his within-line variation is 2.6 st against Carter's 4.2 st.

## 3. Root cause

1. **The tempo is one global value, applied after generation as a time-stretch.** `run_episode.ps1:10` sets drama3 to 0.90. It goes to `render_drama3.ps1 -Tempo 0.90` (line 14) and then to `post_segment.ps1` (line 89), which puts `atempo=0.9` (line 34) into the ffmpeg chain for the whole segment. That stretches speech and every pause alike by 1/0.9 = x1.11. The setting is per engine, not per speaker. It was calibrated on the episode-wide raw average of 172 wpm (`drama3_generate.py` `expect_s`), which hides very different speakers. Check: tests\tempo_compare is 35.5 s at 0.90 vs 30.5 s at 1.05, a ratio of 1.164, which equals 1.05/0.90. So it is a purely linear stretch.
2. **Drama 3 natively speaks slower in Elliot's voice.** Raw Drama 3 chunks before atempo: Carter 186 wpm, **Elliot 150 wpm**, Clara 164 wpm. Times 0.90, that gives 167 / **135** / 148, which matches the final mp3. The slowness is in the clone, not the post chain.
3. **Elliot's reference clip is the cause.** `drama3_refs\Elliot.wav` is 18.9 s of speech with only **32 words, about 102 wpm** (Carter's reference is 189 wpm, Clara's 170 wpm). It is four unrelated read-aloud corpus sentences ("A copy of the report will be sent to them / It makes no influence on the public / ..."). The transcript has no punctuation, the delivery is flat newsreader prosody with pauses between sentences, and the noise floor is high. Drama 3 clones pace, pausing and prosody from the reference, so Elliot comes out slow, pause-heavy and flat. Note: pyin's F0 numbers on that reference clip (median 66 Hz) look like creak or octave errors, so I did not use them.
4. **The pause clamp never fires for Elliot.** `drama3_generate.py clamp()` (lines 102-123) works per chunk, which in turn mode means on one speaker's consecutive lines. So it does act inside lines. It shortens any internal run of frames below *chunk speech median - 32 dB* that lasts more than `--max_pause 0.9 s` down to `--keep_pause 0.6 s`. Between chunks, a fixed 0.35 s gap is inserted (`--pause`). Because atempo runs afterwards, the final values become threshold 1.0 s, kept pause 0.67 s and gap 0.39 s, and pauses of 0.5-0.9 s raw (0.55-1.0 s final) are never touched. The problem is Elliot's raw noise floor, which sits only about **37 dB** below his speech (Carter about 60 dB, Clara about 47 dB). His pauses therefore never drop below speech - 32 dB. Raw pauses of 0.9 s or more found below speech - 32 dB: Carter 0, Elliot 0, Clara 0. Found below speech - 20 dB: Carter 1, **Elliot 69**, Clara 1. Only 8 Elliot clamps happened at all. Later, the qc_vv `--gate` pause gate in post_segment mutes that noise, so these pauses ship as long digital silences of 1-3.8 s. That is the "pauses where Elliot speaks".

## 4. Fixes for the next episode (not applied; simulated on this episode's measured data)

Simulated wpm from re-timing each line: tempo t scales by 0.9/t, and pauses longer than the cap are cut to the cap (in final-mp3 time).

| Speaker | now (t 0.90) | t 0.90 + cap 0.45 s | t 0.95 + cap 0.45 | t 1.00 + cap 0.6 | t 1.00 + cap 0.45 |
|---|---|---|---|---|---|
| Carter | 165.6 | 170.6 | 179.4 | 185.1 | 188.2 |
| Elliot | 135.6 | 149.1 | 156.6 | 160.4 | 164.2 |
| Clara | 146.3 | 148.8 | 156.7 | 163.3 | 164.6 |

Recommended, in order:
1. **Fix the clamp detection (biggest effect on the pauses).** Measure silence against the chunk's noise floor rather than speech - 32 dB. For example, silence = frames below max(speech - 32, floor + 8 dB), or simply speech - 20 dB, which found all 69 of Elliot's long pauses and only 1 each for Carter and Clara. Also tighten the cap: `--max_pause 0.6 --keep_pause 0.4` raw (0.67 / 0.44 s final). Expected: Elliot's pauses over 1.0 s go from 50 to 0, and Elliot rises from 136 to about 146-149 wpm at the unchanged 0.90.
2. **Per-speaker tempo** (needs a `-TempoBySpeaker Host=..,Guest=..,Guest2=..` option, because atempo now runs on whole mixed segments). One way: apply atempo per chunk in drama3_generate.py (every chunk has one speaker) and run post_segment at tempo 1. With the clamp fix, suggested values are **Elliot 1.00 (about 160-164 wpm), Clara 0.95 (about 157), Carter 0.90 (about 171)**. Estimated mix about 2593 - 222 s = **about 2371 s (39.5 min)**, still inside the 38-48 min gate. If Thomas wants it brisker overall, Carter 0.95 gives about 179 wpm and about -40 s more.
3. **Replace Elliot's Drama 3 reference** (root fix for pace and monotony). Use one continuous ~20 s conversational or argumentative clip at about 160-185 wpm, with lively intonation, a clean floor (better than -50 dB) and a punctuated transcript, instead of four stitched read sentences. Or re-cut the current source with `drama3_refs.py --max_s` onto a livelier stretch. Expected: raw Elliot pace near Carter and Clara (165-185 wpm), so the per-speaker tempo matters less, plus more F0 variation. Test with a 3-4 line A/B of Elliot (as in tests\tempo_compare) and measure wpm and F0 std. The target is Elliot F0 std at least 3.3 st, like Clara.
4. **Tags/script:** do not start Elliot lines with `[sighs]`. Three of his four slowest lines do, each costing about 1 s of sigh plus a pause. Elliot also has only 9 questions against Carter's 35. Shorter, more interjective sentences give more contour.
5. **Make QC block on this:** add a per-speaker gate in qc_mix (each speaker 145-175 wpm, no internal silence over 1.5 s) so a run like this one stops for Thomas instead of passing with "MIXQC ISSUES".

## 5. Episode index not updated (tools\start_faultlines_01b.ps1:55)

Cause: `episodes_index.py` ends with a bare `main()` and no `if __name__ == "__main__":` guard. So the inline `python -c "...import episodes_index as E..."` runs argparse on import, sees no subcommand and exits with `the following arguments are required: cmd`. The update was never applied.
State now: entry **#11 faultlines_01 exists** but still holds the rejected v1.10 values (`duration_s` 2116.8 = 35:17, date 2026-10-20, no note).
`add` does **not** fix this. The equivalent subcommand call would be
`C:\grok\podcast\venv_vv\Scripts\python.exe C:\grok\podcast\episodes_index.py add --ep faultlines_01 --series "Fault Lines" --multi --title "Left vs Right: Is It Becoming a War?" --dur 2593.4 --cast "Carter, Elliot, Clara"`
but for an already-registered ep, `plan()` returns a note and `add` only prints `registry: already registered faultlines_01` and writes nothing. post.log shows exactly that.
The call that performs the intended update (same code as line 55, made import-safe by giving argparse the harmless `show` subcommand; it prints the index table first). Not run:

```
C:\grok\podcast\venv_vv\Scripts\python.exe -c "import sys;sys.argv=['episodes_index.py','show'];sys.path.insert(0,r'C:\grok\podcast');import episodes_index as E;p=r'C:\grok\podcast\episodes_index.json';ix=E.load(p);e=[x for x in ix['episodes'] if x['ep']=='faultlines_01'][0];e['duration_s']=2593.4378;e['date']='2026-10-21';e['note']='re-render v1.11 (v1.10 render rejected, moved to episodes/_rejected/faultlines_01_v110)';E.write(ix,p,p[:-5]+'.md');print('registry updated',e['number'],e['duration_s'])"
```
A durable fix for future wrappers is to add the `__main__` guard to episodes_index.py, or an `update --ep --dur --date --note` subcommand.
