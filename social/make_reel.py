"""Make a faceless Reel (vertical MP4), a feed image and a caption from today's live prices on mandamasdinero.com.

usage: python3 make_reel.py [COUNTRY_CODE] [AMOUNT]      e.g.  python3 make_reel.py MX 300
Writes out/<code>-<amount>-<date>/ with reel.mp4, post.png and caption.txt.
Needs Google Chrome and Swift (both already on this Mac); the encoder is encode.swift.
"""
import importlib.util, json, os, re, subprocess, sys, unicodedata, urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stock, voice
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.join(HERE, "..")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
POPULAR = ["Western Union", "Remitly"]  # what most families already use
UNITS = {"MXN": "pesos", "GTQ": "quetzales", "HNL": "lempiras", "USD": "dólares", "DOP": "pesos", "COP": "pesos",
         "CRC": "colones", "PEN": "soles", "CLP": "pesos", "BOB": "bolivianos", "UYU": "pesos"}

spec = importlib.util.spec_from_file_location("u", os.path.join(REPO, "update_rates.py"))
u = importlib.util.module_from_spec(spec)
spec.loader.exec_module(u)


def flag(code):
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code)


def shoot(url, path, w, h, tries=2):
    try:
        _shoot(url, path, w, h)
    except subprocess.TimeoutExpired:  # headless Chrome occasionally hangs; one retry
        if tries <= 1:
            raise
        shoot(url, path, w, h, tries - 1)


def _shoot(url, path, w, h):
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--virtual-time-budget=6000",
                    "--force-device-scale-factor=1", "--default-background-color=00000000", f"--window-size={w},{h}", f"--screenshot={path}", url],
                   check=True, capture_output=True, timeout=90)


def main():
    code = (sys.argv[1] if len(sys.argv) > 1 else "MX").upper()
    amount = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    page = urllib.request.urlopen("https://mandamasdinero.com/").read().decode()
    data = json.loads(re.search(r'<script[^>]*id="rates"[^>]*>(.*?)</script>', page, re.S).group(1))
    _, affiliate = u.page_links(page)
    country = next(c for c in data["countries"] if c["code"] == code)
    if str(amount) not in str(data["brackets"]):
        sys.exit(f"amount must be one of {data['brackets']}")
    ranks = u.ranked(country, amount)
    by_name = {r["name"]: r for r in ranks}
    popular = [by_name[n] for n in POPULAR if n in by_name]
    if not popular:
        sys.exit("no Western Union/Remitly data for this country and amount")
    # Compare against the BETTER of the popular apps, and only show Wise/Instarem where they beat it,
    # so the "+X more" claim holds against both popular apps.
    baseline = max(r["received"] for r in popular)
    good = [r for r in ranks if r["name"] in affiliate and r["received"] > baseline]
    if not good:
        sys.exit(f"Wise/Instarem don't beat Western Union/Remitly today for {code} ${amount}; no video.")
    diff = max(r["received"] for r in good) - baseline
    if diff < 0.005 * baseline:
        sys.exit(f"difference too small today for {code} ${amount} (under 0.5%); no video.")
    shown = sorted(popular + good, key=lambda r: r["received"])
    top = ranks[0]
    promo = None
    if top not in shown and top["markup"] < -0.1:
        promo = f"⭐ {top['name']} da todavía más, pero es una promoción que casi siempre es solo para el primer envío."

    when = datetime.fromisoformat(data["collected"].replace("Z", "+00:00")).astimezone(ZoneInfo("America/Los_Angeles"))
    date = f"{when.day} de {u.MONTHS[when.month - 1]}"
    unit = UNITS.get(country["currency"], country["currency"])
    money = lambda n: f"{n:,.0f}" if n >= 10 else f"{n:,.2f}"  # whole units read better on screen
    fill = {"flag": flag(code), "amount": amount, "country": country["name"], "unit": unit, "date": date,
            "rows": [{"name": r["name"], "received": money(r["received"]), "good": r["name"] in affiliate} for r in shown],
            "diff": money(diff), "promo": promo, "tap": os.environ.get("TAP")}  # TAP: last-scene hint, e.g. "🔗 Link en el perfil"

    out = os.environ.get("OUT_DIR") or os.path.join(HERE, "out", f"{code.lower()}-{amount}-{when:%Y-%m-%d}" + os.environ.get("OUT_SUFFIX", ""))
    os.makedirs(out, exist_ok=True)
    html = os.path.join(out, "reel.html")
    with open(os.path.join(HERE, "reel.html")) as f:
        open(html, "w").write(f.read().replace("/*DATA*/null", json.dumps(fill, ensure_ascii=False)))

    # (scene, rows shown, seconds on screen), in four spoken groups: hook, rows, difference, ending
    groups = [[(0, 0, 2.6)], [(1, n, 1.3) for n in range(1, len(shown))] + [(1, len(shown), 2.6)], [(2, 0, 3.4)], [(3, 0, 4.4)]]
    best_popular = max(popular, key=lambda r: r["received"])["name"]
    spoken = lambda n: str(round(n)) if n >= 10 else f"{n:.2f}"
    lines = [f"¿Mandas {amount} dólares a {country['name']}? Mira cuánto le llega a tu familia con cada app.",
             " ".join([f"Con {shown[0]['name']} llegan {spoken(shown[0]['received'])} {unit}."]
                      + [f"Con {r['name']}, {spoken(r['received'])}." for r in shown[1:-1]]
                      + [f"Y con {shown[-1]['name']}, {spoken(shown[-1]['received'])}."]),
             f"Son {spoken(diff)} {unit} más que con {best_popular}, solo por elegir otra app."
             + (f" {top['name']} da todavía más, pero es una promoción, casi siempre solo para el primer envío." if promo else ""),
             voice.END_LINE + (" El link está en nuestro perfil." if "perfil" in (fill["tap"] or "") else "")]
    clips, said = [], []
    for i, line in enumerate(lines):
        if voice.ENABLED:
            path = os.path.join(out, f"voz{i}.m4a")
            said.append(voice.speak(line, path))
            clips.append(path)
        else:
            said.append(0)
    secs, starts = voice.fit([([s for _, _, s in g], d) for g, d in zip(groups, said)])
    plan = [(scene, rows, s) for (scene, rows, _), s in zip([f for g in groups for f in g], secs)]
    group_of = [gi for gi, g in enumerate(groups) for _ in g]
    # Real people behind the numbers: one stock clip per spoken group, the first one from the country.
    bg = [] if os.environ.get("NOSTOCK") else stock.clips(len(groups), stock.COUNTRY.get(code, []))
    manifest = []
    for i, (scene, rows, secs) in enumerate(plan):
        png = os.path.join(out, f"frame{i:02d}.png")
        if bg:
            shoot(f"file://{html}#scene={scene}&rows={rows}&bg=1", png, 1080, 1920)
            manifest.append(f"{png}\t{secs}\t{bg[group_of[i] % len(bg)]}")
        else:
            shoot(f"file://{html}#scene={scene}&rows={rows}", png, 1080, 1920)
            manifest.append(f"{png}\t{secs}")
    open(os.path.join(out, "manifest.txt"), "w").write("\n".join(manifest))
    final = os.path.join(out, "reel.mp4")
    silent = os.path.join(out, "silent.mp4") if clips else final
    subprocess.run(["swift", os.path.join(HERE, "encode.swift"), os.path.join(out, "manifest.txt"), silent], check=True)
    if clips:
        voice.mux(silent, list(zip(clips, starts)), final)
        os.remove(silent)
    open(os.path.join(out, "narracion.txt"), "w").write("\n".join(lines) + "\n")

    # Feed image (4:5): the full list on one picture.
    shoot(f"file://{html}#scene=1&rows=99&post=1", os.path.join(out, "post.png"), 1080, 1350)

    lines = [f"¿Mandas dinero a {country['name']}? {flag(code)}", "",
             f"Cuántos {unit} recibe la familia por un envío de ${amount} (precios del {date}):", ""]
    lines += [f"{'✅' if r['name'] in affiliate else '🔸'} {r['name']}: {money(r['received'])} {unit}" for r in reversed(shown)]
    if promo:
        lines += [f"⭐ {top['name']}: {money(top['received'])} {unit} (promoción, casi siempre solo el primer envío)"]
    lines += ["", f"Con el mismo dinero, tu familia puede recibir {money(diff)} {unit} más que con {max(popular, key=lambda r: r['received'])['name']}, solo por elegir otra app.", "",
              "Los precios cambian cada día, así que compara antes de mandar 👇", "https://mandamasdinero.com", "",
              "Son estimaciones; el precio final lo ves en la app antes de confirmar.",
              "", "#remesas #enviardinero #" + re.sub(r"\W", "", unicodedata.normalize("NFKD", country["name"].lower()).encode("ascii", "ignore").decode())]
    open(os.path.join(out, "caption.txt"), "w").write("\n".join(lines) + "\n")
    print(out)


main()
