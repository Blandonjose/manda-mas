# Analytics

Manda Más uses [Umami Cloud](https://cloud.umami.is), which sets no cookies, for two custom events plus Umami's
automatic page views. No names, emails, recipient details, exact amounts, wallet addresses or other
personal data are sent. Umami also receives the visitor's IP address, which it doesn't store.

## Configuration

- **Website ID:** `UMAMI_WEBSITE_ID` near the top of `update_rates.py`. While it is empty, the builder adds no
  script and no events leave the browser.
- **Domain filter:** `UMAMI_DOMAIN` (`mandamasdinero.com`). Umami ignores visits on any other host, so local
  builds never send data even with the ID set.
- The script tag is added to every built page (home, country pages, info pages) by `head_meta()`. It also
  respects the browser's "Do Not Track" setting and drops query strings from page URLs.
- **Affiliate flag:** the `AFFILIATE` set in `index.html`, next to `LINKS`. Add a service name there when
  you swap its link for a referral link.

## Events

### `quote_view`

Sent when comparison results are on screen and have been stable for 1.5 seconds. It is sent again only when
the country, amount bucket, number of services, top service or page changes. Typing within a bucket and
the 2-minute live refresh don't send a new event.

| Property | Example |
|---|---|
| `destination_country` | `MX` |
| `amount_bucket` | `0-199`, `200-499`, `500-999`, `1000+` |
| `services_compared` | `10` |
| `top_service` | `Xoom` |
| `page_path` | `/mexico/` |

### `outbound_service_click`

Sent on click or middle click of any link that has `data-service`. Today that means the "Ir a…" buttons
in the results list. One capturing listener on `document` handles every link, so cards redrawn by price
updates, or added later, are covered automatically. It never cancels or delays the click.

| Property | Example |
|---|---|
| `service` | `Remitly` |
| `destination_country` | `GT` |
| `amount_bucket` | `200-499` |
| `rank` | `1` (left out for unranked links) |
| `page_path` | `/` |
| `affiliate` | `true` / `false` |
| `location` | `results` (also `best_option`, `crypto` for future buttons) |

Guide pages (`/guias/…`) don't load the comparison script. Their "Ir a…" links send the same event through
Umami's `data-umami-event` attributes, with `location` set to `guide`. Umami sends those property values as text,
so `affiliate` and `rank` arrive as `"true"`/`"false"` and `"1"` rather than a boolean and a number.

To track a new outbound link, give it `data-service="<name>"`, `data-location="<where>"`, and
`data-rank="<n>"` if it has a ranking position.

## Testing locally

```bash
python3 update_rates.py --site _site
cd _site && python3 -m http.server 8000
```

Open `http://localhost:8000/?analytics_debug=1`. Each event is printed in the browser console as
`[analytics] …` and collected in `window.__mmEvents`. Nothing is sent from localhost.

## Checking the real data (after deploying)

1. In Umami, open the website's **Realtime** view.
2. Visit https://mandamasdinero.com from a browser without an ad blocker and with "Do Not Track" turned off.
3. Wait about 2 seconds after the results show, then click an "Ir a…" button.
4. `quote_view` and `outbound_service_click` appear under **Events**. Click an event to see its properties.

You can also open `https://mandamasdinero.com/?analytics_debug=1` to see in the console exactly what is sent.
