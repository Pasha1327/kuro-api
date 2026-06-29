from http.server import BaseHTTPRequestHandler
import urllib.request
import json
import re

BANKS = [
    {"name": "Ziraat Bankası", "short": "Ziraat", "slug": "ziraat-bankasi",  "type": "state"},
    {"name": "Halkbank",       "short": "Halk",   "slug": "halkbank",        "type": "state"},
    {"name": "Vakıfbank",      "short": "Vakıf",  "slug": "vakifbank",       "type": "state"},
    {"name": "İş Bankası",     "short": "İşbank", "slug": "isbankasi",       "type": "private"},
    {"name": "Garanti BBVA",   "short": "Garanti","slug": "garanti-bbva",    "type": "private"},
    {"name": "Akbank",         "short": "Akbank", "slug": "akbank",          "type": "private"},
    {"name": "Yapıkredi",      "short": "YKB",    "slug": "yapikredi",       "type": "private"},
    {"name": "QNB Finansbank", "short": "Finans", "slug": "qnb-finansbank",  "type": "private"},
]

def fetch_rate(bank_slug, currency):
    currency_map = {
        "USD": "amerikan-dolari",
        "EUR": "euro",
        "RUB": "rus-rublesi",
    }
    currency_slug = currency_map.get(currency, "amerikan-dolari")
    url = f"https://kur.doviz.com/{bank_slug}/{currency_slug}"

    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Accept-Encoding": "identity",
    })

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Primary pattern: "Alış / Satış" block with two numbers
        # Matches: 46,2459 / 47,1815
        pattern = r'Alış\s*/\s*Satış\s*<[^>]+>\s*([\d]+[,.][\d]+)\s*/\s*([\d]+[,.][\d]+)'
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            buy  = float(match.group(1).replace(",", "."))
            sell = float(match.group(2).replace(",", "."))
            if 10 < buy < 500 and 10 < sell < 500:
                return {"buy": buy, "sell": sell}

        # Secondary: look for the pattern without tags between
        pattern2 = r'Alış\s*/\s*Satış[^0-9]*([\d]+[,.][\d]+)\s*/\s*([\d]+[,.][\d]+)'
        match2 = re.search(pattern2, html, re.IGNORECASE | re.DOTALL)
        if match2:
            buy  = float(match2.group(1).replace(",", "."))
            sell = float(match2.group(2).replace(",", "."))
            if 10 < buy < 500 and 10 < sell < 500:
                return {"buy": buy, "sell": sell}

        # Tertiary: find the large price number shown as current rate
        # The main rate shown big on page e.g. "47,1815"
        pattern3 = r'<strong[^>]*>\s*([\d]{2}[,.][\d]{4})\s*</strong>'
        matches3 = re.findall(pattern3, html)
        valid = [float(m.replace(",", ".")) for m in matches3 if 10 < float(m.replace(",", ".")) < 500]
        if len(valid) >= 2:
            valid.sort()
            return {"buy": valid[0], "sell": valid[-1]}
        elif len(valid) == 1:
            sell = valid[0]
            return {"buy": round(sell * 0.976, 4), "sell": sell}

    except Exception:
        pass

    return None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        currency = "USD"
        if "currency=" in self.path:
            currency = self.path.split("currency=")[-1].split("&")[0].upper()
        if currency not in ("USD", "EUR", "RUB"):
            currency = "USD"

        results = []
        for bank in BANKS:
            rate = fetch_rate(bank["slug"], currency)
            if rate:
                results.append({
                    "name":  bank["name"],
                    "short": bank["short"],
                    "type":  bank["type"],
                    "buy":   rate["buy"],
                    "sell":  rate["sell"],
                })

        results.sort(key=lambda x: x["sell"])

        body = json.dumps({
            "currency": currency,
            "banks": results,
        }, ensure_ascii=False).encode("utf-8")

        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        pass
