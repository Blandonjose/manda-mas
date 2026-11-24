"""Collect estimated USD -> Latin America remittance quotes and write them into index.html.

Run:  python3 remesas/update_rates.py
Sources (public, no keys): Wise's provider-comparison feed (10+ money-transfer services)
and Bitso's USDT order books for the stablecoin route. Run it on a schedule (e.g. hourly)
once the page is hosted, so the prices stay fresh.
"""
import html as html_mod
import json
import os
import re
import shutil
import statistics
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
PAGE = os.path.join(HERE, "index.html")

# Fees change with the amount sent, so we sample several amounts and interpolate in the page.
BRACKETS = [50, 100, 150, 200, 250, 300, 400, 500, 600, 750, 1000, 1500, 2000]

# Analytics (Umami Cloud, no cookies). Paste the Website ID from Umami (Settings -> Websites -> Edit)
# here. Left empty, no analytics script is added and no events are sent. See ANALYTICS.md.
UMAMI_WEBSITE_ID = "24dc3526-7c1d-4cf6-81f9-ee6ef3fd8045"
UMAMI_DOMAIN = "mandamasdinero.com"   # Umami ignores visits on any other host, such as localhost

COUNTRIES = [
    # code, name, currency, currency name (plural), Bitso book for the stablecoin route
    ("MX", "México", "MXN", "pesos", "usdt_mxn"),
    ("GT", "Guatemala", "GTQ", "quetzales", None),
    ("HN", "Honduras", "HNL", "lempiras", None),
    ("SV", "El Salvador", "USD", "dólares", None),
    ("DO", "República Dominicana", "DOP", "pesos dominicanos", None),
    ("CO", "Colombia", "COP", "pesos colombianos", "usdt_cop"),
    ("CR", "Costa Rica", "CRC", "colones", None),
    ("PE", "Perú", "PEN", "soles", None),
    ("CL", "Chile", "CLP", "pesos chilenos", None),
    ("BO", "Bolivia", "BOB", "bolivianos", None),
    ("UY", "Uruguay", "UYU", "pesos uruguayos", None),
]


def get_json(url, params):
    url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (remesas-comparador)"})
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except Exception as e:
            err = e
            time.sleep(2 + 3 * attempt)
    raise err


def wise_quotes(currency, country, amount):
    data = get_json("https://api.wise.com/v3/comparisons/", {
        "sourceCountry": "US", "sourceCurrency": "USD", "targetCurrency": currency,
        "targetCountry": country, "sendAmount": amount})
    out = []
    for p in data.get("providers", []):
        q = (p.get("quotes") or [None])[0]
        if not q or not q.get("rate"):
            continue
        out.append({"name": p["name"], "fee": q["fee"], "rate": q["rate"],
                    "markup": q.get("markup") or 0.0, "at": q.get("dateCollected")})
    return out


def collect():
    result = {"collected": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "brackets": BRACKETS, "countries": []}
    for code, name, cur, cur_name, book in COUNTRIES:
        providers, mids = {}, []
        for amount in BRACKETS:
            for q in wise_quotes(cur, code, amount):
                providers.setdefault(q["name"], {})[str(amount)] = {
                    "fee": q["fee"], "rate": q["rate"], "markup": q["markup"], "at": q["at"]}
                if q["markup"] < 50:
                    mids.append(q["rate"] / (1 - q["markup"] / 100))
            time.sleep(0.3)
        country = {"code": code, "name": name, "currency": cur, "currencyName": cur_name,
                   "mid": statistics.median(mids) if mids else (1.0 if cur == "USD" else None),
                   "providers": providers, "stablecoin": None}
        if book:
            t = get_json("https://api.bitso.com/v3/ticker/", {"book": book})["payload"]
            country["stablecoin"] = {"source": "Bitso " + book.upper().replace("_", "/"), "bid": float(t["bid"])}
        print(f"{name:<22} {len(providers):>2} services" + (f", stablecoin {country['stablecoin']['bid']}" if book else ""))
        result["countries"].append(country)
    return result


SLUGS = {"MX": "mexico", "GT": "guatemala", "HN": "honduras", "SV": "el-salvador",
         "DO": "republica-dominicana", "CO": "colombia", "CR": "costa-rica",
         "PE": "peru", "CL": "chile", "BO": "bolivia", "UY": "uruguay"}
FAVICON = ("data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22%3E"
           "%3Crect width=%2232%22 height=%2232%22 rx=%227%22 fill=%22%230b2a5b%22/%3E%3Ctext x=%2216%22 y=%2224%22 "
           "font-size=%2222%22 font-family=%22Arial%22 font-weight=%22700%22 text-anchor=%22middle%22 fill=%22white%22%3E$%3C/text%3E%3C/svg%3E")
RESET = ("<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
         "body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}[hidden]{display:none!important}</style>")


def esc(s):
    return html_mod.escape(s, quote=True)


def faq_items(page):
    """Pull the static FAQ out of the page so Google's structured data always matches what people see."""
    out = []
    for q, a in re.findall(r"<details>\s*<summary>(.*?)</summary>\s*<p>(.*?)</p>\s*</details>", page, re.S):
        out.append({"@type": "Question", "name": html_mod.unescape(q.strip()),
                    "acceptedAnswer": {"@type": "Answer", "text": html_mod.unescape(a.strip())}})
    return out


def page_meta(data, country, base):
    names = [c["name"] for c in data["countries"] if c["providers"]]
    if not country:
        return {
            "path": "",
            "title": "Manda Más: compara envíos de dinero a México y Latinoamérica",
            "desc": "Compara estimaciones actualizadas de cuánto recibe tu familia con Remitly, Western Union, Xoom, Wise y más. "
                    "Envíos de dinero desde Estados Unidos a " + ", ".join(names[:-1]) + " y " + names[-1] + ".",
            "lede": "Mira cuánto puede recibir tu familia con cada servicio al mandar dinero desde Estados Unidos. Comparamos Remitly, Western Union, "
                    f"Xoom, Wise y más para envíos a México y {len(names) - 1} países más de Latinoamérica.",
        }
    known = ["Remitly", "Western Union", "Xoom", "Wise", "Instarem", "WorldRemit", "PayPal", "OFX"]
    provs = sorted(country["providers"], key=lambda n: (known.index(n) if n in known else len(known), n))
    if len(provs) > 4:
        shown = ", ".join(provs[:4]) + " y más"
    elif len(provs) > 1:
        shown = ", ".join(provs[:-1]) + " y " + provs[-1]
    else:
        shown = provs[0]
    return {
        "path": SLUGS[country["code"]] + "/",
        "title": (f"Enviar dinero a {country['name']} desde USA: cuánto llega hoy con cada app | Manda Más" if len(provs) > 1
                  else f"Enviar dinero a {country['name']} desde USA: cuánto llega hoy | Manda Más"),
        "desc": f"¿Cuál es la forma más barata de mandar dinero a {country['name']}? Compara estimaciones actualizadas de {shown} "
                f"y mira cuántos {country['currencyName']} puede recibir tu familia.",
        "lede": f"Mira cuántos {country['currencyName']} puede recibir tu familia en {country['name']} con cada servicio "
                f"al mandar dinero desde Estados Unidos. Comparamos {shown}.",
    }


def fair_rows(c, amount):
    """Services to name as "the one that delivers the most": no banks (customers only), no first-transfer promos."""
    return [r for r in ranked(c, amount) if r["name"] not in BANKS and r["markup"] >= -0.1]


def country_guide(code):
    slug = "forma-mas-barata-mandar-dinero-a-mexico" if code == "MX" else "mandar-dinero-a-" + SLUGS[code]
    return slug if slug in GUIDES else None


def country_lede(data, c, amount=300):
    rows, cur, day = fair_rows(c, amount), esc(c["currencyName"]), fecha(data["collected"])
    if not rows:
        return None
    best = rows[0]
    if len(rows) == 1:
        text = (f"Hoy ({day}) tenemos el precio estimado de {esc(best['name'])} para envíos de ${amount} a {esc(c['name'])} "
                f"desde Estados Unidos: tu familia recibiría unos <b>{local_amount(best['received'], c)} {cur}</b>.")
        if c["currency"] == "USD":
            text += (f" En {esc(c['name'])} se usa el dólar, así que no hay tipo de cambio: lo que cambia entre servicios es la comisión "
                     "y la forma de recibir. Antes de enviar, revisa también Remitly, Western Union y Xoom en su app.")
        return text
    worst = rows[-1]
    promo = any(r["markup"] < -0.1 and r["received"] > best["received"] and r["name"] not in BANKS for r in ranked(c, amount))
    return (f"Hoy ({day}), al mandar ${amount} a {esc(c['name'])} desde Estados Unidos, <b>{esc(best['name'])}</b> es la opción que "
            f"más entrega: unos <b>{local_amount(best['received'], c)} {cur}</b>"
            + (" (sin contar promociones de primer envío)" if promo else "")
            + f". {esc(worst['name'])} entrega unos {local_amount(worst['received'], c)}: "
            f"{local_amount(best['received'] - worst['received'], c)} {cur} menos por el mismo envío. "
            f"Comparamos {len(ranked(c, amount))} servicios; las cifras son estimaciones.")


def country_faq(data, c):
    """Three questions about this country, answered with today's numbers (shown on the page and sent to Google)."""
    pais, cur, day = esc(c["name"]), esc(c["currencyName"]), fecha(data["collected"])
    rows, out = fair_rows(c, 300), []
    if len(rows) > 1:
        b, w = rows[0], rows[-1]
        out.append((f"¿Cuál es la app que más entrega para enviar dinero a {pais}?",
                    f"Hoy ({day}), con un envío de $300, {esc(b['name'])} entrega unos {local_amount(b['received'], c)} {cur} y "
                    f"{esc(w['name'])} unos {local_amount(w['received'], c)}. Sin contar promociones de primer envío. "
                    "La que más entrega cambia según el día y el monto, así que conviene comparar antes de cada envío. Son estimaciones."))
    elif c["currency"] == "USD":
        out.append((f"¿Hay tipo de cambio al mandar dinero a {pais}?",
                    f"No. En {pais} se usa el dólar, así que tu familia recibe dólares. Lo que cambia entre servicios es la comisión y la "
                    f"forma de recibir (cuenta de banco o efectivo). Por ahora nuestros datos solo incluyen el precio de "
                    + ", ".join(esc(r["name"]) for r in rows) + f" para {pais}; antes de enviar, revisa también otros servicios en su app."))
    parts = []
    for amt in (100, 500, 1000):
        r = fair_rows(c, amt)
        if r:
            parts.append(f"con ${amt:,}, {esc(r[0]['name'])} (unos {local_amount(r[0]['received'], c)} {cur})")
    if parts:
        out.append((f"¿Cuánto llega si mando $100, $500 o $1,000 a {pais}?",
                    f"Hoy ({day}), la opción que más entrega es: " + "; ".join(parts) + ". Escribe tu monto exacto arriba para ver "
                    "todas las opciones. Son estimaciones: el precio final lo ves en la app antes de confirmar."))
    r = {x["name"]: x for x in ranked(c, 300)}
    if "Remitly" in r and "Wise" in r:
        win, lose = (r["Wise"], r["Remitly"]) if r["Wise"]["received"] >= r["Remitly"]["received"] else (r["Remitly"], r["Wise"])
        out.append((f"¿Remitly o Wise para mandar dinero a {pais}?",
                    f"Hoy, con $300, {esc(win['name'])} entrega más: unos {local_amount(win['received'], c)} {cur}, frente a "
                    f"{local_amount(lose['received'], c)} con {esc(lose['name'])}. Wise deposita en cuenta de banco; Remitly en muchos "
                    'países también permite recoger en efectivo. <a href="/guias/remitly-vs-wise/">Ver Remitly vs Wise en todos los países</a>.'))
    return "".join(f"<details><summary>{q}</summary><p>{a}</p></details>" for q, a in out)


def static_rows(c, amount, links, aff):
    """The ranking for $300 written into the page, so it is there before the script runs (and for Google).
    renderList() in index.html replaces it with the live, interactive list."""
    out = ""
    for i, r in enumerate(ranked(c, amount), 1):
        pills = ('<span class="pill best">Recibe más</span>' if i == 1 else "") + \
                ('<span class="pill promo">Promoción, casi siempre solo el primer envío</span>' if r["markup"] < -0.1 else "") + \
                ('<span class="pill">Solo clientes del banco</span>' if r["name"] in BANKS else "")
        money = "dólares" if c["currency"] == "USD" else f'{esc(c["currencyName"])} · ${r["received"] / c["mid"]:,.2f}'
        cost = f'comisión ${r["fee"]:,.2f}' + ("" if c["currency"] == "USD" else f' + cambio ${max(0, r["fx"]):,.2f}')
        go = ""
        if r["name"] in links:
            go = (f'<span class="go-wrap"><a class="go" href="{esc(links[r["name"]])}" target="_blank" rel="noopener sponsored" '
                  f'data-service="{esc(r["name"])}" data-rank="{i}" data-location="results">Ir a {esc(r["name"].replace(" (US)", ""))} ↗</a>'
                  + ('<small class="aff-tag">Enlace de afiliado</small>' if r["name"] in aff else "") + "</span>")
        out += (f'<li class="row{" best" if i == 1 else ""}"><div class="row-top"><span class="rank num">{i}</span><div class="who">'
                f'<h3>{esc(r["name"])}</h3>' + (f'<div class="pills">{pills}</div>' if pills else "") + '</div><div class="gets">'
                f'<strong class="num">{local_amount(r["received"], c)}</strong><span class="num">{money}</span></div></div>'
                f'<div class="row-bottom"><p class="cost num">Te cuesta <b>${max(0, r["fee"] + r["fx"]):,.2f}</b> ({cost})</p>{go}</div></li>')
    return out


def build_page(page, data, country, base, nav):
    m = page_meta(data, country, base)
    url = base + m["path"] if base else None
    head_end = page.index('<div class="wrap">')
    head, body = page[:head_end], page[head_end:]
    head = re.sub(r"<title>.*?</title>\s*", "", head, flags=re.S)
    head = re.sub(r'<meta name="description"[^>]*>\s*', "", head)
    body = re.sub(r'(<p class="lede" id="lede">).*?(</p>)', lambda x: x.group(1) + esc(m["lede"]) + x.group(2), body, flags=re.S)
    body = body.replace("<!--COUNTRY_LINKS-->", nav)
    live = [c for c in data["countries"] if c["providers"]]
    if country:
        links, aff = page_links(page)
        name = esc(country["name"])
        body = body.replace('<h1>Que llegue <em>más dinero</em> a tu familia</h1>',
                            f'<h1 class="country-h1">Enviar dinero a {name} desde Estados Unidos</h1>'
                            '<p class="h1-sub">Que llegue <em>más dinero</em> a tu familia</p>', 1)
        lede = country_lede(data, country)
        if lede:
            body = re.sub(r'(<p class="lede" id="lede">).*?(</p>)', lambda x: x.group(1) + lede + x.group(2), body, count=1, flags=re.S)
        body = body.replace('<ol class="list" id="list"></ol>', f'<ol class="list" id="list">{static_rows(country, 300, links, aff)}</ol>', 1)
        extra = []
        if app_links_html(data, country):
            extra.append('<p class="app-links"><b>Precio de hoy por app:</b> ' + app_links_html(data, country) + '</p>')
        guides = []
        if country_guide(country["code"]):
            guides.append(f'<a href="/guias/{country_guide(country["code"])}/">Cómo mandar dinero a {name}</a>')
        if "Remitly" in country["providers"] and "Wise" in country["providers"]:
            guides.append(f'<a href="/guias/remitly-vs-wise/">¿Remitly o Wise para {name}?</a>')
        if guides:
            extra.append('<p class="app-links"><b>Guías:</b> ' + "".join(guides) + '</p>')
        body = body.replace('<section class="crypto"', "".join(extra) + '<section class="crypto"', 1)
        faq = country_faq(data, country)
        if faq:
            body = re.sub(r'(<h2 class="section-title" id="faq-title">Preguntas frecuentes</h2>)\s*<details>.*?</details>',
                          lambda x: x.group(1) + faq, body, count=1, flags=re.S)   # its own questions replace the generic first one
        provs = list(country["providers"])
        perk = (f'<b>{len(provs)} servicios lado a lado</b><span>{esc(", ".join(provs))}.</span>' if len(provs) > 1
                else f'<b>Precio estimado de hoy</b><span>Por ahora tenemos datos de {esc(provs[0])} para {name}.</span>')
        rows = ranked(country, 300)
        badge = (f'<b>{round((rows[0]["received"] - rows[-1]["received"]) / rows[-1]["received"] * 100)}% más</b>dinero eligiendo bien hoy'
                 if len(rows) > 1 and rows[-1]["received"] > 0 else '<b>Gratis</b>y sin registro')
    else:
        perk = f'<b>Hasta {max(len(c["providers"]) for c in live)} servicios lado a lado</b><span>Remitly, Western Union, Xoom, Wise, bancos y más.</span>'
        gaps = [round((r[0]["received"] - r[-1]["received"]) / r[-1]["received"] * 100) for r in (ranked(c, 300) for c in live) if len(r) > 1 and r[-1]["received"] > 0]
        badge = f'<b>Hasta {max(gaps)}%</b>más dinero al comparar' if gaps else '<b>Gratis</b>y sin registro'
    body = body.replace('<b>Hasta 10 servicios lado a lado</b><span>Remitly, Western Union, Xoom, Wise, bancos y más.</span>', perk, 1)
    body = re.sub(r'(<div class="badge" id="story-badge">).*?(</div>)', lambda x: x.group(1) + badge + x.group(2), body, count=1, flags=re.S)
    ld = [{"@context": "https://schema.org", "@type": "WebApplication", "name": "Manda Más",
           "description": m["desc"], "applicationCategory": "FinanceApplication", "operatingSystem": "Any",
           "inLanguage": "es", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}]
    if url:
        ld[0]["url"] = url
    faqs = faq_items(body)
    if faqs:
        ld.append({"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faqs})
    meta = head_meta(m["title"], m["desc"], url, base)
    meta.append('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    attr = f' data-country="{country["code"].lower()}"' if country else ""
    return f'<!doctype html><html lang="es"{attr}><head>' + "".join(meta) + RESET + head + "</head><body>" + body + "</body></html>"


def head_meta(title, desc, url, base):
    meta = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">',
        f"<title>{esc(title)}</title>",
        f'<meta name="description" content="{esc(desc)}">',
        '<meta name="robots" content="index,follow">',
        '<meta property="og:site_name" content="Manda Más">',
        f'<meta property="og:title" content="{esc(title)}">',
        f'<meta property="og:description" content="{esc(desc)}">',
        '<meta property="og:type" content="website">',
        '<meta property="og:locale" content="es_US">',
        '<meta name="twitter:card" content="summary_large_image">',
        '<meta name="theme-color" content="#0b2a5b">',
        f'<link rel="icon" href="{FAVICON}">',
    ]
    if url:
        meta += [f'<link rel="canonical" href="{esc(url)}">', f'<meta property="og:url" content="{esc(url)}">',
                 f'<meta property="og:image" content="{esc(base)}img/og.jpg">',
                 '<meta property="og:image:width" content="1200">', '<meta property="og:image:height" content="630">']
    if UMAMI_WEBSITE_ID:
        meta.append(f'<script defer id="mm-umami" src="https://cloud.umami.is/script.js" data-website-id="{esc(UMAMI_WEBSITE_ID)}" '
                    f'data-domains="{esc(UMAMI_DOMAIN)}" data-do-not-track="true" data-exclude-search="true"></script>')
    return meta


INFO_PAGES = ["quienes-somos", "privacidad", "contacto"]  # pages/<slug>.html, built at /<slug>/
# guides/<slug>.html, built at /guias/<slug>/ and listed on /guias/ in this order
GUIDES = ["enviar-dinero-navidad", "xoom-vs-wise-mexico", "como-mandar-dinero-con-wise", "como-mandar-dinero-con-instarem", "forma-mas-barata-mandar-dinero-a-mexico", "mandar-dinero-a-guatemala", "mandar-dinero-a-honduras",
          "mandar-dinero-a-republica-dominicana", "mandar-dinero-a-colombia", "mandar-dinero-a-el-salvador", "mandar-dinero-a-peru", "mandar-dinero-a-bolivia",
          "cuanto-dinero-se-puede-enviar-a-mexico", "mandar-dinero-a-uruguay", "alternativas-a-western-union",
          "remitly-vs-wise", "remitly-vs-western-union", "envios-sin-comision",
          "which-is-better-remitly-or-western-union", "remitly-vs-wise-which-is-better",
          "tipo-de-cambio", "promociones-primer-envio", "que-necesito-para-mandar-dinero"]
WHATSAPP_CHANNEL = "https://whatsapp.com/channel/0029VbEb41M9mrGinB1b3K2y"  # also linked in index.html (results banner and footer)
NAV_LINKS = ('<div class="nav-links"><a href="/#opciones">Comparar</a><a href="/#como-funciona">Cómo funciona</a>'
             '<a href="/guias/">Guías</a><a href="/#preguntas">Preguntas</a></div>')


def read_doc(folder, slug):
    """A content file with <!--title: --> and <!--description: --> comments on top."""
    with open(os.path.join(HERE, folder, slug + ".html"), encoding="utf-8") as f:
        content = f.read()
    title = re.search(r"<!--title: (.*?)-->", content).group(1)
    desc = re.search(r"<!--description: (.*?)-->", content).group(1)
    return title, desc, re.sub(r"<!--(title|description): .*?-->\s*", "", content)


def build_info_page(page, slug, base, nav):
    """A plain text page (about, privacy, contact) wearing the home page's styles, header and footer."""
    title, desc, content = read_doc("pages", slug)
    return doc_page(page, content, title, desc, slug + "/", base, nav)


def doc_page(page, content, title, desc, path, base, nav, ld=None, lang="es"):
    head_end = page.index('<div class="wrap">')
    head = page[:head_end]
    head = re.sub(r"<title>.*?</title>\s*", "", head, flags=re.S)
    head = re.sub(r'<meta name="description"[^>]*>\s*', "", head)
    foot = re.search(r'<footer class="foot">.*?</footer>', page, re.S).group(0)
    foot = foot.replace("<!--COUNTRY_LINKS-->", nav).replace('href="#top"', 'href="/"').replace('<p id="stamp"></p>', "")
    body = ('<div class="wrap"><header class="hero slim"><div class="inner"><nav class="nav" aria-label="Principal">'
            '<a class="logo" href="/"><span class="logo-mark" aria-hidden="true">$</span><span>Manda <span class="mas">Más</span></span></a>'
            + NAV_LINKS + '</nav></div></header>'
            f'<main class="band"><div class="inner doc">{content}</div></main>{foot}</div>')
    url = base + path if base else None
    meta = head_meta(title, desc, url, base)
    if ld:
        if url:
            ld["url"] = url
        meta.append('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    return f'<!doctype html><html lang="{lang}"><head>' + "".join(meta) + RESET + head + "</head><body>" + body + "</body></html>"


# Guides: Spanish articles with tables built from the hourly data, so every number on them is as
# current as the comparison itself. Placeholders a guide can use:
#   <!--TABLE:MX:300-->              every service for that country and amount (amount must be in BRACKETS)
#   <!--VS:Remitly|Western Union:300-->  those two services side by side in every country
#   <!--BEATS:Western Union:300-->  per country: that service against the best other one (no banks, no first-transfer promos)
#   <!--BEST:500-->                  per country: the service that delivers the most and its lead over the second
#   <!--TOP:MX:300-->                name of the service that delivers the most
#   <!--DATE-->                      day the data was collected
#   <!--GO:Wise-->                   big "Ir a Wise" button with the same (referral) link as the comparison
#   <!--SHARE-->                     "send this guide by WhatsApp" button
# A guide that starts with <!--lang: en--> is in English: its date, VS table, source note and share button come out in English.
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
             "November", "December"]
COUNTRY_EN = {"México": "Mexico", "República Dominicana": "Dominican Republic", "Perú": "Peru", "Brasil": "Brazil",
              "Panamá": "Panama", "Haití": "Haiti"}  # only names that differ in English
WHOLE = {"MXN", "DOP", "COP", "CRC", "CLP", "UYU"}   # same as WHOLE in index.html
BANKS = {"Chase (US)", "Wells Fargo"}                 # same as BANKS in index.html


def parse_time(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")) if iso else None


def fecha(iso, en=False):
    d = parse_time(iso)
    return f"{MONTHS_EN[d.month - 1]} {d.day}, {d.year}" if en else f"{d.day} de {MONTHS[d.month - 1]} de {d.year}"


def page_links(page):
    """LINKS and AFFILIATE from index.html, so guides send people to the same (referral) links as the comparison."""
    block = re.search(r"const LINKS = \{(.*?)\};", page, re.S).group(1)
    aff = re.search(r"const AFFILIATE = new Set\(\[(.*?)\]\)", page).group(1)
    return dict(re.findall(r'"([^"]+)":\s*"([^"]+)"', block)), set(re.findall(r'"([^"]+)"', aff))


def ranked(country, amount):
    """Services ranked by what the family receives for one sampled amount (same math as quote() in index.html)."""
    out = []
    for name, pts in country["providers"].items():
        q = pts.get(str(amount))
        if not q:
            continue
        received = max(0, amount - q["fee"]) * q["rate"]
        fx = max(0, amount - q["fee"]) - received / country["mid"] if country["mid"] else 0
        out.append({"name": name, "fee": q["fee"], "received": received, "fx": fx, "at": q["at"], "markup": q["markup"]})
    return sorted(out, key=lambda r: -r["received"])


def local_amount(n, country):
    return f"{n:,.0f}" if country["currency"] in WHOLE else f"{n:,.2f}"


def bucket(amount):
    return "0-199" if amount < 200 else "200-499" if amount < 500 else "500-999" if amount < 1000 else "1000+"


def go_link(name, country, amount, rank, path, links, aff, cls=None):
    """An "Ir a…" link that Umami counts as outbound_service_click, like the buttons on the comparison."""
    if name not in links:
        return ""
    props = {"service": name, "page_path": path, "affiliate": "true" if name in aff else "false", "location": "guide"}
    if country:
        props.update(destination_country=country["code"], amount_bucket=bucket(amount))
    if rank:
        props["rank"] = str(rank)
    attrs = "".join(f' data-umami-event-{k}="{esc(v)}"' for k, v in props.items())
    klass = f' class="{cls}"' if cls else ""
    tag = '<small class="aff-tag">Enlace de afiliado</small>' if name in aff else ""
    return (f'<a{klass} href="{esc(links[name])}" target="_blank" rel="noopener sponsored" data-umami-event="outbound_service_click"'
            f'{attrs}>Ir a {esc(name.replace(" (US)", ""))} ↗</a>{tag}')


def source_note(data, amount, where, old, en=False):
    if en:
        return (f'<p class="src">Estimates for sending ${amount:,} from the United States, using Wise comparison data collected on '
                f'{fecha(data["collected"], True)}. Where it applies, the transfer is paid by bank transfer and received in a bank account. '
                'Amounts can change: confirm with the service before you send. '
                '<a href="https://wise.com/us/compare/disclaimer" target="_blank" rel="noopener">Wise disclaimer ↗</a></p>')
    note = (f"Estimaciones para un envío de ${amount:,} desde Estados Unidos{where}, con datos de comparación de Wise "
            f"consultados el {fecha(data['collected'])}. Cuando aplica, se paga con transferencia bancaria y se recibe en cuenta "
            "bancaria. Los montos pueden cambiar: confirma con el servicio antes de enviar.")
    if old:
        note += " * Este servicio no ha actualizado su precio en más de un día."
    return f'<p class="src">{note} <a href="https://wise.com/us/compare/disclaimer" target="_blank" rel="noopener">Aviso de Wise ↗</a></p>'


def guide_table(data, code, amount, path, links, aff):
    c = next((x for x in data["countries"] if x["code"] == code), None)
    rows = ranked(c, amount) if c else []
    if not rows:
        return "<p>Por ahora no tenemos datos para este país.</p>"
    now, old_any, body = parse_time(data["collected"]), False, ""
    for i, r in enumerate(rows, 1):
        at = parse_time(r["at"])
        old = bool(at and (now - at).total_seconds() >= 86400)
        old_any |= old
        if c["currency"] == "USD":
            fx = "—"
        elif r["fx"] < -0.005:
            fx = f"a tu favor ${-r['fx']:,.2f}"
        else:
            fx = f"${max(0, r['fx']):,.2f}"
        name = (esc(r["name"]) + (" *" if old else "") + (' <small>(solo clientes)</small>' if r["name"] in BANKS else "")
                + (' <small>(promoción de primer envío)</small>' if r["markup"] < -0.1 else ""))
        body += (f'<tr{" class=top" if i == 1 else ""}><td class="num">{i}</td><td>{name}</td>'
                 f'<td class="num"><b>{local_amount(r["received"], c)}</b></td><td class="num">${r["fee"]:,.2f}</td>'
                 f'<td class="num">{fx}</td><td>{go_link(r["name"], c, amount, i, path, links, aff)}</td></tr>')
    head = (f'<caption>Si mandas ${amount:,} a {esc(c["name"])}, tu familia recibe ({esc(c["currencyName"])})</caption>'
            '<thead><tr><th class="num">#</th><th>Servicio</th><th class="num">Recibe</th><th class="num">Comisión</th>'
            '<th class="num">Costo en el cambio</th><th></th></tr></thead>')
    return (f'<div class="table-wrap"><table class="guide-table">{head}<tbody>{body}</tbody></table></div>'
            + source_note(data, amount, " a " + c["name"], old_any))


def guide_vs(data, a, b, amount, path, links, aff, en=False):
    body = ""
    for c in data["countries"]:
        r = {x["name"]: x for x in ranked(c, amount)}
        if a not in r or b not in r:
            continue
        win = a if r[a]["received"] > r[b]["received"] else b if r[b]["received"] > r[a]["received"] else "Tie" if en else "Empate"
        place, money = (COUNTRY_EN.get(c["name"], c["name"]), c["currency"]) if en else (c["name"], c["currencyName"])
        body += (f'<tr><td><a href="/{SLUGS[c["code"]]}/">{esc(place)}</a></td><td><b>{esc(win)}</b></td><td class="num">{local_amount(r[a]["received"], c)}</td>'
                 f'<td class="num">{local_amount(r[b]["received"], c)}</td><td>{esc(money)}</td></tr>')
    if not body:
        return "<p>We don't have data for both services right now.</p>" if en else "<p>Por ahora no tenemos datos de los dos servicios a la vez.</p>"
    if en:
        head = (f'<caption>If you send ${amount:,}, your family receives</caption><thead><tr><th>Country</th><th>Delivers more</th>'
                f'<th class="num">{esc(a)}</th><th class="num">{esc(b)}</th><th>Currency</th></tr></thead>')
        return (f'<div class="table-wrap"><table class="guide-table">{head}<tbody>{body}</tbody></table></div>'
                + source_note(data, amount, "", False, True))
    head = (f'<caption>Si mandas ${amount:,}, tu familia recibe</caption><thead><tr><th>País</th><th>Entrega más</th><th class="num">{esc(a)}</th>'
            f'<th class="num">{esc(b)}</th><th>Moneda</th></tr></thead>')
    return (f'<div class="table-wrap"><table class="guide-table">{head}<tbody>{body}</tbody></table></div>'
            + source_note(data, amount, "", False))


def guide_beats(data, name, amount):
    body = ""
    for c in data["countries"]:
        rows = [r for r in ranked(c, amount) if r["name"] not in BANKS and (r["markup"] >= -0.1 or r["name"] == name)]
        mine = next((r for r in rows if r["name"] == name), None)
        others = [r for r in rows if r["name"] != name]
        if not mine or not others:
            continue
        best = others[0]
        diff = best["received"] - mine["received"]
        if diff > 0:
            cells = (f'<td><b>{esc(best["name"])}</b></td><td class="num">{local_amount(best["received"], c)}</td>'
                     f'<td class="num"><b>+{local_amount(diff, c)}</b></td>')
        else:
            cells = f'<td colspan="3">{esc(name)} es la que más entrega hoy</td>'
        body += (f'<tr><td><a href="/{SLUGS[c["code"]]}/">{esc(c["name"])}</a></td><td class="num">{local_amount(mine["received"], c)}</td>'
                 f'{cells}<td>{esc(c["currencyName"])}</td></tr>')
    if not body:
        return "<p>Por ahora no tenemos datos para esta comparación.</p>"
    head = (f'<caption>Si mandas ${amount:,}, tu familia recibe</caption><thead><tr><th>País</th><th class="num">{esc(name)}</th>'
            '<th>La que más entrega</th><th class="num">Recibe</th><th class="num">Diferencia</th><th>Moneda</th></tr></thead>')
    return (f'<div class="table-wrap"><table class="guide-table">{head}<tbody>{body}</tbody></table></div>'
            + source_note(data, amount, "", False))


def guide_best(data, amount):
    """Per country: the service that delivers the most (no banks, no first-transfer promos) and its lead over the next one."""
    body = ""
    for c in data["countries"]:
        rows = [r for r in ranked(c, amount) if r["name"] not in BANKS and r["markup"] >= -0.1]
        if len(rows) < 2:
            continue
        best, second = rows[0], rows[1]
        diff = best["received"] - second["received"]
        body += (f'<tr><td><a href="/{SLUGS[c["code"]]}/">{esc(c["name"])}</a></td>'
                 f'<td><b>{esc(best["name"])}</b><br><small>+{local_amount(diff, c)} vs. {esc(second["name"])}</small></td>'
                 f'<td class="num">{local_amount(best["received"], c)}<br><small>{esc(c["currencyName"])}</small></td></tr>')
    if not body:
        return "<p>Por ahora no tenemos datos para esta comparación.</p>"
    head = (f'<caption>Si mandas ${amount:,}, tu familia recibe</caption><thead><tr><th>País</th><th>La que más entrega</th>'
            '<th class="num">Recibe</th></tr></thead>')  # 3 columns so it fits a phone
    return (f'<div class="table-wrap"><table class="guide-table wrap">{head}<tbody>{body}</tbody></table></div>'
            + source_note(data, amount, "", False))


def build_guide(page, data, slug, base, nav, links, aff):
    title, desc, content = read_doc("guides", slug)
    en = "<!--lang: en-->" in content
    content = content.replace("<!--lang: en-->", "").lstrip()
    path = f"/guias/{slug}/"
    content = re.sub(r"<!--TABLE:(\w+):(\d+)-->", lambda m: guide_table(data, m[1], int(m[2]), path, links, aff), content)
    content = re.sub(r"<!--VS:([^|]+)\|([^:]+):(\d+)-->", lambda m: guide_vs(data, m[1], m[2], int(m[3]), path, links, aff, en), content)

    content = re.sub(r"<!--BEATS:([^:]+):(\d+)-->", lambda m: guide_beats(data, m[1], int(m[2])), content)
    content = re.sub(r"<!--BEST:(\d+)-->", lambda m: guide_best(data, int(m[1])), content)

    def top(m):
        c = next((x for x in data["countries"] if x["code"] == m[1]), None)
        rows = ranked(c, int(m[2])) if c else []
        return esc(rows[0]["name"]) if rows else "—"
    content = re.sub(r"<!--TOP:(\w+):(\d+)-->", top, content)
    content = content.replace("<!--DATE-->", fecha(data["collected"], en))
    content = re.sub(r"<!--GO:([^>]+?)-->", lambda m: f'<p class="go-line">{go_link(m[1], None, 0, None, path, links, aff, "cta")}</p>', content)
    if en:
        content = content.replace(">Ir a ", ">Go to ").replace(">Enlace de afiliado<", ">Affiliate link<")
    h1 = re.search(r"<h1>(.*?)</h1>", content, re.S).group(1)
    page_url = (base or "https://mandamasdinero.com/") + path.lstrip("/")
    share = urllib.parse.quote(html_mod.unescape(re.sub(r"<.*?>", "", h1)) + " " + page_url)
    if en:
        content = content.replace("<!--SHARE-->", f'<p><a class="share-wa" href="https://wa.me/?text={share}" target="_blank" rel="noopener">'
                                                  'Send this page to a relative on WhatsApp</a></p>')
    content = content.replace("<!--SHARE-->", f'<p><a class="share-wa" href="https://wa.me/?text={share}" target="_blank" rel="noopener">'
                                              'Mándale esta guía a un familiar por WhatsApp</a></p>'
                                              f'<p>¿Quieres saber cada semana qué app entrega más? <a href="{WHATSAPP_CHANNEL}" target="_blank" rel="noopener" '
                                              'data-umami-event="whatsapp_follow" data-umami-event-location="guide">Sigue nuestro canal de WhatsApp</a>. Es gratis.</p>')
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": html_mod.unescape(re.sub(r"<.*?>", "", h1)),
          "description": desc, "inLanguage": "en" if en else "es", "dateModified": data["collected"],
          "author": {"@type": "Organization", "name": "Manda Más"}, "publisher": {"@type": "Organization", "name": "Manda Más"}}
    out = doc_page(page, content, title, desc, f"guias/{slug}/", base, nav, ld, "en" if en else "es")
    faqs = faq_items(content)
    if faqs:
        faq_ld = {"@context": "https://schema.org", "@type": "FAQPage", "mainEntity": faqs}
        out = out.replace("</head>", '<script type="application/ld+json">' + json.dumps(faq_ld, ensure_ascii=False).replace("</", "<\\/")
                          + "</script></head>", 1)
    return out


# App pages: /<country>/<app>/ ("Remitly a México hoy"), one per service and country, built from the hourly data.
# They answer the exact searches people make ("cuánto llega con Western Union a Guatemala") with today's numbers.
APP_AMOUNTS = [100, 200, 300, 500, 1000]   # must be in BRACKETS
APP_MAIN = 300                             # the amount used in the title, the lead and the full table
APP_GUIDES = {"Wise": [("como-mandar-dinero-con-wise", "Cómo mandar dinero con Wise, paso a paso"), ("remitly-vs-wise", "Remitly vs. Wise")],
              "Instarem": [("como-mandar-dinero-con-instarem", "Cómo mandar dinero con Instarem, paso a paso")],
              "Remitly": [("remitly-vs-western-union", "Remitly vs. Western Union"), ("remitly-vs-wise", "Remitly vs. Wise")],
              "Western Union": [("remitly-vs-western-union", "Remitly vs. Western Union"), ("alternativas-a-western-union", "Alternativas a Western Union")],
              "Xoom": [("xoom-vs-wise-mexico", "Xoom vs. Wise")]}


def app_slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower().replace("(us)", "")).strip("-")


def app_pages(data):
    """[(country, service name)] for every service with a $300 price, in countries with at least two services (no banks)."""
    out = []
    for c in data["countries"]:
        names = [r["name"] for r in ranked(c, APP_MAIN) if r["name"] not in BANKS]
        if len(names) >= 2:
            out += [(c, n) for n in names]
    return out


def app_links_html(data, country, skip=None):
    names = [n for c, n in app_pages(data) if c["code"] == country["code"] and n != skip]
    return "".join(f'<a href="/{SLUGS[country["code"]]}/{app_slug(n)}/">{esc(n)} a {esc(country["name"])} hoy</a>' for n in names)


def build_app_page(page, data, c, name, base, nav, links, aff):
    path = f"/{SLUGS[c['code']]}/{app_slug(name)}/"
    pais, cur = c["name"], c["currencyName"]

    def fair(rows):  # the services to compare against: no banks, no first-transfer promos
        return [r for r in rows if r["name"] not in BANKS and r["markup"] >= -0.1 and r["name"] != name]

    rows = ranked(c, APP_MAIN)
    me = next(r for r in rows if r["name"] == name)
    others = fair(rows)
    q = c["providers"][name][str(APP_MAIN)]
    lead = (f'Si mandas <b>${APP_MAIN}</b> con {esc(name)} a {esc(pais)}, tu familia recibe unos '
            f'<b>{local_amount(me["received"], c)} {esc(cur)}</b>, con una comisión de ${me["fee"]:,.2f}.')
    if others and others[0]["received"] > me["received"]:
        best = others[0]
        lead += (f' Hoy, <b>{esc(best["name"])}</b> entrega {local_amount(best["received"] - me["received"], c)} {esc(cur)} más '
                 f'por el mismo envío ({local_amount(best["received"], c)}).')
    else:
        promo = any(r["markup"] < -0.1 and r["received"] > me["received"] and r["name"] not in BANKS for r in rows)
        lead += (f" Hoy es la app que <b>más entrega</b> a {esc(pais)} por ese monto"
                 + (" (sin contar promociones de primer envío)." if promo else "."))
    if me["markup"] < -0.1:
        lead += " <b>Ojo:</b> este precio es una promoción de primer envío; los siguientes envíos suelen recibir menos."

    body = ""
    for amount in APP_AMOUNTS:
        rs = ranked(c, amount)
        mine = next((r for r in rs if r["name"] == name), None)
        if not mine:
            continue
        ot = fair(rs)
        if ot and ot[0]["received"] > mine["received"]:
            cmp = (f'{esc(ot[0]["name"])}<br><small>+{local_amount(ot[0]["received"] - mine["received"], c)} más</small>')
        else:
            cmp = f'<b>{esc(name)}</b><br><small>es la que más entrega</small>'
        body += (f'<tr><td class="num">${amount:,}</td><td class="num"><b>{local_amount(mine["received"], c)}</b>'
                 f'<br><small>comisión ${mine["fee"]:,.2f}</small></td><td>{cmp}</td></tr>')
    table = (f'<div class="table-wrap"><table class="guide-table wrap"><caption>Con {esc(name)} a {esc(pais)}, tu familia recibe ({esc(cur)})</caption>'
             f'<thead><tr><th class="num">Envías</th><th class="num">Recibe</th><th>La que más entrega</th></tr></thead><tbody>{body}</tbody></table></div>')

    fx = ""
    if c["currency"] != "USD" and c["mid"]:
        fx = (f'<h2>Tipo de cambio de {esc(name)} hoy</h2><p>Con {esc(name)}, <b>1 dólar = {q["rate"]:,.2f} {esc(c["currency"])}</b>. '
              f'El tipo de cambio real (el del mercado) está en {c["mid"]:,.2f}. ')
        if q["markup"] > 0.05:
            fx += (f'La diferencia, cerca de <b>{q["markup"]:.1f}%</b>, es lo que {esc(name)} se queda en el cambio, además de la comisión. '
                   '<a href="/guias/tipo-de-cambio/">Cómo saber si te dan buen tipo de cambio</a>.</p>')
        elif q["markup"] < -0.1:
            fx += 'Te dan un tipo de cambio mejor que el real porque es una promoción de primer envío.</p>'
        else:
            fx += f'{esc(name)} usa prácticamente el tipo de cambio real; lo que cobra está en la comisión.</p>'

    guides = "".join(f'<li><a href="/guias/{s}/">{esc(t)}</a></li>' for s, t in APP_GUIDES.get(name, []) if s in GUIDES)
    elsewhere = "".join(f'<a href="/{SLUGS[x["code"]]}/{app_slug(name)}/">{esc(name)} a {esc(x["name"])}</a>'
                        for x, n in app_pages(data) if n == name and x["code"] != c["code"])
    go = go_link(name, c, APP_MAIN, None, path, links, aff, "cta")
    content = (f'<p class="eyebrow">Precio de hoy · {esc(pais)}</p><h1>{esc(name)} a {esc(pais)} hoy: cuánto recibe tu familia</h1>'
               f'<p class="updated">Precios actualizados el {fecha(data["collected"])}. Se actualizan cada hora.</p>'
               f'<p class="lead">{lead}</p>'
               + (f'<p class="go-line">{go}</p>' if go else "")
               + f'<h2>¿Cuánto llega con {esc(name)} según lo que mandes?</h2>{table}'
               + fx
               + f'<h2>Todas las apps a {esc(pais)} hoy (envío de ${APP_MAIN})</h2>'
               + guide_table(data, c["code"], APP_MAIN, path, links, aff)
               + f'<p><a class="cta" href="/{SLUGS[c["code"]]}/">Compara con tu monto exacto →</a></p>'
               + f'<h2>Otras apps a {esc(pais)}</h2><p class="app-links">{app_links_html(data, c, name)}</p>'
               + (f'<h2>{esc(name)} a otros países</h2><p class="app-links">{elsewhere}</p>' if elsewhere else "")
               + (f'<h2>Guías</h2><ul>{guides}</ul>' if guides else "")
               + '<p class="tip"><b>Recuerda:</b> las cifras son estimaciones, no cotizaciones garantizadas. El precio final lo ves en la app '
                 'antes de confirmar. Manda Más es gratis; algunas apps nos pueden pagar una comisión si te registras desde nuestra página, '
                 'sin costo para ti, y eso nunca cambia el orden.</p><!--SHARE-->')
    url = (base or "https://mandamasdinero.com/") + path.lstrip("/")
    share = urllib.parse.quote(f"{name} a {pais} hoy: cuánto llega " + url)
    content = content.replace("<!--SHARE-->", f'<p><a class="share-wa" href="https://wa.me/?text={share}" target="_blank" rel="noopener">'
                                              'Mándale esta página a un familiar por WhatsApp</a></p>')
    title = f"{name} a {pais} hoy: cuánto llega por ${APP_MAIN} | Manda Más"
    desc = (f"¿Cuánto recibe tu familia en {pais} si mandas dinero con {name}? Hoy, por ${APP_MAIN} llegan unos "
            f"{local_amount(me['received'], c)} {cur}. Mira la comisión, el tipo de cambio y qué app entrega más.")
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": f"{name} a {pais} hoy: cuánto recibe tu familia",
          "description": desc, "inLanguage": "es", "dateModified": data["collected"],
          "author": {"@type": "Organization", "name": "Manda Más"}, "publisher": {"@type": "Organization", "name": "Manda Más"}}
    return doc_page(page, content, title, desc, path.lstrip("/"), base, nav, ld)


def build_guides_index(page, base, nav):
    items = ""
    for slug in GUIDES:
        title, desc, content = read_doc("guides", slug)
        h1 = re.search(r"<h1>(.*?)</h1>", content, re.S).group(1)
        items += f'<li><a href="/guias/{slug}/">{h1}</a><p>{esc(desc)}</p></li>'
    content = ('<p class="eyebrow">Guías</p><h1>Guías para mandar dinero</h1>'
               '<p class="lead">Respuestas cortas y en español a las preguntas más comunes al mandar dinero desde Estados Unidos.</p>'
               f'<ul class="guide-list">{items}</ul>')
    return doc_page(page, content, "Guías para mandar dinero desde Estados Unidos | Manda Más",
                    "Guías en español para mandar dinero a México y Latinoamérica: cuál servicio conviene, comisiones, tipo de cambio y qué necesitas.",
                    "guias/", base, nav)


def write_site(page, data, site_dir, base):
    """Build the public website: a home page, one page per country, the info pages, sitemap.xml and robots.txt."""
    if base and not base.endswith("/"):
        base += "/"
    live = [c for c in data["countries"] if c["providers"]]
    links = "".join(f'<li><a href="{esc((base or "/") + SLUGS[c["code"]] + "/")}">Enviar dinero a {esc(c["name"])}</a></li>' for c in live)
    nav = f'<nav class="countries-nav" aria-labelledby="nav-title"><h2 id="nav-title">Compara por país</h2><ul>{links}</ul></nav>'
    pages = [None] + live
    img_src = os.path.join(HERE, "img")
    if os.path.isdir(img_src):
        shutil.copytree(img_src, os.path.join(site_dir, "img"), dirs_exist_ok=True)
    for country in pages:
        out_dir = site_dir if not country else os.path.join(site_dir, SLUGS[country["code"]])
        os.makedirs(out_dir, exist_ok=True)
        with open(os.path.join(out_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(build_page(page, data, country, base, nav))
    for slug in INFO_PAGES:
        os.makedirs(os.path.join(site_dir, slug), exist_ok=True)
        with open(os.path.join(site_dir, slug, "index.html"), "w", encoding="utf-8") as f:
            f.write(build_info_page(page, slug, base, nav))
    links, aff = page_links(page)
    os.makedirs(os.path.join(site_dir, "guias"), exist_ok=True)
    with open(os.path.join(site_dir, "guias", "index.html"), "w", encoding="utf-8") as f:
        f.write(build_guides_index(page, base, nav))
    for slug in GUIDES:
        os.makedirs(os.path.join(site_dir, "guias", slug), exist_ok=True)
        with open(os.path.join(site_dir, "guias", slug, "index.html"), "w", encoding="utf-8") as f:
            f.write(build_guide(page, data, slug, base, nav, links, aff))
    apps = app_pages(data)
    for c, name in apps:
        d = os.path.join(site_dir, SLUGS[c["code"]], app_slug(name))
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "index.html"), "w", encoding="utf-8") as f:
            f.write(build_app_page(page, data, c, name, base, nav, links, aff))
    if base:
        day = data["collected"][:10]
        urls = "".join(f"<url><loc>{base}{'' if not c else SLUGS[c['code']] + '/'}</loc><lastmod>{day}</lastmod>"
                       f"<changefreq>hourly</changefreq></url>" for c in pages)
        urls += "".join(f"<url><loc>{base}{slug}/</loc><changefreq>monthly</changefreq></url>" for slug in INFO_PAGES)
        urls += f"<url><loc>{base}guias/</loc><changefreq>weekly</changefreq></url>"
        urls += "".join(f"<url><loc>{base}guias/{slug}/</loc><lastmod>{day}</lastmod><changefreq>daily</changefreq></url>"
                        for slug in GUIDES)
        urls += "".join(f"<url><loc>{base}{SLUGS[c['code']]}/{app_slug(n)}/</loc><lastmod>{day}</lastmod><changefreq>daily</changefreq></url>"
                        for c, n in apps)
        with open(os.path.join(site_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + urls + "</urlset>")
        with open(os.path.join(site_dir, "robots.txt"), "w", encoding="utf-8") as f:
            f.write(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n")
    return len(pages) + len(apps)


def check(data):
    """Refuse to publish if a data source came back broken, so the last good version stays up."""
    by_code = {c["code"]: c for c in data["countries"]}
    if len(by_code["MX"]["providers"]) < 3:
        sys.exit("Too few providers for México; not publishing.")
    if sum(1 for c in data["countries"] if c["providers"]) < 4:
        sys.exit("Too many countries came back empty; not publishing.")


def arg(name):
    return sys.argv[sys.argv.index(name) + 1] if name in sys.argv else None


def main():
    site_dir, base = arg("--site"), arg("--base-url")
    data = collect()
    check(data)
    with open(PAGE, encoding="utf-8") as f:
        html = f.read()
    block = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    new, n = re.subn(r'(<script id="rates" type="application/json">).*?(</script>)',
                     lambda m: m.group(1) + block + m.group(2), html, flags=re.S)
    if n != 1:
        sys.exit("Could not find the rates block in index.html")
    with open(PAGE, "w", encoding="utf-8") as f:
        f.write(new)
    print(f"Updated {PAGE} ({data['collected']})")
    if site_dir:
        n = write_site(new, data, site_dir, base)
        print(f"Wrote {n} pages to {site_dir}/" + (" plus sitemap.xml and robots.txt" if base else " (no --base-url: skipped sitemap)"))


if __name__ == "__main__":
    main()
