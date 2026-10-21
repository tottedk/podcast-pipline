"""md_clean.py (template v1.4, 2026-10-15) - strip markdown emphasis marks from script TEXT (never from the speaker field) before TTS.
Gemma/other LLMs sometimes leave *italic*, **bold**, _italic_, `code`, '# ' headings or '- ' bullets in the dialogue. Only the marks are removed;
the words inside are kept exactly (no respelling, no other edits). Conservative on purpose:
  *word* **word** ***word*** _word_ __word__ ~~word~~ `word` [text](url) -> word / text ;  '# ', '> ', '- ', '* ', '+ ' at the start of a line removed
  literal asterisks in math/code stay:  2 * 3,  3*4*5,  a*b ;   underscores inside identifiers stay:  snake_case, my_var_name ;  speaker tags stay:  **Host:** Hi -> Host: Hi
Usage:  python md_clean.py script.json [out.json]   (default: in place; if anything changed, the original is saved as <script>.pre_md.json first; unchanged files are not rewritten)
        from md_clean import clean_markdown, clean_lines, strip_lead_sighs
v1.12 (2026-10-21): strip_lead_sighs() - a Guest/Guest2 line must not OPEN with [sighs] (Fault Lines #1: 3 of Elliot's 4 slowest lines began with
[sighs], ~1 s sigh + pause each). The leading tag is removed (the rest of the line is unchanged; a line that is only "[sighs]" is kept). The CLI
applies it after the markdown clean (run_episode.ps1 runs it in place on every segNN.json before TTS); drama3_generate.py applies it again."""
import re, sys, json, shutil

_W = r"[^\W_]"   # letter/digit
def clean_markdown(t):
    if not t: return t
    s = t
    s = re.sub(r"```[a-zA-Z0-9_+-]*\n?", "", s)                                   # code fences (marks only)
    s = re.sub(r"`([^`\n]+)`", r"\1", s); s = s.replace("`", "")                  # inline code / stray backticks
    s = re.sub(r"!?\[([^\]\n]+)\]\((?:https?://|www\.)[^)\s]*\)", r"\1", s)       # [text](url) -> text
    s = re.sub(r"^[ \t]{0,3}(?:#{1,6}[ \t]+|>[ \t]?|[-*+\u2022][ \t]+)", "", s, flags=re.M)   # leading markdown (headings, quotes, bullets)
    for _ in range(2):                                                            # nested like **_x_** needs two passes
        s = re.sub(r"(?<![\w*])\*{3}(?=\S)(.+?)(?<=\S)\*{3}(?![\w*])", r"\1", s)
        s = re.sub(r"(?<![\w*])\*{2}(?=\S)(.+?)(?<=\S)\*{2}(?![\w*])", r"\1", s)
        s = re.sub(r"(?<![\w*])\*(?=[^\s*])([^*\n]+?)(?<=[^\s*])\*(?![\w*])", r"\1", s)
        s = re.sub(r"(?<![\w_])__(?=\S)(.+?)(?<=\S)__(?![\w_])", r"\1", s)
        s = re.sub(r"(?<![\w_])_(?=[^\s_])([^_\n]+?)(?<=[^\s_])_(?![\w_])", r"\1", s)
        s = re.sub(r"(?<!~)~~(?=\S)(.+?)(?<=\S)~~(?!~)", r"\1", s)
    s = re.sub(r"\*{2,}", "", s)                                                  # unpaired runs of ** (never math)
    s = re.sub(r"(?<![\w*])\*(?=[^\W_])", "", s)                                  # stray leading *word
    s = re.sub(r"(?<=[^\W_])\*(?![\w*])", "", s)                                  # stray trailing word*  (a*b and 3*4 stay: both sides alnum)
    return s.strip() if s != t else t

LEAD_SIGH = re.compile(r"^\s*\[(?:sighs?|sighing|sigh heavily|heavy sigh)\]\s*", re.I)
def strip_lead_sighs(lines, roles=("Guest", "Guest2")):
    """[{speaker,text},...] -> (new list, number of guest lines that lost a leading [sighs] tag)"""
    out = []; n = 0
    for l in lines:
        if isinstance(l, dict) and l.get("speaker") in roles and isinstance(l.get("text"), str) and LEAD_SIGH.match(l["text"]):
            t = LEAD_SIGH.sub("", l["text"], count=1)
            if t.strip(): l = {**l, "text": t}; n += 1
        out.append(l)
    return out, n

def clean_lines(lines):
    """[{speaker,text},...] -> (new list, number of lines whose text changed). Only 'text' is touched."""
    out = []; n = 0
    for l in lines:
        if isinstance(l, dict) and isinstance(l.get("text"), str):
            c = clean_markdown(l["text"])
            if c != l["text"]: n += 1; l = {**l, "text": c}
        out.append(l)
    return out, n

if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    if not args: sys.exit(__doc__)
    src = args[0]; out = args[1] if len(args) > 1 else src
    L = json.load(open(src, encoding="utf-8-sig")); new, n = clean_lines(L); new, ns = strip_lead_sighs(new)
    if ns: print(f"md_clean: {src}: {ns} leading guest [sighs] tag(s) removed")
    n += ns
    if n == 0 and out == src: print(f"md_clean: {src}: nothing to strip"); sys.exit(0)
    if out == src: shutil.copy(src, src[:-5] + ".pre_md.json")
    json.dump(new, open(out, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print(f"md_clean: {n} line(s) cleaned -> {out}")
