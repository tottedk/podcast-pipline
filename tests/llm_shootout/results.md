# LLM shootout - results (aggregate, no model text)

Hardware: RX 7900 XT 20 GB (ROCm via Ollama), Ryzen 5 7600X, 32 GB RAM. ctx 16384, seed 42, keep_alive 20m during tests then 0. Scores 0-5 per task; write/summ/da = 0.5 x automatic checks + 0.5 x Grok Bot's blind rating (NOT Thomas'); json/code fully automatic. Total /25.

| # | Model | Quant | Size GB | GPU % | tok/s write (median all) | TTFT warm / write s | Peak VRAM GB (base) | Hotspot max C | write | summ | json | code | da | Total |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | gemma4:31b-it-qat | QAT int4 (dense 31B) | 18.01 | 92.0 | 4.3 (4.8) | 2.79 / 30.02 | 19.4 (5.5) | 102.0 | 3.5 | 4.75 | 5.0 | 5.0 | 4.6 | **22.85** |
| 2 | qwen3.8:27b-q4_K_M | Q4_K_M (dense 27B) | 16.26 | 100.0 | 4.9 (5.5) | 2.55 / 42.56 | 19.2 (6.5) | 92.0 | 3.5 | 4.5 | 5.0 | 5.0 | 4.75 | **22.75** |
| 3 | muse-glimmer:30b-q4_K_M | Q4_K_M (30B) | 15.4 | 100.0 | 5.3 (5.3) | 3.95 / 296.94 | 19.2 (5.5) | 88.0 | 4.0 | 3.88 | 5.0 | 5.0 | 4.0 | **21.88** |
| 4 | gemma4:26b-a4b-it-qat | QAT int4 (MoE 26B/4B act.) | 14.28 | 100.0 | 23.5 (36.8) | 2.37 / 8.95 | 19.4 (6.5) | 88.0 | 3.25 | 3.75 | 5.0 | 5.0 | 4.5 | **21.5** |
| 5 | qwen3.6:35b-a3b-q4_K_M | Q4_K_M (MoE 35B/3B act.) | 21.91 | 81.9 | 24.5 (27.9) | 2.58 / 13.51 | 19.7 (5.7) | 89.0 | 2.75 | 4.38 | 4.7 | 4.75 | 4.6 | **21.18** |
| 6 | gpt-oss:20b | MXFP4 (MoE 20B/3.6B act.) | 11.99 | 100.0 | 106.4 (117.0) | 2.42 / 3.45 | 18.4 (5.6) | 90.0 | 2.12 | 4.12 | 4.4 | 5.0 | 4.25 | **19.89** |
| 7 | qwen3:14b | Q4_K_M (dense 14B) | 11.02 | 100.0 | 54.4 (62.2) | 2.22 / 5.99 | 17.8 (6.1) | 98.0 | 2.75 | 4.38 | 4.7 | 3.5 | 3.75 | **19.08** |
| 8 | mistral-small3.2:24b | Q4_K_M (dense 24B) | 15.78 | 100.0 | 8.9 (13.3) | 5.4 / 37.84 | 19.1 (5.5) | 90.0 | 3.75 | 3.88 | 3.05 | 3.5 | 3.75 | **17.93** |

json = strict-valid / fully-correct of 10 trials; code = hidden unit tests passed of 20.

- gemma4:31b-it-qat: write words 1065, json strict 10/10 fully correct 10/10, code 20/20, load 23.6 s, unloaded=True
- qwen3.8:27b-q4_K_M: write words 1197, json strict 10/10 fully correct 10/10, code 20/20, load 32.1 s, unloaded=True
- muse-glimmer:30b-q4_K_M: write words 830, json strict 10/10 fully correct 10/10, code 20/20, load 19.1 s, unloaded=True
- gemma4:26b-a4b-it-qat: write words 1158, json strict 10/10 fully correct 10/10, code 20/20, load 27.9 s, unloaded=True
- qwen3.6:35b-a3b-q4_K_M: write words 1281, json strict 10/10 fully correct 9/10, code 19/20, load 23.2 s, unloaded=True
- gpt-oss:20b: write words 1496, json strict 10/10 fully correct 8/10, code 20/20, load 13.6 s, unloaded=True
- qwen3:14b: write words 2067, json strict 10/10 fully correct 9/10, code 14/20, load 9.8 s, unloaded=True
- mistral-small3.2:24b: write words 753, json strict 1/10 fully correct 8/10, code 14/20, load 15.9 s, unloaded=True

## Notes and caveats (read before trusting the numbers)
- **VRAM reality:** the desktop (browser, Steam, Radeon software, dwm) already holds ~5.5-6.7 GB of the 20 GB card (hwmon "base" column), so only ~13-14 GB is really free. Every model larger than ~13 GB therefore filled the card (peak ~19.2-19.7 GB) and Windows spilled the remainder into shared memory, or Ollama offloaded layers to the CPU. That is why the big dense models run at only 4-9 tok/s. gemma4:31b (92% GPU) and qwen3.6:35b (82% GPU) were split by Ollama; the others reported 100% GPU but still hit the memory ceiling. With a freshly booted, empty desktop the 15-18 GB models would be faster.
- **Settings:** ctx 16384, seed 42, temperature 0.8 (write) / 0.5 (da) / 0.3 (summ, json) / 0.2 (code), thinking off (gpt-oss: "low", it cannot be turned off). The script task uses a JSON-schema array output (the pipeline's plain `format: json` made some models return a single turn). One run per model and task, so scores are noisy.
- **Ratings:** write/summ/da are 50% automatic checks and 50% a blind rating by Grok Bot (labels shuffled, key opened after rating). It is NOT Thomas' judgement. Only the blind outputs and my rubric (0-5: accuracy, instruction compliance, fluency, length obedience, human feel) decide those halves; metrics cannot judge how a script sounds.
- **Hotspot:** the card reaches 88-102 C hotspot at ~300 W during prompt processing; gpt-oss hit 100 C in a first attempt (aborted by my 100 C guard, re-run with a 104 C guard).
- Full model outputs stay local (tests/llm_shootout/results/<model>/, gitignored).
