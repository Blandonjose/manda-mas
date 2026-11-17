"""Evergreen explainer Reels (no dated prices, so they can be posted any week).

usage: python3 make_explainer.py [SLUG]     -> out/explainers/<slug>/{video.mp4, texto.txt}  (all of them without SLUG)
Uses the same Chrome screenshot + encode.swift pipeline as make_reel.py.
"""
import json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

LOGO = ('<div class="logo"><div class="mark">$</div><span>Manda <em>Más</em></span></div>'
        '<h2>Compara antes de mandar.</h2>'
        '<div class="ticks"><span>✅ Gratis</span><span>✅ En español</span><span>✅ Sin registrarte</span></div>'
        '<div class="url">mandamasdinero.com</div><div class="tap">' + os.environ.get("TAP", "👇 Toca el link en el comentario fijado") + '</div>')

# Worked example for "sin comisión": mid 18.50; A = $0 fee at 18.00 -> 5,400; B = $3 fee at 18.45 -> 297*18.45 = 5,479.65.
VIDEOS = {
    "sin-comision-no-es-gratis": {
        "slides": [
            ('<div class="eyebrow">Ojo antes de mandar dinero</div><h1>“Sin comisión” <em>no</em> quiere decir gratis.</h1>', 3.0),
            ('<h2>Las apps ganan de dos formas:</h2><div class="cards">'
             '<div class="card"><div class="top"><span>1. La comisión</span></div><div class="bot"><span>La ves: $0, $1.99, $3…</span></div></div>'
             '<div class="card"><div class="top"><span>2. El tipo de cambio</span></div><div class="bot"><span>Casi no se ve: te dan menos pesos por cada dólar</span></div></div></div>', 4.0),
            ('<div class="eyebrow">Ejemplo con $300 a México</div><h2>Si el dólar está a 18.50 pesos…</h2><div class="cards">'
             '<div class="card"><div class="top"><span>App A · “$0 comisión”</span></div><div class="bot"><span>te da 18.00 por dólar</span><b>5,400</b></div></div>'
             '<div class="card good"><div class="top"><span>App B · $3 de comisión</span></div><div class="bot"><span>te da 18.45 por dólar</span><b>5,480</b></div></div>'
             '</div><p class="small">Ejemplo para explicar. Los precios reales cambian cada día.</p>', 5.0),
            ('<h2>La que cobra comisión entrega</h2><div class="num">+80</div><h2>pesos más 🤯</h2>'
             '<p class="body">Lo que importa es cuánto <em>recibe</em> tu familia, no la comisión.</p>', 3.6),
            (LOGO + '<p class="small">Te mostramos cuánto recibe tu familia con cada app, con la comisión y el tipo de cambio ya incluidos.</p>', 4.4),
        ],
        "caption": [
            "“Sin comisión” no quiere decir gratis 👀", "",
            "Las apps para mandar dinero ganan de dos formas: la comisión (que sí ves) y el tipo de cambio (que casi no se ve).", "",
            "Ejemplo con $300 a México, si el dólar está a 18.50:",
            "🔸 App A, “$0 comisión”, te da 18.00 → tu familia recibe 5,400 pesos",
            "✅ App B, $3 de comisión, te da 18.45 → tu familia recibe 5,480 pesos", "",
            "La que cobra comisión entrega 80 pesos más. Por eso hay que comparar cuánto RECIBE tu familia 🙌", "",
            "Compara gratis y en español 👇", "https://mandamasdinero.com", "",
            "(Ejemplo para explicar; los precios reales cambian cada día.)", "",
            "#remesas #enviardinero #tipodecambio",
        ],
    },
    "3-cosas-antes-de-mandar": {
        "slides": [
            ('<div class="eyebrow">Antes de mandar dinero</div><h1><em>3 cosas</em> que debes revisar</h1><p class="body">para que a tu familia le llegue más 👇</p>', 3.0),
            ('<div class="num">1</div><h2>Mira cuánto <em>recibe</em> tu familia.</h2><p class="body">No te fijes solo en la comisión. El tipo de cambio también cuesta.</p>', 4.0),
            ('<div class="num">2</div><h2>Las promociones casi siempre son <em>solo el primer envío</em>.</h2><p class="body">El segundo envío puede salir más caro. Compara otra vez.</p>', 4.2),
            ('<div class="num">3</div><h2>Lee el <em>resumen final</em> antes de confirmar.</h2><p class="body">Ahí ves el monto exacto que va a recibir tu familia.</p>', 4.0),
            (LOGO + '<p class="small">Comparamos las apps cada hora: Western Union, Remitly, Wise, Xoom y más.</p>', 4.4),
        ],
        "caption": [
            "3 cosas que debes revisar antes de mandar dinero 💸", "",
            "1️⃣ Mira cuánto RECIBE tu familia, no solo la comisión. El tipo de cambio también cuesta.",
            "2️⃣ Las promociones casi siempre son solo para el primer envío. El segundo puede salir más caro.",
            "3️⃣ Lee el resumen final antes de confirmar: ahí ves el monto exacto.", "",
            "En Manda Más comparamos las apps cada hora, gratis y en español 👇", "https://mandamasdinero.com", "",
            "¿Le sirve a alguien? Compártelo 🙏", "",
            "#remesas #enviardinero #consejos",
        ],
    },
}


def shoot(url, path):
    for _ in range(2):  # headless Chrome occasionally hangs; one retry
        try:
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--virtual-time-budget=6000",
                            "--force-device-scale-factor=1", "--window-size=1080,1920", f"--screenshot={path}", url],
                           check=True, capture_output=True, timeout=90)
            return
        except subprocess.TimeoutExpired:
            pass
    raise RuntimeError("Chrome timed out twice: " + url)


for slug, v in VIDEOS.items():
    if len(sys.argv) > 1 and slug != sys.argv[1]:
        continue
    out = os.environ.get("OUT_DIR") or os.path.join(HERE, "out", "explainers" + os.environ.get("OUT_SUFFIX", ""), slug)
    os.makedirs(out, exist_ok=True)
    html = os.path.join(out, "slides.html")
    with open(os.path.join(HERE, "explainer.html")) as f:
        open(html, "w").write(f.read().replace("/*SLIDES*/[]", json.dumps([{"html": h} for h, _ in v["slides"]], ensure_ascii=False)))
    manifest = []
    for i, (_, secs) in enumerate(v["slides"]):
        png = os.path.join(out, f"slide{i}.png")
        shoot(f"file://{html}#n={i}", png)
        manifest.append(f"{png}\t{secs}")
    open(os.path.join(out, "manifest.txt"), "w").write("\n".join(manifest))
    subprocess.run(["swift", os.path.join(HERE, "encode.swift"), os.path.join(out, "manifest.txt"), os.path.join(out, "video.mp4")], check=True)
    open(os.path.join(out, "texto.txt"), "w").write("\n".join(v["caption"]) + "\n")
    print(out)
