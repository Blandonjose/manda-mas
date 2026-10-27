"""Collect live USD -> Latin America remittance quotes and write them into index.html.

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

COUNTRIES = [
    # code, name, currency, currency name (plural), Bitso book for the stablecoin route
    ("MX", "México", "MXN", "pesos", "usdt_mxn"),
    ("GT", "Guatemala", "GTQ", "quetzales", None),
    ("HN", "Honduras", "HNL", "lempiras", None),
    ("SV", "El Salvador", "USD", "dólares", None),
    ("DO", "República Dominicana", "DOP", "pesos dominicanos", None),
    ("CO", "Colombia", "COP", "pesos colombianos", "usdt_cop"),
    ("CR", "Costa Rica", "CRC", "colones", None),
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
        "sourceCurrency": "USD", "targetCurrency": currency, "targetCountry": country, "sendAmount": amount})
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
         "DO": "republica-dominicana", "CO": "colombia", "CR": "costa-rica"}
FAVICON = ("data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 32 32%22%3E"
           "%3Crect width=%2232%22 height=%2232%22 rx=%227%22 fill=%22%230d6a55%22/%3E%3Ctext x=%2216%22 y=%2224%22 "
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
            "title": "Manda Más: compara envíos de dinero a México y Centroamérica",
            "desc": "Compara en vivo cuánto recibe tu familia con Remitly, Western Union, Xoom, Wise y más. "
                    "Envíos de dinero desde Estados Unidos a " + ", ".join(names[:-1]) + " y " + names[-1] + ".",
            "lede": "Mira cuánto recibe tu familia con cada servicio antes de mandar dinero. Comparamos Remitly, Western Union, "
                    "Xoom, Wise y más para envíos a " + ", ".join(names[:-1]) + " y " + names[-1] + ".",
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
        "desc": f"¿Cuál es la forma más barata de mandar dinero a {country['name']}? Compara en vivo {shown}, "
                f"y mira cuántos {country['currencyName']} recibe tu familia.",
        "lede": f"Mira cuántos {country['currencyName']} recibe tu familia en {country['name']} con cada servicio, "
                f"antes de mandar dinero. Comparamos {shown}.",
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
    meta = [
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">',
        f"<title>{esc(m['title'])}</title>",
        f'<meta name="description" content="{esc(m["desc"])}">',
        '<meta name="robots" content="index,follow">',
        '<meta property="og:site_name" content="Manda Más">',
        f'<meta property="og:title" content="{esc(m["title"])}">',
        f'<meta property="og:description" content="{esc(m["desc"])}">',
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
    meta.append('<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>")
    attr = f' data-country="{country["code"].lower()}"' if country else ""
    return f'<!doctype html><html lang="es"{attr}><head>' + "".join(meta) + RESET + head + "</head><body>" + body + "</body></html>"


def write_site(page, data, site_dir, base):
    """Build the public website: a home page, one page per country, sitemap.xml and robots.txt."""
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
    if base:
        day = data["collected"][:10]
        urls = "".join(f"<url><loc>{base}{'' if not c else SLUGS[c['code']] + '/'}</loc><lastmod>{day}</lastmod>"
                       f"<changefreq>hourly</changefreq></url>" for c in pages)
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
