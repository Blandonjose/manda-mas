"""Free stock footage of real people from Pexels, for the backgrounds of the social videos.

clips(n, topics) -> list of local .mp4 paths (may be shorter than n, or empty without a key)
Needs a free Pexels API key: env PEXELS_API_KEY, or the file
~/Desktop/Manda Más – promociones/pexels-key.txt (just the key). Without one, the videos keep
the plain blue background.

Each clip is used at most once every 45 days (stock-used.json), so videos keep looking different.
Pexels license: free for commercial use, no credit needed. The people in these clips are not our
customers: never caption them as if they were, or put words in their mouths.
"""
import json, os, random, time, urllib.parse, urllib.request

KEY_FILE = os.path.expanduser("~/Desktop/Manda Más – promociones/pexels-key.txt")
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


def key():
    k = os.environ.get("PEXELS_API_KEY")
    if not k and os.path.exists(KEY_FILE):
        k = open(KEY_FILE).read().strip()
    return k or None


def _used():
    try:
        return json.load(open(USED))
    except (OSError, ValueError):
        return {}


def _get(url, k):
    req = urllib.request.Request(url, headers={"Authorization": k, "User-Agent": "manda-mas-social/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def _best_file(video):
    """A portrait MP4 between 1280 and 2160 px tall, closest to 1920."""
    ok = [f for f in video.get("video_files", []) if f.get("file_type") == "video/mp4" and f.get("width") and f.get("height")
          and f["height"] > f["width"] and 1280 <= f["height"] <= 2160]
    return min(ok, key=lambda f: abs(f["height"] - 1920)) if ok else None


def clips(n, topics=None):
    k = key()
    if not k:
        return []
    os.makedirs(CACHE, exist_ok=True)
    used, now = _used(), time.time()
    fresh = {vid: ts for vid, ts in used.items() if now - ts < REUSE_DAYS * 86400}
    queries = list(topics or []) + random.sample(GENERAL, len(GENERAL))
    out = []
    for q in queries:
        if len(out) >= n:
            break
        try:
            res = _get("https://api.pexels.com/videos/search?" + urllib.parse.urlencode(
                {"query": q, "orientation": "portrait", "size": "medium", "per_page": 30}), k)
        except Exception:
            continue
        videos = [v for v in res.get("videos", []) if str(v["id"]) not in fresh and v.get("duration", 0) >= 5]
        random.shuffle(videos)
        for v in videos:
            f = _best_file(v)
            link = f and f["link"]
            if not link or urllib.parse.urlparse(link).hostname not in ("videos.pexels.com", "player.vimeo.com"):
                continue
            path = os.path.join(CACHE, f"{v['id']}.mp4")
            if not os.path.exists(path):
                try:
                    urllib.request.urlretrieve(link, path + ".part")
                    os.replace(path + ".part", path)
                except Exception:
                    continue
            fresh[str(v["id"])] = now
            out.append(path)
            break  # one clip per search, so the clips differ from each other
    json.dump(fresh, open(USED, "w"))
    return out
