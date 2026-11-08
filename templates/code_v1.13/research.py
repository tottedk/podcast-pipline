r"""tools\research.py (2026-11-01, technical v1.13) - topic-first web research for brief_gen.py. STDLIB ONLY (no requests/bs4/ddgs on the PC).
search(query)  : DuckDuckGo lite endpoint (no key) -> DuckDuckGo HTML (often 202 anomaly page) -> Wikipedia search API (always available backstop)
fetch(url)     : robots.txt-respecting GET (UA header, 20 s timeout, <= 3 MB, html/text only), readable text extraction (p/li/h/blockquote,
                 no script/style/nav/header/footer/aside/form), title + site + date
research(topic, queries, log) -> (sources, docs): sources = list of dicts for gen\research\sources.json;
                 docs = book-like objects {title, author(site), file(url), path, url, pages(~400-word sections), kind "web"} for brief_gen's
                 normal focus -> notes -> quote-verification steps (quotes are verified against the fetched page text exactly like book pages).
CLI smoke test: python research.py "query" [--fetch]"""
import gzip, html, json, re, sys, time, urllib.error, urllib.parse, urllib.request, urllib.robotparser
from html.parser import HTMLParser

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
BOT_UA = "EpisodeDeskResearch/1.13 (private study podcast; stdlib urllib)"
SKIP_DOMAINS = ("youtube.com", "youtu.be", "facebook.com", "instagram.com", "tiktok.com", "twitter.com", "x.com", "pinterest.", "linkedin.com",
                "amazon.", "ebay.", "reddit.com", "quora.com", "duckduckgo.com", "bing.com", "google.", "spotify.com", "apple.com/podcast")
MAX_BYTES = 3_000_000; TIMEOUT = 20

def _get(url, data=None, ua=UA, timeout=TIMEOUT, accept="text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.5"):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": ua, "Accept": accept, "Accept-Language": "en-GB,en;q=0.8", "Accept-Encoding": "gzip"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        ct = r.headers.get("Content-Type", ""); raw = r.read(MAX_BYTES + 1)
        if r.headers.get("Content-Encoding", "") == "gzip": raw = gzip.decompress(raw)
        cs = (re.search(r"charset=([\w-]+)", ct) or [None, "utf-8"])[1]
        try: txt = raw.decode(cs, "replace")
        except LookupError: txt = raw.decode("utf-8", "replace")
        return r.status, ct, txt, r.geturl()

def _skip(url):
    h = urllib.parse.urlparse(url).netloc.lower()
    return (not url.startswith("http")) or any(d in h or d in url for d in SKIP_DOMAINS) or url.lower().split("?")[0].endswith((".pdf", ".jpg", ".png", ".mp3", ".mp4", ".zip"))

# ---------------- search ----------------
def _ddg_links(page):
    out = []
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', page, re.S | re.I):
        href, label = html.unescape(m.group(1)), re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if "uddg=" in href: href = urllib.parse.unquote(urllib.parse.parse_qs(urllib.parse.urlparse(href).query).get("uddg", [""])[0])
        if href.startswith("//"): href = "https:" + href
        if not href.startswith("http") or "duckduckgo.com" in href or not label: continue
        if ('result__a' in m.group(0) or 'result-link' in m.group(0)) and href not in [u for u, _ in out]: out.append((href, html.unescape(label)))
    return out

def search(q, n=6, log=print, retry=True):
    """-> list of (url, title, engine). DuckDuckGo html, then lite; Wikipedia backstop is added by research()."""
    for eng, url, data in (("ddg_lite", "https://lite.duckduckgo.com/lite/", urllib.parse.urlencode({"q": q, "kl": "uk-en"}).encode()),
                           ("ddg_html", "https://html.duckduckgo.com/html/", urllib.parse.urlencode({"q": q, "kl": "uk-en"}).encode())):
        try:
            stc, ct, page, _ = _get(url, data=data)
            res = [(u, t, eng) for u, t in _ddg_links(page) if not _skip(u)]
            if res: return res[:n]
            log(f"research: {eng} gave 0 results for '{q}' (status {stc}, {len(page)} bytes{', anomaly/captcha page' if 'anomaly' in page.lower() or stc == 202 else ''})")
        except Exception as e: log(f"research: {eng} failed for '{q}': {e}")
        time.sleep(1.5)
    if retry:   # DuckDuckGo rate-limits bursts with a 202 anomaly page: one slow retry
        time.sleep(12); return search(q, n, log, retry=False)
    return []

def wiki_search(q, n=3, log=print):
    try:
        u = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "list": "search", "srsearch": q, "srlimit": n, "format": "json"})
        _, _, txt, _ = _get(u, ua=BOT_UA, accept="application/json")
        return [("https://en.wikipedia.org/wiki/" + urllib.parse.quote(x["title"].replace(" ", "_")), x["title"], "wikipedia") for x in json.loads(txt)["query"]["search"]]
    except Exception as e: log(f"research: wikipedia search failed for '{q}': {e}"); return []

# ---------------- extraction ----------------
class _Text(HTMLParser):
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "button", "select", "figure", "iframe", "template"}
    KEEP = {"p", "li", "h1", "h2", "h3", "h4", "blockquote", "dd", "td"}
    def __init__(self):
        super().__init__(convert_charrefs=True); self.skip = 0; self.cur = None; self.blocks = []; self.title = ""; self.in_title = False; self.meta = {}
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP: self.skip += 1
        elif tag == "title": self.in_title = True
        elif tag == "meta":
            k = (a.get("property") or a.get("name") or "").lower()
            if k in ("og:title", "og:site_name", "author", "article:published_time", "date", "citation_author", "dc.date"): self.meta.setdefault(k, a.get("content") or "")
        elif tag in self.KEEP and not self.skip: self.cur = []
        elif tag == "br" and self.cur is not None: self.cur.append(" ")
    def handle_endtag(self, tag):
        if tag in self.SKIP: self.skip = max(0, self.skip - 1)
        elif tag == "title": self.in_title = False
        elif tag in self.KEEP and self.cur is not None:
            t = re.sub(r"\s+", " ", "".join(self.cur)).strip()
            if t: self.blocks.append((tag, t))
            self.cur = None
    def handle_data(self, d):
        if self.in_title: self.title += d
        if self.cur is not None and not self.skip: self.cur.append(d)

def extract(page):
    p = _Text()
    try: p.feed(page)
    except Exception: pass
    keep = []
    for tag, t in p.blocks:
        w = len(t.split())
        if tag.startswith("h") and 2 <= w <= 20: keep.append(t + ".")
        elif w >= 12 and not re.search(r"(?i)cookie|subscribe|sign up|newsletter|all rights reserved|javascript|advert", t): keep.append(t)
    seen = set(); keep = [t for t in keep if not (t in seen or seen.add(t))]
    title = (p.meta.get("og:title") or p.title or "").strip()
    return {"title": re.sub(r"\s+", " ", html.unescape(title))[:160], "site": p.meta.get("og:site_name", ""), "author": p.meta.get("author") or p.meta.get("citation_author", ""),
            "date": (p.meta.get("article:published_time") or p.meta.get("date") or p.meta.get("dc.date") or "")[:10], "text": "\n".join(keep)}

_robots = {}
def allowed(url):
    pr = urllib.parse.urlparse(url); base = f"{pr.scheme}://{pr.netloc}"
    if base not in _robots:
        rp = urllib.robotparser.RobotFileParser()
        try:
            _, _, txt, _ = _get(base + "/robots.txt", ua=BOT_UA, timeout=8, accept="text/plain"); rp.parse(txt.splitlines())
        except Exception: rp = None   # no robots.txt / unreachable = allowed
        _robots[base] = rp
    rp = _robots[base]
    return True if rp is None else (rp.can_fetch(BOT_UA, url) or rp.can_fetch("*", url))

def fetch(url, log=print):
    if url.startswith("https://en.wikipedia.org/wiki/"):   # plain-text extract via the API (no nav noise)
        t = urllib.parse.unquote(url.rsplit("/", 1)[1])
        u = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode({"action": "query", "prop": "extracts", "explaintext": 1, "titles": t, "format": "json", "redirects": 1})
        _, _, txt, _ = _get(u, ua=BOT_UA, accept="application/json"); pg = next(iter(json.loads(txt)["query"]["pages"].values()))
        body = re.sub(r"\n==+ (See also|References|External links|Further reading|Notes|Bibliography|Sources) ==+\n.*", "", pg.get("extract", ""), flags=re.S)
        body = re.sub(r"\n==+ ([^=]+) ==+\n", r"\n\1.\n", body)
        return {"title": pg.get("title", t), "site": "Wikipedia", "author": "Wikipedia", "date": "", "text": body, "url": url}
    if not allowed(url): raise RuntimeError("disallowed by robots.txt")
    stc, ct, page, final = _get(url)
    if "html" not in ct and "text/plain" not in ct: raise RuntimeError(f"content-type {ct}")
    d = extract(page) if "html" in ct else {"title": url, "site": "", "author": "", "date": "", "text": page}
    d["url"] = final; return d

def sections(text, n=400):
    w = text.split(); return [" ".join(w[i:i + n]) for i in range(0, len(w), n)]

def site_name(url, d):
    s = (d.get("site") or "").strip()
    if s and len(s) < 60: return s
    h = urllib.parse.urlparse(url).netloc.lower().replace("www.", ""); return h

# ---------------- driver ----------------
def research(topic, queries, log=print, per_query=5, max_docs=14, min_words=300, deadline_s=600, wiki_titles=None):
    t0 = time.time(); cand, seen = [], set()
    for q in queries:
        if time.time() - t0 > deadline_s * 0.5: break
        for u, t, e in search(q, per_query, log):
            k = u.split("#")[0].rstrip("/")
            if k not in seen: seen.add(k); cand.append((u, t, e, q))
        time.sleep(4)
    for q in (wiki_titles or queries[:3]):   # Wikipedia backstop: always a few encyclopaedic pages, also when DuckDuckGo blocks
        for u, t, e in wiki_search(q, 1 if wiki_titles else 2, log):
            k = u.rstrip("/")
            if k not in seen: seen.add(k); cand.append((u, t, e, q))
    log(f"research: {len(queries)} queries -> {len(cand)} candidate urls ({sum(c[2].startswith('ddg') for c in cand)} DuckDuckGo, {sum(c[2] == 'wikipedia' for c in cand)} Wikipedia)")
    sources, docs, per_site = [], [], {}
    for u, t, e, q in cand:
        if len(docs) >= max_docs or time.time() - t0 > deadline_s: break
        host = urllib.parse.urlparse(u).netloc.lower()
        if per_site.get(host, 0) >= 2: continue
        rec = {"url": u, "search_title": t, "engine": e, "query": q}
        try:
            d = fetch(u, log); w = len(d["text"].split())
            rec.update(title=d["title"] or t, site=site_name(u, d), author=d.get("author", ""), date=d.get("date", ""), words=w)
            if w < min_words: rec["status"] = f"skipped: only {w} words of readable text"
            else:
                secs = sections(d["text"])[:40]; per_site[host] = per_site.get(host, 0) + 1
                docs.append({"title": rec["title"], "author": rec["site"], "file": d["url"], "path": d["url"], "url": d["url"], "pages": secs, "kind": "web", "date": rec["date"]})
                rec["status"] = f"used: {len(secs)} sections"
        except Exception as ex: rec["status"] = f"failed: {str(ex)[:120]}"
        log(f"research: {rec['status']} | {u}"); sources.append(rec)
    log(f"research: {len(docs)} readable pages ({sum(len(d['pages']) for d in docs)} sections) in {time.time()-t0:.0f} s")
    return sources, docs

if __name__ == "__main__":
    q = " ".join(a for a in sys.argv[1:] if not a.startswith("--")) or "AI training data human bias"
    r = search(q) + wiki_search(q); print(json.dumps(r, indent=1))
    if "--fetch" in sys.argv and r:
        d = fetch(r[0][0]); print(d["title"], d["site"], len(d["text"].split()), "words"); print(d["text"][:600])
