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
        "title": f"Enviar dinero a {country['name']} desde Estados Unidos: compara precios | Manda Más",
        "desc": f"¿Cuál es la forma más barata de mandar dinero a {country['name']}? Compara estimaciones actualizadas de {shown} "
                f"y mira cuántos {country['currencyName']} puede recibir tu familia.",
        "lede": f"Mira cuántos {country['currencyName']} puede recibir tu familia en {country['name']} con cada servicio "
                f"al mandar dinero desde Estados Unidos. Comparamos {shown}.",
    }


def build_page(page, data, country, base, nav):
    m = page_meta(data, country, base)
    url = base + m["path"] if base else None
    head_end = page.index('<div class="wrap">')
    head, body = page[:head_end], page[head_end:]
    head = re.sub(r"<title>.*?</title>\s*", "", head, flags=re.S)
    head = re.sub(r'<meta name="description"[^>]*>\s*', "", head)
    body = re.sub(r'(<p class="lede" id="lede">).*?(</p>)', lambda x: x.group(1) + esc(m["lede"]) + x.group(2), body, flags=re.S)
    body = body.replace("<!--COUNTRY_LINKS-->", nav)
    ld = [{"@context": "https://schema.org", "@type": "WebApplication", "name": "Manda Más",
           "description": m["desc"], "applicationCategory": "FinanceApplication", "operatingSystem": "Any",
           "inLanguage": "es", "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"}}]
    if url:
        ld[0]["url"] = url
    faqs = faq_items(page)
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
GUIDES = ["forma-mas-barata-mandar-dinero-a-mexico", "remitly-vs-western-union", "envios-sin-comision",
          "tipo-de-cambio", "promociones-primer-envio", "que-necesito-para-mandar-dinero"]
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


def doc_page(page, content, title, desc, path, base, nav, ld=None):
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
    return '<!doctype html><html lang="es"><head>' + "".join(meta) + RESET + head + "</head><body>" + body + "</body></html>"


# Guides: Spanish articles with tables built from the hourly data, so every number on them is as
# current as the comparison itself. Placeholders a guide can use:
#   <!--TABLE:MX:300-->              every service for that country and amount (amount must be in BRACKETS)
#   <!--VS:Remitly|Western Union:300-->  those two services side by side in every country
#   <!--TOP:MX:300-->                name of the service that delivers the most
#   <!--DATE-->                      day the data was collected
MONTHS = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
          "noviembre", "diciembre"]
WHOLE = {"MXN", "DOP", "COP", "CRC", "CLP", "UYU"}   # same as WHOLE in index.html
BANKS = {"Chase (US)", "Wells Fargo"}                 # same as BANKS in index.html


def parse_time(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00")) if iso else None


def fecha(iso):
    d = parse_time(iso)
    return f"{d.day} de {MONTHS[d.month - 1]} de {d.year}"


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


def go_link(name, country, amount, rank, path, links, aff):
    """An "Ir a…" link that Umami counts as outbound_service_click, like the buttons on the comparison."""
    if name not in links:
        return ""
    props = {"service": name, "destination_country": country["code"], "amount_bucket": bucket(amount),
             "page_path": path, "affiliate": "true" if name in aff else "false", "location": "guide"}
    if rank:
        props["rank"] = str(rank)
    attrs = "".join(f' data-umami-event-{k}="{esc(v)}"' for k, v in props.items())
    return (f'<a href="{esc(links[name])}" target="_blank" rel="noopener sponsored" data-umami-event="outbound_service_click"'
            f'{attrs}>Ir a {esc(name.replace(" (US)", ""))} ↗</a>')


def source_note(data, amount, where, old):
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


def guide_vs(data, a, b, amount, path, links, aff):
    body = ""
    for c in data["countries"]:
        r = {x["name"]: x for x in ranked(c, amount)}
        if a not in r or b not in r:
            continue
        win = a if r[a]["received"] > r[b]["received"] else b if r[b]["received"] > r[a]["received"] else "Empate"
        body += (f'<tr><td>{esc(c["name"])}</td><td><b>{esc(win)}</b></td><td class="num">{local_amount(r[a]["received"], c)}</td>'
                 f'<td class="num">{local_amount(r[b]["received"], c)}</td><td>{esc(c["currencyName"])}</td></tr>')
    if not body:
        return "<p>Por ahora no tenemos datos de los dos servicios a la vez.</p>"
    head = (f'<caption>Si mandas ${amount:,}, tu familia recibe</caption><thead><tr><th>País</th><th>Entrega más</th><th class="num">{esc(a)}</th>'
            f'<th class="num">{esc(b)}</th><th>Moneda</th></tr></thead>')
    return (f'<div class="table-wrap"><table class="guide-table">{head}<tbody>{body}</tbody></table></div>'
            + source_note(data, amount, "", False))


def build_guide(page, data, slug, base, nav, links, aff):
    title, desc, content = read_doc("guides", slug)
    path = f"/guias/{slug}/"
    content = re.sub(r"<!--TABLE:(\w+):(\d+)-->", lambda m: guide_table(data, m[1], int(m[2]), path, links, aff), content)
    content = re.sub(r"<!--VS:([^|]+)\|([^:]+):(\d+)-->", lambda m: guide_vs(data, m[1], m[2], int(m[3]), path, links, aff), content)

    def top(m):
        c = next((x for x in data["countries"] if x["code"] == m[1]), None)
        rows = ranked(c, int(m[2])) if c else []
        return esc(rows[0]["name"]) if rows else "—"
    content = re.sub(r"<!--TOP:(\w+):(\d+)-->", top, content)
    content = content.replace("<!--DATE-->", fecha(data["collected"]))
    h1 = re.search(r"<h1>(.*?)</h1>", content, re.S).group(1)
    ld = {"@context": "https://schema.org", "@type": "Article", "headline": html_mod.unescape(re.sub(r"<.*?>", "", h1)),
          "description": desc, "inLanguage": "es", "dateModified": data["collected"],
          "author": {"@type": "Organization", "name": "Manda Más"}, "publisher": {"@type": "Organization", "name": "Manda Más"}}
    return doc_page(page, content, title, desc, f"guias/{slug}/", base, nav, ld)


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
    if base:
        day = data["collected"][:10]
        urls = "".join(f"<url><loc>{base}{'' if not c else SLUGS[c['code']] + '/'}</loc><lastmod>{day}</lastmod>"
                       f"<changefreq>hourly</changefreq></url>" for c in pages)
        urls += "".join(f"<url><loc>{base}{slug}/</loc><changefreq>monthly</changefreq></url>" for slug in INFO_PAGES)
        urls += f"<url><loc>{base}guias/</loc><changefreq>weekly</changefreq></url>"
        urls += "".join(f"<url><loc>{base}guias/{slug}/</loc><lastmod>{day}</lastmod><changefreq>daily</changefreq></url>"
                        for slug in GUIDES)
        with open(os.path.join(site_dir, "sitemap.xml"), "w", encoding="utf-8") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + urls + "</urlset>")
        with open(os.path.join(site_dir, "robots.txt"), "w", encoding="utf-8") as f:
            f.write(f"User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n")
    return len(pages)


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
