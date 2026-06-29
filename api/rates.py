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
        "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
    })

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        # Try multiple patterns
        patterns = [
            # Pattern 1: JSON-LD schema
            r'"price"\s*:\s*"?([\d]+[.,][\d]+)"?',
            # Pattern 2: data attributes
            r'data-sell="([\d]+[.,][\d]+)"',
            r'data-buy="([\d]+[.,][\d]+)"',
            # Pattern 3: common HTML patterns on doviz.com
            r'<span[^>]*class="[^"]*sell[^"]*"[^>]*>([\d]+[.,][\d]+)',
            r'Satış[^<]*<[^>]+>([\d,\.]+)',
            r'([\d]{2}[.,][\d]{2,4})\s*</span>',
            # Pattern 4: any number that looks like TRY rate (30-60 range)
            r'"sell_price"\s*:\s*([\d]+\.[\d]+)',
            r'"satis"\s*:\s*"?([\d]+[.,][\d]+)"?',
            r'"alis"\s*:\s*"?([\d]+[.,][\d]+)"?',
        ]

        numbers = []
        for pattern in patterns:
            matches = re.findall(pattern, html, re.IGNORECASE)
            for m in matches:
                val = float(m.replace(",", "."))
                if 20.0 < val < 200.0:  # reasonable TRY range
                    numbers.append(val)

        if len(numbers) >= 2:
            numbers.sort()
            return {"buy": numbers[0], "sell": numbers[-1]}
        elif len(numbers) == 1:
            return {"buy": round(numbers[0] * 0.97, 4), "sell": numbers[0]}

    except Exception as e:
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
