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

def fetch_html(bank_slug, currency):
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

    with urllib.request.urlopen(req, timeout=10) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def parse_rate(html):
    patterns = [
        r'Alış\s*/\s*Satış[^0-9]*([\d]+[,.][\d]+)\s*/\s*([\d]+[,.][\d]+)',
        r'"alis"\s*:\s*"?([\d]+[,.][\d]+)"?[^}]*"satis"\s*:\s*"?([\d]+[,.][\d]+)"?',
        r'data-alis="([\d]+[,.][\d]+)"[^"]*data-satis="([\d]+[,.][\d]+)"',
        r'"buying"\s*:\s*([\d]+\.[\d]+)[^}]*"selling"\s*:\s*([\d]+\.[\d]+)',
        r'"buy"\s*:\s*([\d]+\.[\d]+)[^}]*"sell"\s*:\s*([\d]+\.[\d]+)',
    ]
    for p in patterns:
        m = re.search(p, html, re.IGNORECASE | re.DOTALL)
        if m:
            buy  = float(m.group(1).replace(",", "."))
            sell = float(m.group(2).replace(",", "."))
            if 10 < buy < 500 and 10 < sell < 500:
                return {"buy": buy, "sell": sell}
    return None

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        currency = "USD"
        if "currency=" in self.path:
            currency = self.path.split("currency=")[-1].split("&")[0].upper()
        if currency not in ("USD", "EUR", "RUB"):
            currency = "USD"

        # Debug mode: return raw HTML of first bank
        if "debug=1" in self.path:
            try:
                html = fetch_html("ziraat-bankasi", currency)
                # Return first 3000 chars to see structure
                snippet = html[:3000]
                body = json.dumps({"html": snippet}).encode("utf-8")
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(body)
            return

        results = []
        for bank in BANKS:
            try:
                html = fetch_html(bank["slug"], currency)
                rate = parse_rate(html)
                if rate:
                    results.append({
                        "name":  bank["name"],
                        "short": bank["short"],
                        "type":  bank["type"],
                        "buy":   rate["buy"],
                        "sell":  rate["sell"],
                    })
            except Exception:
                pass

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
