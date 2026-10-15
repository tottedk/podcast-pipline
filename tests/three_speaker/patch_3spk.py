import sys, io, os
R = r"C:\grok\podcast"
def patch(fn, reps):
    p = os.path.join(R, fn); s = open(p, encoding="utf-8").read()
    for a, b in reps:
        n = s.count(a)
        if n == 0: sys.exit(f"{fn}: NOT FOUND: {a[:70]!r}")
        s = s.replace(a, b)
    open(p, "w", encoding="utf-8", newline="").write(s); print("patched", fn)

patch("vv_generate.py", [
 ('ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default="Frank")',
  'ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default="Frank")\nap.add_argument("--guest2", default="", help="voice for speaker \'Guest2\' (3-speaker scripts; v1.2)")'),
 ('vh, vg = V[a.host.lower()], V[a.guest.lower()]\nif a.clean_refs: vh, vg = cleaned(vh), cleaned(vg)',
  'vh, vg = V[a.host.lower()], V[a.guest.lower()]\nvg2 = V[a.guest2.lower()] if a.guest2 else None\nif a.clean_refs: vh, vg = cleaned(vh), cleaned(vg); vg2 = cleaned(vg2) if vg2 else None\nVMAP = {"Host": vh, "Guest": vg, "Guest2": vg2}; ORDER = {"Host": 0, "Guest": 1, "Guest2": 2}\nif any(l["speaker"] == "Guest2" for l in lines) and not vg2: sys.exit("script has Guest2 lines: pass --guest2 <voice>")'),
 ('Guest={os.path.basename(vg)} cfg', 'Guest={os.path.basename(vg)}{" Guest2="+os.path.basename(vg2) if vg2 else ""} cfg'),
 ('spk = sorted(set(l["speaker"] for l in ch), key=lambda s: 0 if s=="Host" else 1)',
  'spk = sorted(set(l["speaker"] for l in ch), key=lambda s: ORDER.get(s, 1))   # Host=Speaker 1, Guest=2, Guest2=3 (renumbered per chunk)'),
 ('vs = [vh if s=="Host" else vg for s in spk]', 'vs = [VMAP.get(s) or vg for s in spk]'),
])
patch("qc_vv.py", [
 ('ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default="Frank");',
  'ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default="Frank"); ap.add_argument("--guest2", default="");'),
 ('names = {"Host": a.host, "Guest": a.guest}', 'names = {"Host": a.host, "Guest": a.guest, "Guest2": a.guest2}'),
 ('ref = {s: (VF.get(names[s]) or', 'ref = {s: (VF.get(names.get(s, "")) or'),
 ('res["ref_f0"] = {"Host": ref_f0(a.host), "Guest": ref_f0(a.guest)}',
  'res["ref_f0"] = {"Host": ref_f0(a.host), "Guest": ref_f0(a.guest)}\nif a.guest2: res["ref_f0"]["Guest2"] = ref_f0(a.guest2)'),
])
patch("qc_mix.py", [
 ('ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default="Frank");',
  'ap.add_argument("--host", default="Carter"); ap.add_argument("--guest", default="Frank"); ap.add_argument("--guest2", default="");'),
 ('R = {"Host": ref(a.host), "Guest": ref(a.guest)}', 'R = {"Host": ref(a.host), "Guest": ref(a.guest)}\nif a.guest2: R["Guest2"] = ref(a.guest2)'),
 ('run = {"Host": [], "Guest": []}', 'run = {s: [] for s in R}'),
])
patch("podcast.ps1", [
 ('  [string]$GuestVoice = "Frank",', '  [string]$GuestVoice = "Frank",\n  [string]$Guest2Voice = "",     # v1.2: voice for "Guest2" lines (3-speaker scripts)'),
 ('$gl = if ($Glossary) { " --glossary `"$Glossary`"" } else { "" }',
  '$gl = if ($Glossary) { " --glossary `"$Glossary`"" } else { "" }\nif ($Guest2Voice) { $gl += " --guest2 $Guest2Voice" }'),
 ('$qa = "--chunks `"$chunks`" --host $HostVoice --guest $GuestVoice" +', '$qa = "--chunks `"$chunks`" --host $HostVoice --guest $GuestVoice" + $(if ($Guest2Voice) { " --guest2 $Guest2Voice" } else { "" }) +'),
 ('Write-Host "[2/3] VibeVoice ($HostVoice / $GuestVoice)..."', 'Write-Host "[2/3] VibeVoice ($HostVoice / $GuestVoice$(if ($Guest2Voice) { " / $Guest2Voice" }))..."'),
])
K = 'l["speaker"].lower().startswith("g") else "Host"'
patch("make_video.py", [
 ('COL = {"Host": (240, 170, 60), "Guest": (80, 190, 230)}',
  'COL = {"Host": (240, 170, 60), "Guest": (80, 190, 230), "Guest2": (220, 50, 70)}   # host amber, guest blue, guest2 crimson (v1.2)\n'
  'def spk_of(s):\n    s = s.lower().replace(" ", "")\n    return "Guest2" if s in ("guest2", "speaker3") else ("Guest" if s.startswith("g") else "Host")\n'
  'def spk_name(ctx, k): return {"Host": ctx["host"], "Guest": ctx["guest"], "Guest2": ctx.get("guest2") or "Guest 2"}[k]'),
 ('"Guest" if l["speaker"].lower().startswith("g") else "Host"', 'spk_of(l["speaker"])'),
 ('f"with {ctx[\'host\']} (host) and {ctx[\'guest\']} (guest)"',
  '(f"with {ctx[\'host\']} (host), {ctx[\'guest\']} and {ctx[\'guest2\']} (guests)" if ctx.get("guest2") else f"with {ctx[\'host\']} (host) and {ctx[\'guest\']} (guest)")'),
 ('nm = ctx["host"] if cue["spk"] == "Host" else ctx["guest"]; role',
  'nm = spk_name(ctx, cue["spk"]); role'),
 ('        subtitle(d, cue["text"])\n        out = Image.alpha_composite(im, ov)',
  '        if ctx.get("burn"): subtitle(d, cue["text"])\n        out = Image.alpha_composite(im, ov)'),
 ('name = ctx["host"] + " (host)" if cue["spk"] == "Host" else ctx["guest"] + " (guest)"',
  'name = spk_name(ctx, cue["spk"]) + (" (host)" if cue["spk"] == "Host" else " (guest)")'),
 ('    subtitle(d, cue["text"])\n    out = Image.alpha_composite(im, ov)',
  '    if ctx.get("burn"): subtitle(d, cue["text"])\n    out = Image.alpha_composite(im, ov)'),
 ('ap.add_argument("--guest", default="Frank")\n',
  'ap.add_argument("--guest", default="Frank")\n    ap.add_argument("--guest2", default="", help="name of the 2nd guest (script speaker \'Guest2\'; crimson plate)")\n'
  '    ap.add_argument("--burn-subs", action="store_true", help="burn subtitles into the frames + soft mov_text track (pre-v1.2 default); default: separate .srt only")\n'),
 ('"guest": a.guest, "bgmode"', '"guest": a.guest, "guest2": a.guest2, "burn": a.burn_subs, "bgmode"'),
 ('        subprocess.run(cmd, check=True); cmd = None',
  '        subprocess.run(nosubs(cmd, a.burn_subs), check=True); cmd = None'),
 ('    if cmd: subprocess.run(cmd, check=True)', '    if cmd: subprocess.run(nosubs(cmd, a.burn_subs), check=True)'),
 ('if __name__ == "__main__":',
  'def nosubs(cmd, burn):\n    """v1.2: without --burn-subs, drop the mov_text subtitle stream (the .srt is written next to the mp4)"""\n'
  '    if burn: return cmd\n    out, i = [], 0\n    while i < len(cmd):\n'
  '        if cmd[i] in ("-map", "-c:s", "-metadata:s:s:0") and i + 1 < len(cmd) and (cmd[i+1].endswith(":s") or cmd[i] != "-map"): i += 2; continue\n'
  '        out.append(cmd[i]); i += 1\n    return out\n\nif __name__ == "__main__":'),
])
