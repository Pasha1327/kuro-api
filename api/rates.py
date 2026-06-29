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

def fetch_html(bank_slug, currency):
    currency_slug = CURRENCY_SLUGS.get(currency, "amerikan-dolari")
    url = f"https://kur.doviz.com/{bank_slug}/{currency_slug}"
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "tr-TR,tr;q=0.9",
        "Accept-Encoding": "identity",
    })
    with urllib.request.urlopen(req, timeout=12) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def extract_rate(html):
    # Strategy: find JSON data blocks with buying/selling
    # doviz.com embeds data in script tags as JSON

    # Pattern 1: Look for data in script tags - "buying" and "selling" fields
    script_blocks = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE)
    
    for block in script_blocks:
        # Try to find buying/selling pattern
        m = re.search(r'"buying"\s*:\s*([\d.]+)[^}]*"selling"\s*:\s*([\d.]+)', block)
        if m:
            buy = float(m.group(1))
            sell = float(m.group(2))
            if 5 < buy < 500 and 5 < sell < 500 and sell >= buy:
                return {"buy": buy, "sell": sell}
        
        # Try alis/satis
        m = re.search(r'"alis"\s*:\s*"?([\d.]+)"?[^}]*"satis"\s*:\s*"?([\d.]+)"?', block, re.IGNORECASE)
        if m:
            buy = float(m.group(1))
            sell = float(m.group(2))
            if 5 < buy < 500 and 5 < sell < 500 and sell >= buy:
                return {"buy": buy, "sell": sell}

        # Try "data" array with buy/sell
        m = re.search(r'"buy"\s*:\s*([\d.]+)[^}]*"sell"\s*:\s*([\d.]+)', block)
        if m:
            buy = float(m.group(1))
            sell = float(m.group(2))
            if 5 < buy < 500 and 5 < sell < 500 and sell >= buy:
                return {"buy": buy, "sell": sell}

    # Pattern 2: Look anywhere in HTML for JSON-like buying/selling
    m = re.search(r'"buying"\s*:\s*([\d.]+)[^}]{0,50}"selling"\s*:\s*([\d.]+)', html)
    if m:
        buy = float(m.group(1))
        sell = float(m.group(2))
        if 5 < buy < 500 and 5 < sell < 500 and sell >= buy:
            return {"buy": buy, "sell": sell}

    # Pattern 3: data-buying / data-selling attributes
    m = re.search(r'data-buying="([\d.]+)"[^"]*data-selling="([\d.]+)"', html)
    if not m:
        m = re.search(r'data-selling="([\d.]+)"[^"]*data-buying="([\d.]+)"', html)
        if m:
            sell = float(m.group(1))
            buy = float(m.group(2))
            if 5 < buy < 500 and 5 < sell < 500:
                return {"buy": buy, "sell": sell}
    if m:
        buy = float(m.group(1))
        sell = float(m.group(2))
        if 5 < buy < 500 and 5 < sell < 500:
            return {"buy": buy, "sell": sell}

    return None


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        currency = "USD"
        if "currency=" in self.path:
            currency = self.path.split("currency=")[-1].split("&")[0].upper()
        if currency not in ("USD", "EUR", "RUB"):
            currency = "USD"

        # Debug: search for numbers in range in HTML
        if "debug=1" in self.path:
            try:
                html = fetch_html("garanti-bbva", currency)
                # Find all occurrences of numbers in TRY range with context
                findings = []
                for m in re.finditer(r'(buying|selling|alis|satis|buy|sell)["\s:]+([0-9.]+)', html, re.IGNORECASE):
                    val = float(m.group(2)) if m.group(2) else 0
                    if 5 < val < 500:
                        start = max(0, m.start() - 30)
                        end = min(len(html), m.end() + 30)
                        findings.append({
                            "key": m.group(1),
                            "val": val,
                            "ctx": html[start:end]
                        })
                body = json.dumps({
                    "html_length": len(html),
                    "findings": findings[:20]
                }, ensure_ascii=False).encode("utf-8")
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
                rate = extract_rate(html)
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
