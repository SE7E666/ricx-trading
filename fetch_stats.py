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
LOG_FILE   = SCRIPT_DIR / "ricx_update.log"
API_BASE   = "https://www.myfxbook.com/api"
HEADERS    = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.myfxbook.com/",
}

PT_MONTHS = {1:"Jan",2:"Fev",3:"Mar",4:"Abr",5:"Mai",6:"Jun",
             7:"Jul",8:"Ago",9:"Set",10:"Out",11:"Nov",12:"Dez"}

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
    try:
        v = float(pct)
        return f"{v:.1f}%" if v > 0 else "--"
    except:
        return "--"

def months_since(d):
    if not d:
        return "--"
    for fmt in ("%m/%d/%Y %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            dt = datetime.strptime(str(d).strip()[:16], fmt[:len(fmt)])
            return str(max(1, (datetime.now()-dt).days // 30))
        except:
            pass
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(str(d).strip()[:10], fmt)
            return str(max(1, (datetime.now()-dt).days // 30))
        except:
            pass
    return "--"

def do_logout(token, cookies, headers):
    try:
        requests.get(
            f"{API_BASE}/logout.json",
            params={"session": token},
            cookies=cookies,
            headers=headers,
            timeout=5
        )
    except:
        pass

def get_monthly_chart(token, cookies, headers):
    """Fetch daily gain data and aggregate into monthly chart points."""
    end   = datetime.now()
    # Use a wide window -- myfxbook will return data from account start
    start = end.replace(year=end.year - 2)

    try:
        r = requests.get(
            f"{API_BASE}/get-daily-gain.json",
            params={
                "session": session_token_for_chart(token),
                "id":      ACCOUNT_ID,
                "start":   start.strftime("%Y-%m-%d"),
                "end":     end.strftime("%Y-%m-%d"),
            },
            headers=headers,
            cookies=cookies,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()

        if data.get("error"):
            print(f"  Chart API: {data.get('message','erro desconhecido')}")
            return None

        daily = data.get("dailyGain", [])
        if not daily:
            print("  Chart API: sem dados diários")
            return None

        print(f"  Chart API: {len(daily)} entradas diárias recebidas")
        if daily:
            print(f"  Amostra: {daily[0]}")

        # Each entry: [date_str, cumulative_gain_pct]
        # myfxbook returns dates as MM/DD/YYYY — handle multiple formats
        DATE_FMTS = ["%m/%d/%Y", "%Y-%m-%d", "%d/%m/%Y"]
        def parse_date(s):
            s = str(s).strip()[:10]
            for fmt in DATE_FMTS:
                try:
                    return datetime.strptime(s, fmt)
                except ValueError:
                    continue
            return None

        # Group by month — keep last value of each month (= cumulative at month end)
        # API can return: list-of-dicts, list of [dict], or list of [date, value]
        monthly = {}
        skipped = 0
        for entry in daily:
            try:
                # Case 1: [[{date:.., value:..}], ...] — list containing one dict
                if isinstance(entry, list) and len(entry) > 0 and isinstance(entry[0], dict):
                    e = entry[0]
                    date_str = e.get("date", "")
                    gain_pct = float(e.get("value", 0))
                # Case 2: [{date:.., value:..}, ...] — direct dict
                elif isinstance(entry, dict):
                    date_str = entry.get("date", "")
                    gain_pct = float(entry.get("value", 0))
                # Case 3: [[date, value], ...] — plain list
                elif isinstance(entry, list) and len(entry) >= 2:
                    date_str = str(entry[0])
                    gain_pct = float(entry[1])
                else:
                    skipped += 1
                    continue
                dt = parse_date(date_str)
                if dt is None:
                    skipped += 1
                    continue
                monthly[(dt.year, dt.month)] = round(gain_pct, 2)
            except Exception:
                skipped += 1
                continue
        if skipped:
            print(f"  Aviso: {skipped} entradas ignoradas")

        if not monthly:
            return None

        chart_data = []
        for (y, m) in sorted(monthly.keys()):
            label = f"{PT_MONTHS[m]}/{str(y)[2:]}"
            chart_data.append({"date": label, "value": monthly[(y, m)]})

        print(f"  Chart data: {len(chart_data)} meses ({chart_data[0]['date']} → {chart_data[-1]['date']})")
        return chart_data if len(chart_data) >= 2 else None

    except Exception as e:
        print(f"  Erro ao buscar chart data: {e}")
        return None

def session_token_for_chart(token):
    """Return token as-is (helper for clarity)."""
    return token

def get_winrate(token, cookies, headers):
    """Calculate winrate from closed trade history."""
    try:
        r = requests.get(
            f"{API_BASE}/get-history.json",
            params={"session": token, "id": ACCOUNT_ID},
            headers=headers,
            cookies=cookies,
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
        if data.get("error"):
            print(f"  Winrate API: {data.get('message','')}")
            return "--"
        history = data.get("history", [])
        if not history:
            print("  Winrate API: sem histórico")
            return "--"
        won  = sum(1 for t in history if float(t.get("profit", 0)) > 0)
        lost = sum(1 for t in history if float(t.get("profit", 0)) <= 0)
        total = won + lost
        if total == 0:
            return "--"
        wr = won / total * 100
        print(f"  Winrate: {won}W / {lost}L de {total} trades = {wr:.1f}%")
        return f"{wr:.1f}%"
    except Exception as e:
        print(f"  Erro winrate: {e}")
        return "--"

def write_log(stats, error_msg=""):
    """Write (overwrite) a single log file with last run results."""
    success = not error_msg
    lines = [
        "=" * 52,
        "  RICX Stats Update Log",
        f"  {