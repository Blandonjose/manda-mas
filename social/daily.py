"""Make today's two social videos (noon and 6 PM) with captions for YouTube, Instagram and Facebook.

usage: python3 social/daily.py [YYYY-MM-DD]
Writes  ~/Desktop/Manda Más – promociones/videos auto/<date>/
          1-mediodia/  and  2-tarde/   each with video.mp4, youtube.txt, instagram.txt, facebook.txt
          plan.json    what was made, for which time, and why some countries were skipped
          LÉEME.txt    the same in plain Spanish
Set MANDAMAS_OUT to write somewhere else. Needs Google Chrome and Swift (both on this Mac).

Country videos use the live prices on mandamasdinero.com, so run it on the day of posting.
make_reel.py refuses a country when Wise/Instarem don't beat Western Union/Remitly or the gap is
under 0.5%; daily.py then moves on to the next country in the rotation. Wednesdays and Saturdays
the noon slot is an evergreen tip instead of a country.
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
        "3-cosas-antes-de-mandar": "3 cosas que debes revisar antes de mandar dinero 💸 #shorts"}
TAP = "🔗 Link en el perfil"
DISC = "Manda Más es gratis. Algunas apps nos pueden pagar una comisión si te registras desde nuestra página, sin costo para ti."


def flag(code):
    return "".join(chr(0x1F1E6 + ord(c) - 65) for c in code)


def captions(folder, yt_title, body, tag):
    yt = f"TÍTULO:\n{yt_title}\n\nDESCRIPCIÓN:\n{body}\n\nCompara gratis: https://mandamasdinero.com\n\n{DISC}\n\n#remesas #enviardinero #{tag} #shorts\n"
    ig_tags = f"#remesas #enviardinero #{tag} #latinosenusa #dinero #tipodecambio"
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
    captions(folder, f"¿Mandas $300 a {name}? Cuánto llega con cada app {flag(code)} #shorts", body, re.sub(r"\W", "", slug.lower()))
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
    captions(folder, TIPS[slug], body, "consejos")


def main():
    day = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    base = os.environ.get("MANDAMAS_OUT") or os.path.expanduser("~/Desktop/Manda Más – promociones/videos auto")
    out = os.path.join(base, day.isoformat())
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    n = day.toordinal()
    slots = [("1-mediodia", "12:00 pm"), ("2-tarde", "6:00 pm")]
    plan, skipped, made = [], [], set()
    tip_day = day.weekday() in (2, 5)  # Wednesday, Saturday
    for i, (folder_name, time) in enumerate(slots):
        folder = os.path.join(out, folder_name)
        if i == 0 and tip_day:
            slug = list(TIPS)[(n // 7 + (day.weekday() == 5)) % len(TIPS)]  # Wednesday and Saturday get different tips
            tip_video(slug, folder)
            plan.append({"slot": folder_name, "time": time, "video": "consejo: " + slug})
            continue
        start = (2 * n + i) % len(COUNTRIES)
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
            tip_video(list(TIPS)[(n + i) % len(TIPS)], folder)
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
