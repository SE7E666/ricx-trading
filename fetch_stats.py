"""
RICX Trading Bot -- myfxbook Stats Fetcher
===========================================
EXECUTA LOCALMENTE (na tua maquina) onde o myfxbook e acessivel.
Depois faz git push automatico para atualizar o site.

Uso: duplo clique em atualizar_stats.bat
     ou: python fetch_stats.py
"""

import requests, json, sys, time, os
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
    try: v=float(v); return f"+{v:.1f}%" if v>=0 else f"{v:.1f}%"
    except: return "--"

def fmt_dd(v):
    try: return f"-{abs(float(v)):.1f}%"
    except: return "--"

def fmt_wr(won,total):
    try: return f"{won/total*100:.1f}%" if total>0 else "--"
    except: return "--"

def months_since(d):
    if not d: return "--"
    try:
        dt = datetime.strptime(d[:10],"%Y-%m-%d")
        return str(max(1,(datetime.now()-dt).days//30))
    except: return "--"

def main():
    print("="*50)
    print("  RICX Stats Fetcher")
    print(f"  {datetime.now():%Y-%m-%d %H:%M:%S}")
    print("="*50)

    email, pw = load_creds()
    http = requests.Session()
    http.headers.update(HEADERS)

    print("A fazer login no myfxbook...")
    try:
        r = http.get(f"{API_BASE}/login.json", params={"email":email,"password":pw}, timeout=20)
        r.raise_for_status()
        d = r.json()
    except Exception as e:
        print(f"ERRO login: {e}"); sys.exit(1)

    if d.get("error"):
        print(f"Login falhou: {d.get('message')}"); sys.exit(1)

    token = d["session"]
    print(f"Login OK. Token: {token[:8]}...")
    time.sleep(0.8)

    print("A buscar contas...")
    try:
        r2 = http.get(f"{API_BASE}/get-my-accounts.json", params={"session":token}, timeout=20)
        r2.raise_for_status()
        adata = r2.json()
    except Exception as e:
        print(f"ERRO contas: {e}"); sys.exit(1)
    finally:
        try: http.get(f"{API_BASE}/logout.json", params={"session":token}, timeout=5)
        except: pass

    if adata.get("error"):
        print(f"ERRO: {adata.get('message')}"); sys.exit(1)

    accounts = adata.get("accounts",[])
    if not accounts:
        print("Nenhuma conta encontrada."); sys.exit(1)

    print(f"Contas: {len(accounts)}")
    for a in accounts:
        print(f"  ID={a.get('id')} | {a.get('name')} | gain={a.get('gain')}")

    acc = next((a for a in accounts if str(a.get("id"))==str(ACCOUNT_ID)), accounts[0])
    won  = int(acc.get("wonTrades",0) or 0)
    lost = int(acc.get("lostTrades",0) or 0)

    stats = {
        "gain":          fmt_gain(acc.get("gain",0)),
        "months":        months_since(acc.get("firstTradeDate","")),
        "winrate":       fmt_wr(won, won+lost),
        "drawdown":      fmt_dd(acc.get("drawdown",0)),
        "trades":        str(won+lost) if (won+lost)>0 else "--",
        "profit_factor": f"{float(acc.get('profitFactor',0)):.2f}" if acc.get("profitFactor") else "--",
        "balance":       f"${float(acc.get('balance',0)):,.2f}",
        "profit":        f"${float(acc.get('profit',0)):,.2f}",
        "last_updated":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "account_name":  acc.get("name","RICX"),
        "currency":      acc.get("currency","USD"),
    }

    json.dump(stats, open(OUTPUT,"w",encoding="utf-8"), indent=2, ensure_ascii=False)
    print("\nstats.json atualizado!")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print("\nConcluido!")

if __name__=="__main__":
    main()
