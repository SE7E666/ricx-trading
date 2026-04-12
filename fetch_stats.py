"""
RICX Trading Bot -- myfxbook Stats Fetcher
"""

import requests, json, sys, os
from pathlib import Path
from datetime import datetime

ACCOUNT_ID = 11746315
SCRIPT_DIR = Path(__file__).parent
ENV_FILE   = SCRIPT_DIR / ".env"
OUTPUT     = SCRIPT_DIR / "stats.json"
API_BASE   = "https://www.myfxbook.com/api"
HEADERS    = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.myfxbook.com/",
}

def load_creds():
    email = os.environ.get("MYFXBOOK_EMAIL","").strip()
    pw    = os.environ.get("MYFXBOOK_PASSWORD","").strip()
    if email and pw:
        return email, pw
    if ENV_FILE.exists():
        c = {}
        for line in open(ENV_FILE):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k,_,v = line.partition("=")
                c[k.strip()] = v.strip().strip('"').strip("'")
        email = c.get("MYFXBOOK_EMAIL","")
        pw    = c.get("MYFXBOOK_PASSWORD","")
        if email and pw:
            return email, pw
    print("ERRO: Cria o ficheiro .env com MYFXBOOK_EMAIL e MYFXBOOK_PASSWORD")
    sys.exit(1)

def fmt_gain(v):
    try:
        v = float(v)
        return f"+{v:.1f}%" if v >= 0 else f"{v:.1f}%"
    except:
        return "--"

def fmt_dd(v):
    try:
        return f"-{abs(float(v)):.1f}%"
    except:
        return "--"

def fmt_wr(won, total):
    try:
        return f"{won/total*100:.1f}%" if total > 0 else "--"
    except:
        return "--"

def fmt_wr_pct(pct):
    """Format winrate from a direct percentage value (e.g. 65.5 -> '65.5%')"""
    try:
        v = float(pct)
        return f"{v:.1f}%" if v > 0 else "--"
    except:
        return "--"

def months_since(d):
    """Parse multiple date formats myfxbook might return."""
    if not d:
        return "--"
    for fmt in ("%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(str(d).strip()[:16], fmt[:len(fmt)])
            return str(max(1, (datetime.now()-dt).days // 30))
        except:
            pass
    # Try just first 10 chars
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(str(d).strip()[:10], fmt)
            return str(max(1, (datetime.now()-dt).days // 30))
        except:
            pass
    return "--"

def main():
    print("="*50)
    print("  RICX Stats Fetcher")
    print(f"  {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("="*50)

    email, pw = load_creds()

    print("A fazer login no myfxbook...")
    try:
        r = requests.get(
            f"{API_BASE}/login.json",
            params={"email": email, "password": pw},
            headers=HEADERS,
            timeout=20,
        )
        r.raise_for_status()
        d = r.json()
        login_cookies = r.cookies
    except Exception as e:
        print(f"ERRO login: {e}")
        sys.exit(1)

    if d.get("error"):
        print(f"Login falhou: {d.get('message')}")
        sys.exit(1)

    from urllib.parse import unquote
    token = unquote(d["session"])
    print(f"Login OK. Token: {token[:8]}...")
    print(f"Cookies recebidos: {list(login_cookies.keys())}")

    xsrf = login_cookies.get("XSRF-TOKEN", "")
    request_headers = dict(HEADERS)
    if xsrf:
        request_headers["X-XSRF-TOKEN"] = xsrf
        print("XSRF-TOKEN encontrado, a adicionar como header.")

    print("A buscar contas...")
    adata = None
    try:
        r2 = requests.get(
            f"{API_BASE}/get-my-accounts.json",
            params={"session": token},
            headers=request_headers,
            cookies=login_cookies,
            timeout=20,
        )
        r2.raise_for_status()
        adata = r2.json()
        print(f"Resposta: {adata.get('error')} | {adata.get('message','')}")
    except Exception as e:
        print(f"ERRO contas: {e}")
        sys.exit(1)
    finally:
        try:
            requests.get(
                f"{API_BASE}/logout.json",
                params={"session": token},
                cookies=login_cookies,
                headers=request_headers,
                timeout=5
            )
        except:
            pass

    if adata.get("error"):
        print(f"ERRO: {adata.get('message')}")
        sys.exit(1)

    accounts = adata.get("accounts", [])
    if not accounts:
        print("Nenhuma conta encontrada.")
        sys.exit(1)

    print(f"Contas: {len(accounts)}")
    for a in accounts:
        print(f"  ID={a.get('id')} | {a.get('name')} | gain={a.get('gain')}")

    acc = next((a for a in accounts if str(a.get("id")) == str(ACCOUNT_ID)), accounts[0])

    # DEBUG: print all fields so we know what's available
    print("\n--- Campos disponíveis para a conta RYCX AXI ---")
    for k, v in acc.items():
        print(f"  {k}: {v}")
    print("---")

    # Trades: try wonTrades+lostTrades, then longTrades+shortTrades
    won  = int(acc.get("wonTrades", 0) or 0)
    lost = int(acc.get("lostTrades", 0) or 0)
    total_trades = won + lost
    if total_trades == 0:
        long_t  = int(acc.get("longTrades", 0) or 0)
        short_t = int(acc.get("shortTrades", 0) or 0)
        total_trades = long_t + short_t
        won = long_t  # use as proxy if no won/lost split

    # Winrate: try direct percentage field first
    wr_pct = acc.get("wonTradesPercent") or acc.get("profitableTradesPercent")
    if wr_pct and float(wr_pct) > 0:
        winrate = fmt_wr_pct(wr_pct)
    elif won + lost > 0:
        winrate = fmt_wr(won, won + lost)
    else:
        # Try to get from public stats endpoint
        winrate = "--"

    # Months: try firstTradeDate then creationDate then tracking
    date_field = (acc.get("firstTradeDate") or
                  acc.get("creationDate") or
                  acc.get("tracking") or "")
    months = months_since(date_field)

    # Monthly gain (myfxbook field: "monthly")
    monthly_raw = acc.get("monthly") or acc.get("avgMonthlyGain") or acc.get("monthlyGain")
    if monthly_raw:
        try:
            monthly = f"+{abs(float(monthly_raw)):.2f}%"
        except:
            monthly = "--"
    else:
        monthly = "--"

    # Winrate: try multiple field names
    wr_direct = (acc.get("wonTradesPercent") or acc.get("profitableTradesPercent") or
                 acc.get("winRate") or acc.get("winrate"))
    if wr_direct and float(str(wr_direct).replace('%','')) > 0:
        try:
            winrate = f"{float(str(wr_direct).replace('%','')):.1f}%"
        except:
            pass  # keep winrate from earlier calculation

    stats = {
        "gain":         fmt_gain(acc.get("gain", 0)),
        "monthly":      monthly,
        "months":       months,
        "winrate":      winrate,
        "drawdown":     fmt_dd(acc.get("drawdown", 0)),
        "balance":      f"${float(acc.get('balance', 0)):,.2f}",
        "profit":       f"${float(acc.get('profit', 0)):,.2f}",
        "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "account_name": acc.get("name", "RICX"),
        "currency":     acc.get("currency", "USD"),
    }

    # Escrita atómica: escreve em ficheiro temporário e 