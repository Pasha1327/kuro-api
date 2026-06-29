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

CURRENCY_SLUGS = {
    "USD": "amerikan-dolari",
    "EUR": "euro",
    "RUB": "rus-rublesi",
}

CURRENCY_NAMES = {
    "USD": ["Amerikan Doları", "USD"],
    "EUR": ["Euro", "EUR"],
    "RUB": ["Rus Rublesi", "RUB"],
}

def fetch_bank_page(bank_slug, currency):
    currency_slug = CURRENCY_SLUGS.get(currency, "amerikan-dolari")
    url = f"https://kur.doviz.com/{bank_slug}/{currency_slug}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
        "Accept-Encoding": "identity",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
    })
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def fetch_bank_list_page(bank_slug, currency):
    """Fetch the bank's currency list page (e.g. /garanti-bbva) to find all rates"""
    url = f"https://kur.doviz.com/{bank_slug}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Accept-Encoding": "identity",
    })
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def extract_rate_from_html(html, currency):
    """Extract buy/sell rate from doviz.com HTML"""
    
    # Pattern 1: Table row with currency name and two numbers
    # Matches rows like: | Garanti BBVA Amerikan Doları USD... | 44,9550 | 46,9550 | 21:17 |
    currency_names = CURRENCY_NAMES.get(currency, ["USD"])
    
    for name in currency_names:
        # Look for the currency in a table row context
        # Pattern: currency_name followed by two decimal numbers
        pattern = rf'{re.escape(name)}[^|]*\|\s*([\d]{{2,3}}[,.][\d]{{2,4}})\s*\|\s*([\d]{{2,3}}[,.][\d]{{2,4}})'
        match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        if match:
            buy  = float(match.group(1).replace(",", "."))
            sell = float(match.group(2).replace(",", "."))
            if 5 < buy < 1000 and 5 < sell < 1000:
                return {"buy": buy, "sell": sell}

    # Pattern 2: JSON data embedded in page
    # doviz.com sometimes embeds __NEXT_DATA__ or similar
    json_patterns = [
        r'"buying"\s*:\s*([\d]+\.[\d]+)[^}]*?"selling"\s*:\s*([\d]+\.[\d]+)',
        r'"buy"\s*:\s*([\d]+\.[\d]+)[^}]*?"sell"\s*:\s*([\d]+\.[\d]+)',
        r'"alis"\s*:\s*"?([\d,]+)"?[^}]*?"satis"\s*:\s*"?([\d,]+)"?',
        r'"alış"\s*:\s*"?([\d,]+)"?[^}]*?"satış"\s*:\s*"?([\d,]+)"?',
    ]
    for pat in json_patterns:
        m = re.search(pat, html, re.IGNORECASE)
        if m:
            buy  = float(m.group(1).replace(",", "."))
            sell = float(m.group(2).replace(",", "."))
            if 5 < buy < 1000 and 5 < sell < 1000:
                return {"buy": buy, "sell": sell}

    # Pattern 3: Two consecutive TRY-range numbers near each other
    # Find all numbers in valid TRY range
    all_numbers = re.findall(r'\b([\d]{2,3}[,.][\d]{2,4})\b', html)
    valid = []
    for n in all_numbers:
        val = float(n.replace(",", "."))
        if 5 < val < 1000:
            valid.append(val)
    
    # Find pairs where sell > buy and difference is reasonable (0.1-10%)
    for i in range(len(valid) - 1):
        buy = valid[i]
        sell = valid[i+1]
        if sell > buy and 0.001 < (sell - buy) / buy < 0.15:
            return {"buy": buy, "sell": sell}

    return None

def fetch_rate(bank_slug, currency):
    try:
        html = fetch_bank_page(bank_slug, currency)
        return extract_rate_from_html(html, currency)
    except Exception:
        pass
    
    # Fallback: try bank list page
    try:
        html = fetch_bank_list_page(bank_slug, currency)
        return extract_rate_from_html(html, currency)
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

        # Debug mode
        if "debug=1" in self.path:
            try:
                html = fetch_bank_page("garanti-bbva", currency)
                body = json.dumps({"html_length": len(html), "sample": html[:2000]}, ensure_ascii=False).encode("utf-8")
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
