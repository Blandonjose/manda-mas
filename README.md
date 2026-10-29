# Manda Más

Compares how much a family receives when you send dollars to México, Central America and South America with each
money-transfer service. In Spanish, phone-first, no sign-up. Manda Más never handles anyone's money.

## How it works

- `index.html`: the whole page (design, logic and the latest prices, embedded as JSON).
- `update_rates.py`: pulls updated quote estimates and writes them into `index.html`.
  Sources: Wise's public provider-comparison feed and Bitso's USDT order books. Python 3.9+, no installs.
- `.github/workflows/refresh.yml`: every hour, GitHub runs the script, wraps the page as a full
  website and publishes it to GitHub Pages. If a source is down, the run fails and the last good
  version stays online.

## Commands

```bash
python3 update_rates.py                 # refresh prices in index.html
python3 update_rates.py --site _site    # also build the website into _site/
```

## Data permission and presentation

- Wise confirmed on 29 October 2026 that Manda Más may use the Comparison API for informational comparison, subject to its API rules.
- Treat prices, received amounts and delivery times as estimates; identify the United States as the sending country; show when data was collected; use short-lived caching; and link Wise's comparison disclaimer.
- The existing unauthenticated comparison endpoint remains in use for the current site. Any new integration should use Wise's documented authenticated API and keep its token server-side.

## Before promoting it publicly

- Replace the "Ir a…" links in `index.html` (`LINKS`) with your referral links.

## Analytics

Umami, with no cookies: `quote_view` and `outbound_service_click`. Set `UMAMI_WEBSITE_ID` in `update_rates.py`.
Events, properties and how to test them are in [ANALYTICS.md](ANALYTICS.md).
