"""
RICX Trading Bot -- myfxbook Stats Fetcher
===========================================
Acessa a pagina PUBLICA do robot no myfxbook via browser real (Playwright).
Nao precisa de login. Funciona mesmo com IPs de cloud providers.

Requisitos:
  pip install playwright
  playwright install --with-deps chromium
"""

import json
import sys
import re
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
OUTPUT     = SCRIPT_DIR / "stats.json"

# URL publica da conta RICX no myfxbook
MYFXBOOK_URL = "https://www.myfxbook.com/members/RIppeR_SE7E/rycx-axi/11746315"


def parse_percent(text):
    """Extrai numero de string como '52.17%' ou '-8.46%'"""
    if not text:
        return None
    text = text.strip().replace(",", ".")
    m = re.search(r"[-+]?\d+\.?\d*", text)
    return float(m.group()) if m else None


def format_gain(v):
    if v is None:
        return "--"
    sign = "+" if v >= 0 else ""
    return f"{sign}{v:.1f}%"


def format_drawdown(v):
    if v is None:
        return "--"
    return f"-{abs(v):.1f}%"


def months_since(date_str):
    """Calcula meses desde uma data no formato 'MM/YYYY' ou 'YYYY-MM-DD'"""
    if not date_str:
        return "--"
    try:
        # tenta MM/YYYY primeiro
        for fmt in ("%m/%Y", "%Y-%m-%d", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(date_str.strip()[:10], fmt[:len(date_str.strip()[:10])])
                break
            except ValueError:
                continue
        else:
            return "--"
        delta = datetime.now() - dt
        return str(max(1, delta.days // 30))
    except Exception:
        return "--"


def main():
    print("=" * 50)
    print("  RICX -- myfxbook Public Page Scraper")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("ERRO: playwright nao instalado. Execute: pip install playwright")
        sys.exit(1)

    stats = {
        "gain": "--", "months": "--", "winrate": "--",
        "drawdown": "--", "trades": "--", "profit_factor": "--",
        "balance": "--", "profit": "--",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "account_name": "RICX", "currency": "USD",
    }

    with sync_playwright() as p:
        print("Abrindo browser Chromium...")
        browser = p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        page = browser.new_page(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )

        # Interceptar chamadas de API do myfxbook para capturar dados JSON
        captured = {}

        def handle_response(response):
            url = response.url
            if "myfxbook.com" in url and any(k in url for k in ["get-gain", "get-data", "account-data", "stats"]):
                try:
                    body = response.text()
                    if body and body.strip().startswith("{"):
                        captured[url] = json.loads(body)
                        print(f"  Capturado: {url[:80]}")
                except Exception:
                    pass

        page.on("response", handle_response)

        print(f"Navegando para: {MYFXBOOK_URL}")
        try:
            page.goto(MYFXBOOK_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(4000)  # esperar carregamento JS
        except Exception as e:
            print(f"AVISO ao navegar: {e}")

        html = page.content()
        print(f"HTML carregado: {len(html)} chars")

        # ── Extrair dados do DOM ──
        def safe_text(selector):
            try:
                el = page.query_selector(selector)
                return el.inner_text().strip() if el else None
            except Exception:
                return None

        def safe_attr(selector, attr):
            try:
                el = page.query_selector(selector)
                return el.get_attribute(attr) if el else None
            except Exception:
                return None

        # Gain total -- myfxbook usa #totalGain ou elemento com essa classe
        gain_raw = (
            safe_text("#totalGain") or
            safe_text("[id*='gain']") or
            safe_text(".gain") or
            safe_text("[class*='gain']")
        )

        # Drawdown
        dd_raw = (
            safe_text("#maxDrawdown") or
            safe_text("[id*='drawdown']") or
            safe_text("[class*='drawdown']")
        )

        # Trades
        trades_raw = (
            safe_text("#totalTrades") or
            safe_text("[id*='trades']") or
            safe_text("[class*='trades']")
        )

        # Win rate / profitability
        wr_raw = (
            safe_text("#profitability") or
            safe_text("[id*='profit']") or
            safe_text("[class*='profit']")
        )

        print(f"DOM -- gain={gain_raw} dd={dd_raw} trades={trades_raw} wr={wr_raw}")

        # Tentar extrair de texto do HTML via regex se DOM nao encontrou
        if not gain_raw:
            # Procurar padroes de stats no HTML
            # myfxbook normalmente tem: "Gain</td><td>52.17%"
            m = re.search(r'(?i)gain[^<]{0,50}>([+-]?\d+\.?\d*%)', html)
            if m:
                gain_raw = m.group(1)
                print(f"Gain extraido via regex: {gain_raw}")

        if not dd_raw:
            m = re.search(r'(?i)drawdown[^<]{0,100}>([+-]?\d+\.?\d*%)', html)
            if m:
                dd_raw = m.group(1)

        if not trades_raw:
            m = re.search(r'(?i)trades[^<]{0,100}>([\d,]+)', html)
            if m:
                trades_raw = m.group(1)

        browser.close()

    # ── Processar valores extraidos ──
    gain_v = parse_percent(gain_raw)
    dd_v   = parse_percent(dd_raw)

    if gain_v is not None:
        stats["gain"]     = format_gain(gain_v)
    if dd_v is not None:
        stats["drawdown"] = format_drawdown(dd_v)
    if trades_raw:
        t = trades_raw.replace(",", "").strip()
        if t.isdigit():
            stats["trades"] = t
    if wr_raw:
        wr_v = parse_percent(wr_raw)
        if wr_v is not None:
            stats["winrate"] = f"{wr_v:.1f}%"

    # Verificar se conseguiu dados reais
    got_data = any(stats[k] != "--" for k in ["gain", "drawdown", "trades"])
    if not got_data:
        print("AVISO: Nao foi possivel extrair dados da pagina publica.")
        print("A tentar API autenticada como fallback...")
        result = _try_api_fallback()
        if result:
            stats.update(result)
            got_data = True

    stats["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print("\nstats.json:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    if not got_data:
        print("\nAVISO: Stats mantidos como '--'. Dados nao disponiveis.")
        # Nao falha