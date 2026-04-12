"""
RICX Trading Bot — myfxbook Stats Fetcher
==========================================
Busca os dados de performance do myfxbook via API oficial
e salva em stats.json para o site exibir automaticamente.

Uso:
  1. Cria um ficheiro .env na mesma pasta com as tuas credenciais (ver .env.example)
  2. Executa: python fetch_stats.py
  3. O ficheiro stats.json será atualizado automaticamente

Requisitos:
  pip install requests python-dotenv
"""

import requests
import json
import sys
from pathlib import Path
from datetime import datetime

# ─── CONFIGURAÇÃO ───────────────────────────────────────────────
ACCOUNT_ID = 11746315          # ID da tua conta no myfxbook
SCRIPT_DIR = Path(__file__).parent
ENV_FILE   = SCRIPT_DIR / ".env"
OUTPUT     = SCRIPT_DIR / "stats.json"
API_BASE   = "https://www.myfxbook.com/api"


# ─── CARREGAR CREDENCIAIS ────────────────────────────────────────
def load_credentials():
    """
    Lê credenciais em dois modos:
    1. GitHub Actions / servidor: lê variáveis de ambiente (MYFXBOOK_EMAIL, MYFXBOOK_PASSWORD)
    2. Local: lê do ficheiro .env na pasta do script
    """
    import os

    # Modo 1: variáveis de ambiente (GitHub Actions, servidor)
    email    = os.environ.get("MYFXBOOK_EMAIL", "").strip()
    password = os.environ.get("MYFXBOOK_PASSWORD", "").strip()

    if email and password:
        print("🔐 Credenciais carregadas via variáveis de ambiente.")
        return email, password

    # Modo 2: ficheiro .env local
    if not ENV_FILE.exists():
        print(f"❌ Credenciais não encontradas.")
        print(f"   • Em produção: define MYFXBOOK_EMAIL e MYFXBOOK_PASSWORD como secrets no GitHub.")
        print(f"   • Localmente: cria o ficheiro .env com base no .env.example")
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
        print("❌ MYFXBOOK_EMAIL ou MYFXBOOK_PASSWORD não definidos no .env")
        sys.exit(1)

    print("🔐 Credenciais carregadas via ficheiro .env local.")
    return email, password


# ─── API CALLS ───────────────────────────────────────────────────
def api_login(email, password):
    """Faz login e retorna o session token"""
    print("🔑 A fazer login no myfxbook...")
    url = f"{API_BASE}/login.json"
    r = requests.get(url, params={"email": email, "password": password}, timeout=15)
    r.raise_for_status()
    data = r.json()

    if data.get("error"):
        print(f"❌ Login falhou: {data.get('message', 'Erro desconhecido')}")
        sys.exit(1)

    session = data["session"]
    print(f"✅ Login bem-sucedido.")
    return session


def api_get_accounts(session):
    """Busca lista de contas"""
    print("📊 A buscar dados das contas...")
    url = f"{API_BASE}/get-my-accounts.json"
    r = requests.get(url, params={"session": session}, timeout=15)
    r.raise_for_status()
    return r.json()


def api_logout(session):
    """Encerra a sessão"""
    try:
        requests.get(f"{API_BASE}/logout.json", params={"session": session}, timeout=10)
    except Exception:
        pass


# ─── CÁLCULOS ────────────────────────────────────────────────────
def months_since(date_str):
    """Calcula meses desde uma data no formato YYYY-MM-DD HH:MM:SS"""
    if not date_str:
        return "--"
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        delta = datetime.now() - dt
        return str(max(1, delta.days // 30))
    except Exception:
        return "--"


def format_gain(value):
    """Formata o ganho como +XX.X%"""
    try:
        v = float(value)
        sign = "+" if v >= 0 else ""
        return f"{sign}{v:.1f}%"
    except Exception:
        return "--"


def format_drawdown(value):
    """Formata o drawdown como -XX.X%"""
    try:
        v = abs(float(value))
        return f"-{v:.1f}%"
    except Exception:
        return "--"


def format_winrate(won, total):
    """Calcula e formata o winrate"""
    try:
        if total > 0:
            return f"{(won / total * 100):.1f}%"
    except Exception:
        pass
    return "--"


# ─── MAIN ────────────────────────────────────────────────────────
def main():
    print("=" * 50)
    print("  RICX — myfxbook Stats Fetcher")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)

    email, password = load_credentials()
    session = api_login(email, password)

    try:
        accounts_data = api_get_accounts(session)
    finally:
        api_logout(session)

    if accounts_data.get("error"):
        print(f"❌ Erro ao buscar contas: {accounts_data.get('message')}")
        sys.exit(1)

    accounts = accounts_data.get("accounts", [])
    if not accounts:
        print("❌ Nenhuma conta encontrada na tua conta myfxbook.")
        sys.exit(1)

    # Encontrar a conta pelo ID
    account = next((a for a in accounts if a.get("id") == ACCOUNT_ID), None)

    if not account:
        print(f"⚠️  Conta ID {ACCOUNT_ID} não encontrada. A usar a primeira conta disponível.")
        account = accounts[0]

    print(f"✅ Conta encontrada: {account.get('name', 'N/A')}")

    # Extrair dados
    won   = account.get("wonTrades", 0)
    lost  = account.get("lostTrades", 0)
    total = won + lost

    stats = {
        "gain":           format_gain(account.get("gain", 0)),
        "months":         months_since(account.get("firstTradeDate", "")),
        "winrate":        format_winrate(won, total),
        "drawdown":       format_drawdown(account.get("drawdown", 0)),
        "trades":         str(total) if total > 0 else "--",
        "profit_factor":  f"{float(account.get('profitFactor', 0)):.2f}" if account.get("profitFactor") else "--",
        "balance":        f"${float(account.get('balance', 0)):,.2f}",
        "profit":         f"${float(account.get('profit', 0)):,.2f}",
        "last_updated":   datetime.now().strftime("%Y-%m-%d %H:%M"),
        "account_name":   account.get("name", "RICX"),
        "currency":       account.get("currency", "USD"),
    }

    # Salvar JSON
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

    print("\n📁 stats.json atualizado com sucesso!")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print("\n✅ Concluído!")


if __name__ == "__main__":
    main()
