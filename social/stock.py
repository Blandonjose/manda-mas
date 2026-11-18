"""Free stock footage of real people (Pixabay or Pexels), for the backgrounds of the social videos.

clips(n, topics) -> list of local .mp4 paths (may be shorter than n, or empty without a key)
Needs a free API key from either site, as just the key in a text file:
  ~/Desktop/Manda Más – promociones/pixabay-key.txt   (or env PIXABAY_API_KEY)
  ~/Desktop/Manda Más – promociones/pexels-key.txt    (or env PEXELS_API_KEY)
Pixabay is tried first. Without either, the videos keep the plain blue background.

Simplest and most reliable: clips saved by hand (normal "Free download" on pixabay.com or pexels.com)
into  ~/Desktop/Manda Más – promociones/clips/   — general clips at the top, country clips in a
subfolder named by code (clips/MX/, clips/GT/, ...). These are used before the API.
Pixabay's API terms: download the files (no hotlinking) and no mass downloading; we fetch a
handful of clips per batch.

Each clip is used at most once every 45 days (stock-used.json), so videos keep looking different.
Pexels license: free for commercial use, no credit needed. The people in these clips are not our
customers: never caption them as if they were, or put words in their mouths.
"""
import json, os, random, time, urllib.parse, urllib.request

FOLDER = os.path.expanduser("~/Desktop/Manda Más – promociones")
CACHE = os.path.expanduser("~/Library/Caches/mandamas-stock")
USED = os.path.join(CACHE, "stock-used.json")
REUSE_DAYS = 45

GENERAL = ["hispanic family home", "latina woman smartphone", "latino man phone", "woman using phone kitchen",
           "family video call", "grandmother smiling phone", "mexican family", "latino family dinner",
           "construction worker phone break", "woman counting money", "young latina phone smiling",
           "father daughter phone", "elderly couple home", "mother and son hug", "family celebration latin"]
COUNTRY = {"MX": ["mexico city street", "mexico village", "mexican market"], "GT": ["guatemala", "antigua guatemala"],
           "DO": ["dominican republic", "santo domingo"], "CO": ["colombia city", "medellin"], "PE": ["lima peru", "peru market"],
           "CL": ["santiago chile", "chile city"], "UY": ["montevideo", "uruguay"], "HN": ["honduras"], "BO": ["bolivia", "la paz bolivia"],
           "CR": ["costa rica town"]}


def key(site="pexels"):
    k = os.environ.get(f"{site.upper()}_API_KEY")
    path = os.path.join(FOLDER, f"{site}-key.txt")
    if not k and os.path.exists(path):
        k = open(path).read().strip()
    return k or None


def _used():
    try:
        return json.load(open(USED))
    except (OSError, ValueError):
        return {}


def _get(url, k=None):
    req = urllib.request.Request(url, headers={"User-Agent": "manda-mas-social/1.0", **({"Authorization": k} if k else {})})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _best_file(video):
    """A portrait MP4 between 1280 and 2160 px tall, closest to 1920."""
    ok = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width") and f.get("height")
          and f["height"] > f["width"] and 1280 <= f["height"] <= 2160]
    return min(ok, key=lambda f: abs(f["height"] - 1920)) if ok else None


def _pixabay(q, k):
    """[(id, mp4 url)] for one search, portrait clips first (Pixabay has no orientation filter for video)."""
    res = _get("https://pixabay.com/api/videos/?" + urllib.parse.urlencode(
        {"key": k, "q": q, "per_page": 50, "safesearch": "true", "video_type": "film"}))
    out = []
    for h in res.get("hits", []):
        if h.get("duration", 0) < 5:
            continue
        files = [f for f in h.get("videos", {}).values() if f.get("url") and f.get("height", 0) >= 720]
        if not files:
            continue
        f = min(files, key=lambda f: abs(max(f["width"], f["height"]) - 1920))
        out.append((f["height"] > f["width"], f"pb{h['id']}", f["url"]))
    out.sort(key=lambda x: not x[0])
    return [(i, u) for _, i, u in out]


def _pexels(q, k):
    res = _get("https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
        {"query": q, "orientation": "portrait", "size": "medium", "per_page": 30}), k)
    out = []
    for v in res.get("videos", []):
        f = _best_file(v) if v.get("duration", 0) >= 5 else None
        if f:
            out.append((str(v["id"]), f["link"]))
    return out


ALLOWED_HOSTS = ("videos.pexels.com", "player.vimeo.com", "cdn.pixabay.com")


CLIPS = os.path.join(FOLDER, "clips")


def _local(n, topics, fresh, now):
    """Clips downloaded by hand from pixabay.com / pexels.com into the clips folder.
    clips/MX/*.mp4 etc. are used for that country's videos; clips/*.mp4 for anything."""
    code = next((c for c, qs in COUNTRY.items() if topics and list(topics) == qs), None)
    pools = ([os.path.join(CLIPS, code)] if code else []) + [CLIPS]
    out = []
    for d in pools:
        try:
            names = [f for f in os.listdir(d) if f.lower().endswith(".mp4")]
        except OSError:
            continue
        random.shuffle(names)
        for f in names:
            vid = "local:" + os.path.relpath(os.path.join(d, f), CLIPS)
            if len(out) >= n:
                return out
            if vid not in fresh:
                fresh[vid] = now
                out.append(os.path.join(d, f))
    # Not enough unused clips: reuse the ones used longest ago (better than a plain background).
    if len(out) < n:
        old = sorted((ts, vid) for vid, ts in fresh.items() if vid.startswith("local:") and os.path.join(CLIPS, vid[6:]) not in out
                     and os.path.exists(os.path.join(CLIPS, vid[6:])) and ts < now)
        for ts, vid in old[:n - len(out)]:
            fresh[vid] = now
            out.append(os.path.join(CLIPS, vid[6:]))
    return out


def clips(n, topics=None):
    used, now = _used(), time.time()
    fresh = {vid: ts for vid, ts in used.items() if now - ts < REUSE_DAYS * 86400}
    out = _local(n, topics, fresh, now)
    if out:
        os.makedirs(CACHE, exist_ok=True)
        json.dump(fresh, open(USED, "w"))
    if len(out) >= n:
        return out
    return out + _api(n - len(out), topics)


def _api(n, topics=None):
    site ="pixabay" if key("pixabay") else "pexels" if key("pexels") else None
    if not site:
        return []
    k = key(site)
    search = _pixabay if site == "pixabay" else _pexels
    os.makedirs(CACHE, exist_ok=True)
    used, now = _used(), time.time()
    fresh = {vid: ts for vid, ts in used.items() if now - ts < REUSE_DAYS * 86400}
    queries = list(topics or []) + random.sample(GENERAL, len(GENERAL))
    out = []
    for q in queries:
        if len(out) >= n:
            break
        try:
            found = [(i, u) for i, u in search(q, k) if i not in fresh]
        except Exception:
            continue
        top = found[:10]  # keep portrait clips first, but don't always take the same one
        random.shuffle(top)
        for vid, link in top:
            if urllib.parse.urlparse(link).hostname not in ALLOWED_HOSTS:
                continue
            path = os.path.join(CACHE, f"{vid}.mp4")
            if not os.path.exists(path):
                try:
                    urllib.request.urlretrieve(link, path + ".part")
                    os.replace(path + ".part", path)
                except Exception:
                    continue
            fresh[vid] = now
            out.append(path)
            break  # one clip per search, so the clips differ from each other
    json.dump(fresh, open(USED, "w"))
    return out
