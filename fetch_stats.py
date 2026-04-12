"""
RICX Trading Bot — myfxbook Stats Fetcher
==========================================
Busca os dados de performance do myfxbook via API oficial
e salva em stats.json para o site exibir automaticamente.

Uso:
  1. Cria um ficheiro .env na mesma pasta com as tuas credenciais
  2. Executa: python fetch_stats.py
  3. O ficheiro stats.json sera atualizado automaticamente

Requisitos:
  pip install requests
"""

import requests
import json
import sys
import time
from pathlib import Path
from datetime import datetime

# ─── CONFIGURACAO ────────────────────────────────────────────────
ACCOUNT_ID = 11746315
SCRIPT_DIR = Path(__file__).parent
ENV_FILE   = SCRIPT_DIR / ".env"
OUTPUT     = SCRIPT_DIR / "stats.json"
API_BASE   = "https://www.myfxbook.com/api"

# Headers para imitar um browser real
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    "Referer": "https://www.myfxbook.com/",
}


# ─── CREDENCIAIS ─────────────────────────────────────────────────
def load_credentials():
    import os
    email    = os.environ.get("MYFXBOOK_EMAIL", "").strip()
    password = os.environ.get("MYFXBOOK_PASSWORD", "").strip()
    if email and password:
        print("Credenciais carregadas via variaveis de ambiente.")
        return email, password

    if not ENV_FILE.exists():
        print("ERRO: Credenciais nao encontradas.")
        print("  Em producao: define MYFXBOOK_EMAIL e MYFXBOOK_PASSWORD como secrets no GitHub.")
        print("  Localmente: cria o ficheiro .env")
        sys.exit(1)

    creds = {}
    with open(ENV_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                creds[key.strip()] = val.strip().strip('"').strip("'")

    email    = creds.get("MYFXBOOK_EMAIL", "")
    password = creds.get("MYFXBOOK_PASSWORD", "")
    if not email or not password:
        print("ERRO: MYFXBOOK_EMAIL ou MYFXBOOK_PASSWORD nao definidos no .env")
        sys.exit(1)

    print("Credenciais carregadas via .env local.")
    return email, password


# ─── CALCULOS ────────────────────────────────────────────────────
def months_since(date_str):
    if not date_str:
        return "--"
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        delta = datetime.now() - dt
        return str(max(1, delta.days // 30))
    except Exception:
        return "--"

def format_gain(value):
    try:
        v = float(value)
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.1f}%"
    except Exception:
        return "--"

def format_drawdown(value):
    try:
        v = abs(float(value))
        return f"-{v:.1f}%"
    except Exception:
        return "--"

def format_winrate(won, total):
    try:
        if total > 0:
            return f"{(won / total * 100):.1f}%"
    except Exception:
        pass
    return "--"


# ─── MAIN ────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  RICX -- myfxbook Stats Fetcher")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    email, password = load_credentials()

    # Usar requests.Session() para manter cookies entre chamadas
    # (essencial: myfxbook valida o IP via cookie de sessao, nao so o token)
    http = requests.Session()
    http.headers.update(HEADERS)

    # ── LOGIN ──
    print("A fazer login no myfxbook...")
    try:
        r = http.get(
            f"{API_BASE}/login.json",
            params={"email": email, "password": password},
            timeout=20,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"ERRO na chamada de login: {e}")
        sys.exit(1)

    if data.get("error"):
        print(f"ERRO: Login falhou: {data.get('message', 'Erro desconhecido')}")
        sys.exit(1)

    session_token = data["session"]
    print(f"Login bem-sucedido. Token: {session_token[:8]}...")

    # Pequena pausa para evitar rate limiting
    time.sleep(1)

    # ── GET ACCOUNTS ──
    print("A buscar dados das contas...")
    try:
        r2 = http.get(
            f"{API_BASE}/get-my-accounts.json",
            params={"session": session_token},
            timeout=20,
        )
        r2.raise_for_status()
        accounts_data = r2.json()
    except Exception as e:
        print(f"ERRO na chamada get-my-accounts: {e}")
        sys.exit(1)
    finally:
        # Logout (best-effort)
        try:
            http.get(f"{API_BASE}/logout.json", params={"session": session_token}, timeout=10)
        except Exception:
            pass

    print(f"Resposta: error={accounts_data.get('error')}, message={accounts_data.get('message','')}")

    if accounts_data.get("error"):
        print(f"ERRO ao buscar contas: {accounts_data.get('message')}")
        sys.exit(1)

    accounts = accounts_data.get("accounts", [])
    if not accounts:
        print("ERRO: Nenhuma conta encontrada.")
        sys.exit(1)

    print(f"Contas encontradas: {len(accounts)}")
    for a in accounts:
        print(f"  - ID={a.get('id')} nome={a.get('name')} gain={a.get('gain')}")

    # Encontrar conta pelo ID (comparar como string para evitar tipo errado)
    account = next((a for a in accounts if str(a.get("id")) == str(ACCOUNT_ID)), None)
    if not account:
        print(f"Conta ID {ACCOUNT_ID} nao encontrada. A usar a primeira conta disponivel.")
        account = accounts[0]

    print(f"Conta selecionada: {account.get('name', 'N/A')} (ID={account.get('id')})")

    won   = int(account.get("wonTrades", 0) or 0)
    lost  = int(account.get("lostTrades", 0) or 0)
    total = won + lost

    stats = {
        "gain":          format_gain(account.get("gain", 0)),
        "months":        months_since(account.get("firstTradeDate", "")),
        "winrate":       format_winrate(won, total),
        "drawdown":      format_drawdown(account.get("drawdown", 0)),
        "trades":        str(total) if total > 0 else "--",
        "profit_factor": f"{float(account.get('profitFactor', 0)):.2f}" if account.get("profitFactor") else "--",
        "balance":       f"${float(account.get('balance', 0)):,.2f}",
        "profit":        f"${float(account.get('profit', 0)):,.2f}",
        "last_updated":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "account_name":  account.get("name", "RICX"),
        "currency":      account.get("currency", "USD"),
    }

    with open(OUTPUT, "w", encoding="utf-8") as f:
   