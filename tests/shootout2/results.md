# shootout2 (2026-10-14 19:00-19:20) - das Man seg02 lines 0-8 (443 words, 9 lines), Carter/Frank/Samuel, no glossary
All three: seed 42 take passed (WER<5%, no hallucination) -> no retry; shipped seed 42.
| | VV-1.5B (podcast.ps1 -NoQc, 450w chunk) | SoulX-1.7B (+0.3 s gaps) | VV-7B Q8 audio.cpp Vulkan |
|---|---|---|---|
| WER | 3.38% | 1.58% | 1.58% |
| align | 96.8% | 98.9% | 98.6% |
| noise / pitch ev / lowprob | 7/0/0 | 16/0/0 | 10/0/1 |
| QC score / flags | 31.9 f0_drift | 62.6 noise,f0_drift,rate | 36.6 f0_drift |
| Carter med F0 (ref 131) | 162.6 | 134.2 | 142.4 |
| Frank med F0 (ref 127.5 gen / 115.9 prompt) | 128.7 | 130.8 | 117.2 |
| Samuel med F0 (prompt 101.3) | 114.3 | 118.5 | 132.2 |
| spk mix-ups | 0 | 0 | 0 |
| raw audio | 156.2 s | 185.2 s (182.8 speech) | 164.4 s |
| gen time | 127.5 s | 263.8 s | 73.0 s |
| RTF | 0.82 | 1.44 | 0.44 |
| VRAM | 6.78 GB torch (adapter +7.6) | 6.83 GB torch (adapter +8.8) | adapter +12.0 GB |
Files: ab\1_vv15_s42.mp3, ab\2_soulx_s42.mp3, ab\3_vv7b_s42.mp3, ab\lineup_vv15_soulx_vv7b.mp3 (lines 2-3, Frank Heidegger/Dasein + Samuel)
