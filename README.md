# Manda Más

Compares how much a family receives when you send dollars to México and Central America with each
money-transfer service. In Spanish, phone-first, no sign-up. Manda Más never handles anyone's money.

## How it works

- `index.html`: the whole page (design, logic and the latest prices, embedded as JSON).
- `update_rates.py`: pulls fresh quotes and writes them into `index.html`.
  Sources: Wise's public provider-comparison feed and Bitso's USDT order books. Python 3.9+, no installs.
- `.github/workflows/refresh.yml`: every hour, GitHub runs the script, wraps the page as a full
  website and publishes it to GitHub Pages. If a source is down, the run fails and the last good
  version stays online.

## Commands

```bash
python3 update_rates.py                 # refresh prices in index.html
python3 update_rates.py --site _site    # also build the website into _site/
```

## Before promoting it publicly

- Check that Wise's terms allow using its comparison data this way.
- Replace the "Ir a…" links in `index.html` (`LINKS`) with your referral links.
