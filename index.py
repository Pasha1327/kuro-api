from http.server import BaseHTTPRequestHandler
import urllib.request
import json
import re

BANKS = [
    {"name": "Ziraat Bankası", "short": "Ziraat", "slug": "ziraat-bankasi", "type": "state"},
    {"name": "Halkbank",       "short": "Halk",   "slug": "halkbank",       "type": "state"},
    {"name": "Vakıfbank",      "short": "Vakıf",  "slug": "vakifbank",      "type": "state"},
    {"name": "İş Bankası",     "short": "İşbank", "slug": "isbankasi",      "type": "private"},
    {"name": "Garanti BBVA",   "short": "Garanti","slug": "garanti-bbva",   "type": "private"},
    {"name": "Akbank",         "short": "Akbank", "slug": "akbank",         "type": "private"},
    {"name": "Yapıkredi",      "short": "YKB",    "slug": "yapikredi",      "type": "private"},
    {"name": "QNB Finansbank", "short": "Finans", "slug": "qnb-finansbank", "type": "private"},
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
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "tr-TR,tr;q=0.9",
    })

    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            html = resp.read().decode("utf-8")

        pattern = r'Alış\s*/\s*Satış\s*([\d,\.]+)\s*/\s*([\d,\.]+)'
        match = re.search(pattern, html)
        if match:
            buy_str  = match.group(1).replace(",", ".")
            sell_str = match.group(2).replace(",", ".")
            return {"buy": float(buy_str), "sell": float(sell_str)}
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
