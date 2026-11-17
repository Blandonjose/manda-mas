"""Evergreen explainer Reels (no dated prices, so they can be posted any week).

usage: python3 make_explainer.py [SLUG]     -> out/explainers/<slug>/{video.mp4, texto.txt}  (all of them without SLUG)
Uses the same Chrome screenshot + encode.swift pipeline as make_reel.py.
"""
import json, os, subprocess, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stock, voice

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
    "promo-primer-envio": {
        "slides": [
            ('<div class="eyebrow">Ojo con las promociones</div><h1>El súper precio casi siempre es <em>solo el primer envío</em>.</h1>', 3.2),
            ('<h2>Muchas apps te dan un mejor tipo de cambio para que te registres.</h2><p class="body">Está bien aprovecharlo 👍</p>', 3.6),
            ('<div class="num">2°</div><h2>Pero en el <em>segundo envío</em> vuelve el precio normal.</h2><p class="body">Y ese precio puede ser peor que el de otras apps.</p>', 4.2),
            ('<h2>Antes de cada envío,</h2><h1><em>compara otra vez.</em></h1>', 3.0),
            (LOGO, 4.4),
        ],
        "caption": [
            "Ojo con las promociones para mandar dinero 👀", "",
            "Muchas apps dan un súper tipo de cambio en el PRIMER envío para que te registres. Está bien aprovecharlo.", "",
            "Pero en el segundo envío vuelve el precio normal, y puede ser peor que el de otras apps.", "",
            "Antes de cada envío, compara otra vez 🙌",
        ],
    },
    "no-pagues-con-tarjeta-de-credito": {
        "slides": [
            ('<div class="eyebrow">Antes de pagar tu envío</div><h1>¿Pagas con <em>tarjeta de crédito</em>? 💳</h1>', 3.0),
            ('<h2>Algunos bancos lo cobran como <em>adelanto en efectivo</em>:</h2><div class="cards">'
             '<div class="card"><div class="top"><span>Una comisión extra</span></div></div>'
             '<div class="card"><div class="top"><span>Intereses desde el primer día</span></div></div></div>', 4.6),
            ('<h2>Y algunas apps también cobran más si pagas con tarjeta.</h2>', 3.4),
            ('<h2>Casi siempre sale más barato pagar</h2><h1>desde tu <em>cuenta de banco</em> o con <em>débito</em>.</h1>', 3.8),
            (LOGO, 4.4),
        ],
        "caption": [
            "¿Pagas tus envíos con tarjeta de crédito? 💳", "",
            "Algunos bancos cobran eso como “adelanto en efectivo”: una comisión extra e intereses desde el primer día. Y algunas apps también cobran más si pagas con tarjeta.", "",
            "Casi siempre sale más barato pagar desde tu cuenta de banco o con tarjeta de débito. Revisa el total en la app antes de confirmar 🙌",
        ],
    },
    "impuesto-1-por-ciento-efectivo": {
        "slides": [
            ('<div class="eyebrow">Desde 2026</div><h1>Si pagas tu envío <em>en efectivo</em>, hay un impuesto de 1%.</h1>', 3.6),
            ('<h2>Aplica cuando pagas con:</h2><div class="cards">'
             '<div class="card"><div class="top"><span>💵 Efectivo</span></div></div>'
             '<div class="card"><div class="top"><span>📄 Money order</span></div></div>'
             '<div class="card"><div class="top"><span>🏦 Cheque de caja</span></div></div></div>', 4.2),
            ('<div class="eyebrow">Ejemplo</div><h2>En un envío de $300 son</h2><div class="num">$3</div><h2>más, solo de impuesto.</h2>', 3.8),
            ('<h2>Si pagas desde tu <em>cuenta de banco</em> o con <em>tarjeta</em>, ese impuesto no se cobra.</h2>', 3.8),
            (LOGO, 4.4),
        ],
        "caption": [
            "Desde 2026, si pagas tu envío en efectivo hay un impuesto federal de 1% 💵", "",
            "Aplica cuando pagas con efectivo, money order o cheque de caja. En un envío de $300 son $3 más.", "",
            "Si pagas desde tu cuenta de banco o con tarjeta, ese impuesto no se cobra.", "",
            "(Información general, no es asesoría de impuestos.)",
        ],
    },
    "el-tipo-de-cambio-real": {
        "slides": [
            ('<div class="eyebrow">Truco rápido</div><h1>¿Cómo saber si una app te da un <em>buen</em> tipo de cambio?</h1>', 3.4),
            ('<h2>Busca en Google “dólar a peso”.</h2><p class="body">Ese es el tipo de cambio de referencia, sin ganancia para nadie.</p>', 4.0),
            ('<div class="eyebrow">Ejemplo con $300</div><div class="cards">'
             '<div class="card"><div class="top"><span>Referencia</span><span>18.50</span></div></div>'
             '<div class="card"><div class="top"><span>La app te da</span><span>18.10</span></div></div></div>'
             '<h2>Son <em>120 pesos</em> menos para tu familia.</h2><p class="small">Ejemplo para explicar. Los precios reales cambian cada día.</p>', 5.0),
            ('<h2>Mientras más cerca de la referencia,</h2><h1><em>mejor</em> para tu familia.</h1>', 3.2),
            (LOGO, 4.4),
        ],
        "caption": [
            "¿Cómo saber si una app te da buen tipo de cambio? 🤔", "",
            "Busca en Google “dólar a peso”: ese es el tipo de cambio de referencia.", "",
            "Ejemplo con $300: si la referencia es 18.50 y la app te da 18.10, tu familia recibe 120 pesos menos.", "",
            "Mientras más cerca de la referencia, mejor. (Ejemplo para explicar; los precios cambian cada día.)",
        ],
    },
    "un-envio-o-varios": {
        "slides": [
            ('<div class="eyebrow">¿Mandas varias veces al mes?</div><h1>Las comisiones <em>se suman</em>.</h1>', 3.0),
            ('<div class="eyebrow">Ejemplo con $3.99 de comisión</div><div class="cards">'
             '<div class="card"><div class="top"><span>3 envíos de $100</span><span>$11.97</span></div></div>'
             '<div class="card good"><div class="top"><span>1 envío de $300</span><span>$3.99</span></div></div></div>'
             '<p class="small">Ejemplo para explicar. Cada app cobra distinto.</p>', 5.0),
            ('<h2>Te ahorras</h2><div class="num">$8</div><h2>con el mismo dinero.</h2>', 3.4),
            ('<h2>Si tu familia puede esperar, junta los envíos chicos en uno.</h2>', 3.4),
            (LOGO, 4.4),
        ],
        "caption": [
            "¿Mandas varias veces al mes? Las comisiones se suman 💸", "",
            "Ejemplo con una comisión de $3.99:",
            "🔸 3 envíos de $100 → $11.97 en comisiones",
            "✅ 1 envío de $300 → $3.99", "",
            "Si tu familia puede esperar, juntar los envíos chicos te ahorra dinero. (Ejemplo para explicar; cada app cobra distinto.)",
        ],
    },
    "deposito-o-efectivo": {
        "slides": [
            ('<div class="eyebrow">¿Cómo recibe tu familia?</div><h1>Depósito en banco o <em>retiro en efectivo</em>.</h1>', 3.2),
            ('<h2>Muchas veces el retiro en efectivo <em>cuesta más</em>.</h2><p class="body">La comisión o el tipo de cambio pueden ser peores.</p>', 4.0),
            ('<h2>Y algunas apps solo depositan en cuenta de banco.</h2><p class="body">Confírmalo antes de elegir.</p>', 3.6),
            ('<h2>Si tu familia tiene cuenta, compara las dos opciones en la app.</h2>', 3.4),
            (LOGO, 4.4),
        ],
        "caption": [
            "¿Tu familia recibe en el banco o retira en efectivo? 🏦💵", "",
            "Muchas veces el retiro en efectivo cuesta más: la comisión o el tipo de cambio pueden ser peores. Y algunas apps solo depositan en cuenta de banco.", "",
            "Si tu familia tiene cuenta, compara las dos opciones en la app antes de mandar 🙌",
        ],
    },
    "nombre-exacto": {
        "slides": [
            ('<div class="eyebrow">Para que no se atore tu envío</div><h1>Escribe el nombre <em>exacto</em>.</h1>', 3.0),
            ('<h2>El nombre debe ser igual al de su identificación.</h2><p class="body">Con los dos apellidos, si los usa.</p>', 3.8),
            ('<h2>Si es depósito, revisa también:</h2><div class="cards">'
             '<div class="card"><div class="top"><span>El banco</span></div></div>'
             '<div class="card"><div class="top"><span>El número de cuenta</span></div></div></div>', 4.0),
            ('<h2>Un error puede <em>retrasar</em> el dinero varios días.</h2>', 3.0),
            (LOGO, 4.4),
        ],
        "caption": [
            "Para que tu envío no se atore ⏳", "",
            "Escribe el nombre exacto como aparece en la identificación de quien recibe, con los dos apellidos si los usa. Si es depósito, revisa el banco y el número de cuenta.", "",
            "Un error puede retrasar el dinero varios días.",
        ],
    },
    "cuidado-con-estafas": {
        "slides": [
            ('<div class="eyebrow">⚠️ Cuidado</div><h1>Nunca mandes dinero a alguien que <em>no conoces</em> en persona.</h1>', 3.6),
            ('<h2>Señales de estafa:</h2><div class="cards">'
             '<div class="card"><div class="top"><span>“Ganaste un premio”</span></div></div>'
             '<div class="card"><div class="top"><span>“Paga para liberar tu dinero”</span></div></div>'
             '<div class="card"><div class="top"><span>Te piden prisa o secreto</span></div></div></div>', 4.8),
            ('<h2>Una vez que se cobra,</h2><h1>casi nunca se puede <em>recuperar</em>.</h1>', 3.2),
            ('<h2>Si dudas, llama a tu familiar a su número de siempre.</h2>', 3.4),
            (LOGO, 4.4),
        ],
        "caption": [
            "⚠️ Nunca mandes dinero a alguien que no conoces en persona", "",
            "Señales de estafa: “ganaste un premio”, “paga para liberar tu dinero”, o te piden prisa o secreto.", "",
            "Una vez que el dinero se cobra, casi nunca se puede recuperar. Si alguien dice ser tu familiar y pide dinero, llámale a su número de siempre.", "",
            "Compártelo con alguien que lo necesite 🙏",
        ],
    },
    "tus-derechos-al-enviar": {
        "slides": [
            ('<div class="eyebrow">Tus derechos al enviar desde EE. UU.</div><h1>Guarda tu <em>recibo</em>.</h1>', 3.0),
            ('<h2>En la mayoría de los casos tienes</h2><div class="num">30 min</div><h2>para cancelar el envío.</h2>', 4.0),
            ('<h2>Y hasta</h2><div class="num">180 días</div><h2>para reportar un error.</h2>', 3.8),
            ('<h2>El recibo trae el número de envío y lo que debe recibir tu familia.</h2><p class="body">Sin él es más difícil reclamar.</p>', 4.0),
            (LOGO, 4.4),
        ],
        "caption": [
            "Tus derechos al mandar dinero desde Estados Unidos 📄", "",
            "Con la regla federal de envíos de dinero, en la mayoría de los casos tienes 30 minutos para cancelar y hasta 180 días para reportar un error.", "",
            "Guarda tu recibo: trae el número de envío y lo que debe recibir tu familia. Sin él es más difícil reclamar.", "",
            "(Información general, no es asesoría legal.)",
        ],
    },
    "el-precio-cambia-cada-dia": {
        "slides": [
            ('<div class="eyebrow">¿Siempre usas la misma app?</div><h1>La que más entrega <em>cambia</em>.</h1>', 3.0),
            ('<h2>Las apps cambian su tipo de cambio todos los días.</h2><p class="body">A veces varias veces al día.</p>', 3.6),
            ('<h2>La que ganó la semana pasada</h2><h1>hoy puede ser <em>la peor</em>.</h1>', 3.2),
            ('<h2>Compara el mismo día que vas a mandar.</h2><p class="body">Toma menos de un minuto.</p>', 3.4),
            (LOGO + '<p class="small">Actualizamos los precios cada hora.</p>', 4.4),
        ],
        "caption": [
            "¿Siempre mandas con la misma app? 🤔", "",
            "Las apps cambian su tipo de cambio todos los días, a veces varias veces al día. La que más entregó la semana pasada hoy puede ser la peor.", "",
            "Compara el mismo día que vas a mandar. Toma menos de un minuto 🙌",
        ],
    },
}


# What the voice says on each slide (the last slide, the logo, always says voice.END_LINE).
NARRATION = {
    "sin-comision-no-es-gratis": [
        "Ojo antes de mandar dinero. Sin comisión no quiere decir gratis.",
        "Las apps ganan de dos formas: con la comisión, que sí ves, y con el tipo de cambio, que casi no se ve.",
        "Un ejemplo con 300 dólares a México. Una app sin comisión te da 18 pesos por dólar, y tu familia recibe 5400. Otra cobra 3 dólares, pero te da 18.45, y tu familia recibe 5480.",
        "La que cobra comisión entrega 80 pesos más. Lo que importa es cuánto recibe tu familia.",
    ],
    "3-cosas-antes-de-mandar": [
        "Tres cosas que debes revisar antes de mandar dinero, para que a tu familia le llegue más.",
        "Uno: mira cuánto recibe tu familia, no solo la comisión. El tipo de cambio también cuesta.",
        "Dos: las promociones casi siempre son solo para el primer envío. El segundo puede salir más caro.",
        "Tres: lee el resumen final antes de confirmar. Ahí ves el monto exacto que va a recibir tu familia.",
    ],
    "promo-primer-envio": [
        "Ojo con las promociones. El súper precio casi siempre es solo para el primer envío.",
        "Muchas apps te dan un mejor tipo de cambio para que te registres. Está bien aprovecharlo.",
        "Pero en el segundo envío vuelve el precio normal, y puede ser peor que el de otras apps.",
        "Así que antes de cada envío, compara otra vez.",
    ],
    "no-pagues-con-tarjeta-de-credito": [
        "¿Pagas tus envíos con tarjeta de crédito? Ojo.",
        "Algunos bancos lo cobran como adelanto en efectivo: con una comisión extra, y con intereses desde el primer día.",
        "Y algunas apps también cobran más si pagas con tarjeta.",
        "Casi siempre sale más barato pagar desde tu cuenta de banco, o con tarjeta de débito.",
    ],
    "impuesto-1-por-ciento-efectivo": [
        "Desde 2026, si pagas tu envío en efectivo, hay un impuesto federal de uno por ciento.",
        "Aplica cuando pagas con efectivo, con money order, o con cheque de caja.",
        "En un envío de 300 dólares, son 3 dólares más, solo de impuesto.",
        "Si pagas desde tu cuenta de banco o con tarjeta, ese impuesto no se cobra.",
    ],
    "el-tipo-de-cambio-real": [
        "¿Cómo saber si una app te da un buen tipo de cambio?",
        "Busca en Google: dólar a peso. Ese es el tipo de cambio de referencia.",
        "Por ejemplo, si la referencia es 18.50, y la app te da 18.10, en 300 dólares tu familia recibe 120 pesos menos.",
        "Mientras más cerca de la referencia, mejor para tu familia.",
    ],
    "un-envio-o-varios": [
        "¿Mandas dinero varias veces al mes? Las comisiones se suman.",
        "Por ejemplo, con una comisión de 3.99, tres envíos de 100 dólares cuestan casi 12 dólares en comisiones. Un solo envío de 300 cuesta 3.99.",
        "Te ahorras unos 8 dólares, con el mismo dinero.",
        "Si tu familia puede esperar, junta los envíos chicos en uno.",
    ],
    "deposito-o-efectivo": [
        "¿Tu familia recibe en el banco, o retira en efectivo?",
        "Muchas veces el retiro en efectivo cuesta más: la comisión o el tipo de cambio pueden ser peores.",
        "Y algunas apps solo depositan en cuenta de banco. Confírmalo antes de elegir.",
        "Si tu familia tiene cuenta, compara las dos opciones en la app.",
    ],
    "nombre-exacto": [
        "Para que no se atore tu envío, escribe el nombre exacto.",
        "Tiene que ser igual al de su identificación, con los dos apellidos si los usa.",
        "Y si es depósito, revisa también el banco y el número de cuenta.",
        "Un error puede retrasar el dinero varios días.",
    ],
    "cuidado-con-estafas": [
        "Cuidado. Nunca mandes dinero a alguien que no conoces en persona.",
        "Señales de estafa: te dicen que ganaste un premio, te piden pagar para liberar tu dinero, o te piden prisa o secreto.",
        "Una vez que el dinero se cobra, casi nunca se puede recuperar.",
        "Si alguien dice ser tu familiar y te pide dinero, llámale a su número de siempre.",
    ],
    "tus-derechos-al-enviar": [
        "Tus derechos al mandar dinero desde Estados Unidos. Primero: guarda tu recibo.",
        "En la mayoría de los casos, tienes 30 minutos para cancelar el envío.",
        "Y hasta 180 días para reportar un error.",
        "El recibo trae el número de envío y lo que debe recibir tu familia. Sin él, es más difícil reclamar.",
    ],
    "el-precio-cambia-cada-dia": [
        "¿Siempre mandas con la misma app? La que más entrega cambia.",
        "Las apps cambian su tipo de cambio todos los días, y a veces varias veces al día.",
        "La que ganó la semana pasada, hoy puede ser la peor.",
        "Compara el mismo día que vas a mandar. Toma menos de un minuto.",
    ],
}


def shoot(url, path):
    for _ in range(2):  # headless Chrome occasionally hangs; one retry
        try:
            subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--virtual-time-budget=6000",
                            "--force-device-scale-factor=1", "--default-background-color=00000000", "--window-size=1080,1920", f"--screenshot={path}", url],
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
    lines = [voice.END_LINE + (" El link está en nuestro perfil." if "perfil" in os.environ.get("TAP", "") else "")
             if 'class="logo"' in h else NARRATION[slug][i] for i, (h, _) in enumerate(v["slides"])]
    clips, said = [], []
    for i, line in enumerate(lines):
        if voice.ENABLED:
            path = os.path.join(out, f"voz{i}.m4a")
            said.append(voice.speak(line, path))
            clips.append(path)
        else:
            said.append(0)
    secs_all, starts = voice.fit([([s], d) for (_, s), d in zip(v["slides"], said)])
    bg = [] if os.environ.get("NOSTOCK") else stock.clips(len(secs_all))  # real people behind each slide
    manifest = []
    for i, secs in enumerate(secs_all):
        png = os.path.join(out, f"slide{i}.png")
        shoot(f"file://{html}#n={i}" + ("&bg=1" if bg else ""), png)
        manifest.append(f"{png}\t{secs}" + (f"\t{bg[i % len(bg)]}" if bg else ""))
    open(os.path.join(out, "manifest.txt"), "w").write("\n".join(manifest))
    final = os.path.join(out, "video.mp4")
    silent = os.path.join(out, "silent.mp4") if clips else final
    subprocess.run(["swift", os.path.join(HERE, "encode.swift"), os.path.join(out, "manifest.txt"), silent], check=True)
    if clips:
        voice.mux(silent, list(zip(clips, starts)), final)
        os.remove(silent)
    open(os.path.join(out, "narracion.txt"), "w").write("\n".join(lines) + "\n")
    open(os.path.join(out, "texto.txt"), "w").write("\n".join(v["caption"]) + "\n")
    print(out)
