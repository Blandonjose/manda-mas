"""Make today's three social videos (noon country, 3 PM tip, 6 PM country) with captions for YouTube, Instagram and Facebook.

usage: python3 social/daily.py [YYYY-MM-DD]
Writes  ~/Desktop/Manda Más – promociones/videos auto/<date>/
          1-mediodia/, 2-tarde/, 3-noche/   each with video.mp4, youtube.txt, instagram.txt, facebook.txt
          plan.json    what was made, for which time, and why some countries were skipped
          LÉEME.txt    the same in plain Spanish
Set MANDAMAS_OUT to write somewhere else. Needs Google Chrome and Swift (both on this Mac). Videos are narrated with the Mac's Spanish voice
(social/voice.py; VOICE=Name to change it, NOVOICE=1 for silent videos).
With a free Pexels key (social/stock.py) real people from stock footage play behind the numbers;
without one, the videos keep the plain blue background. NOSTOCK=1 turns the footage off.

Country videos use the live prices on mandamasdinero.com, so run it on the day of posting.
make_reel.py refuses a country when Wise/Instarem don't beat Western Union/Remitly or the gap is
under 0.5%; daily.py then moves on to the next country in the rotation. The 3 PM slot is an
evergreen tip; the twelve tips rotate, so each one comes back every twelve days.
"""
import json, os, re, shutil, subprocess, sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
# Countries that are often skipped (Western Union wins, or the gap is small) sit between the others,
# so a skip moves to a different country instead of always falling through to the same one.
COUNTRIES = [("MX", "México", "Mexico"), ("HN", "Honduras", "Honduras"), ("GT", "Guatemala", "Guatemala"),
             ("BO", "Bolivia", "Bolivia"), ("DO", "República Dominicana", "Republica-Dominicana"), ("CR", "Costa Rica", "Costa-Rica"),
             ("CO", "Colombia", "Colombia"), ("PE", "Perú", "Peru"), ("CL", "Chile", "Chile"), ("UY", "Uruguay", "Uruguay")]
TIPS = {"sin-comision-no-es-gratis": "“Sin comisión” NO quiere decir gratis al mandar dinero 👀 #shorts",
        "promo-primer-envio": "La promoción para mandar dinero casi siempre es solo el primer envío 👀 #shorts",
        "impuesto-1-por-ciento-efectivo": "Impuesto de 1% si pagas tu envío de dinero en efectivo (2026) 💵 #shorts",
        "3-cosas-antes-de-mandar": "3 cosas que debes revisar antes de mandar dinero 💸 #shorts",
        "el-tipo-de-cambio-real": "Cómo saber si una app te da buen tipo de cambio 🤔 #shorts",
        "no-pagues-con-tarjeta-de-credito": "¿Mandar dinero con tarjeta de crédito? Ojo con este cobro 💳 #shorts",
        "un-envio-o-varios": "Mandar dinero: un envío grande o varios chicos 💸 #shorts",
        "cuidado-con-estafas": "Cuidado con estas estafas al mandar dinero ⚠️ #shorts",
        "deposito-o-efectivo": "Mandar dinero: ¿depósito en banco o retiro en efectivo? 🏦 #shorts",
        "tus-derechos-al-enviar": "Tus derechos al mandar dinero desde Estados Unidos 📄 #shorts",
        "nombre-exacto": "Para que no se atore tu envío de dinero ⏳ #shorts",
        "el-precio-cambia-cada-dia": "La app que más entrega cambia cada día 📈 #shorts"}
# Seasonal tips: YouTube titles, and the days the 3 PM tip is one of them (other days keep the normal rotation).
SEASONAL = {"navidad-fechas": "Mandar dinero para Navidad: la fecha para que llegue antes del 24 🎄 #shorts",
            "navidad-envio-grande": "En diciembre mandamos más: así rinde más tu envío 🎄 #shorts",
            "navidad-estafas": "Cuidado con estas estafas de fin de año al mandar dinero ⚠️ #shorts",
            "ano-nuevo-fechas": "Mandar dinero para Año Nuevo: la fecha para que llegue antes del 31 🎆 #shorts"}
SEASON_DAYS = {"2026-12-02": "navidad-fechas", "2026-12-04": "navidad-envio-grande", "2026-12-06": "navidad-estafas",
               "2026-12-08": "navidad-fechas", "2026-12-10": "navidad-envio-grande", "2026-12-12": "navidad-estafas",
               "2026-12-14": "navidad-fechas", "2026-12-16": "navidad-envio-grande", "2026-12-18": "navidad-fechas",
               "2026-12-20": "navidad-estafas", "2026-12-21": "navidad-fechas", "2026-12-24": "ano-nuevo-fechas",
               "2026-12-26": "navidad-estafas", "2026-12-28": "ano-nuevo-fechas", "2026-12-30": "navidad-envio-grande"}
TAP = "🔗 Link en el perfil"
DISC = "Manda Más es gratis. Algunas apps nos pueden pagar una comisión si te registras desde nuestra página, sin costo para ti."


def flag(code):
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code)


def captions(folder, yt_title, body, tag):
    yt = f"TÍTULO:\n{yt_title}\n\nDESCRIPCIÓN:\n{body}\n\nCompara gratis: https://mandamasdinero.com\n\n{DISC}\n\n#remesas #enviardinero #{tag} #shorts\n"
    ig_tags = f"#remesas #enviardinero #{tag} #latinosenusa #tipodecambio"  # Instagram allows 5 hashtags
    ig = f"{body}\n\n🔗 Compara gratis con el link de nuestro perfil: mandamasdinero.com\n\n{DISC}\n\n{ig_tags}\n"
    fb = f"{body}\n\nCompara gratis 👇\nhttps://mandamasdinero.com\n\n{DISC}\n\n{ig_tags}\n"
    for name, text in (("youtube.txt", yt), ("instagram.txt", ig), ("facebook.txt", fb)):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
            f.write(text)


def country_video(code, name, slug, folder):
    env = dict(os.environ, TAP=TAP, OUT_DIR=folder)
    p = subprocess.run([sys.executable, os.path.join(HERE, "make_reel.py"), code, "300"], env=env, capture_output=True, text=True)
    if p.returncode != 0:
        shutil.rmtree(folder, ignore_errors=True)
        return (p.stderr.strip().splitlines() or ["error"])[-1]
    cap = open(os.path.join(folder, "caption.txt"), encoding="utf-8").read()
    body = (cap.split("Los precios cambian cada día")[0].strip()
            + "\n\nLos precios cambian cada día. Son estimaciones; el precio final lo ves en la app antes de confirmar.")
    shutil.move(os.path.join(folder, "reel.mp4"), os.path.join(folder, "video.mp4"))
    keep = {"video.mp4", "post.png"}
    for f in os.listdir(folder):
        if f not in keep:
            os.remove(os.path.join(folder, f))
    # Title starts with the words people search for.
    captions(folder, f"Enviar dinero a {name}: cuánto llega con cada app ($300) {flag(code)} #shorts", body, re.sub(r"\W", "", slug.lower()))
    return None


def tip_video(slug, folder):
    env = dict(os.environ, TAP=TAP, OUT_DIR=folder)
    subprocess.run([sys.executable, os.path.join(HERE, "make_explainer.py"), slug], env=env, check=True, capture_output=True)
    text = open(os.path.join(folder, "texto.txt"), encoding="utf-8").read()
    body = re.sub(r"\n(Compara gratis y en español 👇|En Manda Más comparamos las apps cada hora, gratis y en español 👇)\nhttps://mandamasdinero.com\n", "\n", text)
    body = re.sub(r"\n#.*\n?$", "", body).strip()
    for f in os.listdir(folder):
        if f != "video.mp4":
            os.remove(os.path.join(folder, f))
    captions(folder, TIPS.get(slug) or SEASONAL[slug], body, "consejos")


def main():
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    base = os.environ.get("MANDAMAS_OUT") or os.path.expanduser("~/Desktop/Manda Más – promociones/videos auto")
    out = os.path.join(base, day.isoformat())
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    n = day.toordinal()
    slots = [("1-mediodia", "12:00 pm"), ("2-tarde", "3:00 pm"), ("3-noche", "6:00 pm")]
    plan, skipped, made = [], [], set()
    tips = list(TIPS)
    tip_today = tips[n % len(tips)]
    tip_today = SEASON_DAYS.get(day.isoformat(), tip_today)
    for i, (folder_name, time) in enumerate(slots):
        folder = os.path.join(out, folder_name)
        if folder_name == "2-tarde":
            tip_video(tip_today, folder)
            plan.append({"slot": folder_name, "time": time, "video": "consejo: " + tip_today})
            continue
        start = (2 * n + (i > 0)) % len(COUNTRIES)
        for k in range(len(COUNTRIES)):
            code, name, slug = COUNTRIES[(start + k) % len(COUNTRIES)]
            if code in made or any(s["country"] == code for s in skipped):
                continue
            why = country_video(code, name, slug, folder)
            if why:
                skipped.append({"country": code, "why": why})
                continue
            made.add(code)
            plan.append({"slot": folder_name, "time": time, "video": name})
            break
        else:
            tip_video(tips[(n + 1 + i) % len(tips)], folder)  # never the same tip as 2-tarde
            plan.append({"slot": folder_name, "time": time, "video": "consejo (ningún país pasó el filtro)"})
    with open(os.path.join(out, "plan.json"), "w", encoding="utf-8") as f:
        json.dump({"date": day.isoformat(), "posts": plan, "skipped": skipped}, f, ensure_ascii=False, indent=2)
    lines = [f"VIDEOS DE HOY — {day.isoformat()}", "", "Publicar en YouTube Shorts, Instagram Reels y Facebook Reels (Página Manda Más):", ""]
    lines += [f"{p['time']:>9}  {p['slot']}  →  {p['video']}" for p in plan]
    if skipped:
        lines += ["", "Países sin video hoy:"] + [f"  {s['country']}: {s['why']}" for s in skipped]
    lines += ["", "Cada carpeta: video.mp4 + youtube.txt + instagram.txt + facebook.txt. Copiar los textos tal cual."]
    with open(os.path.join(out, "LÉEME.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(out)


main()
