"""prep_script.py script.json [out.json] [--min_words 2] - merge short interjection lines (<= min_words words, e.g. 'Right.', 'Yes.')
into the SAME speaker's next line as a lead-in, so VibeVoice never renders a stand-alone one-word line after a turn change
(the most artifact-prone case). Writes out.json (default: overwrite, backup <script>.pre_merge.json). The merged file is used
for TTS AND align/video, so subtitles stay consistent. Prints what was merged."""
import sys, json, shutil
args = [x for x in sys.argv[1:] if not x.startswith("--")]; mw = 2
if "--min_words" in sys.argv: mw = int(sys.argv[sys.argv.index("--min_words")+1])
src = args[0]; out = args[1] if len(args) > 1 else src
L = json.load(open(src, encoding="utf-8-sig")); res = []; carry = {}; n = 0
for l in L:
    t = l["text"].strip(); sp = l["speaker"]
    if len(t.split()) <= mw and len(L) > 1:
        carry[sp] = (carry.get(sp, "") + " " + t).strip(); n += 1; print("merge:", sp, repr(t)); continue
    if carry.get(sp): t = carry.pop(sp) + " " + t
    res.append({"speaker": sp, "text": t})
for sp, t in carry.items():   # leftover at the end: append to that speaker's last line
    prev = [r for r in res if r["speaker"] == sp]
    if prev: prev[-1]["text"] += " " + t
    else: res.append({"speaker": sp, "text": t})
if out == src: shutil.copy(src, src[:-5] + ".pre_merge.json")
json.dump(res, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(f"{len(L)} -> {len(res)} lines, {n} short lines merged -> {out}")
# NOTE: merging changes line indices -> run it BEFORE writing chapters.in.json / backgrounds.json.
