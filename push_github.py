"""
RICX -- Publica stats.json no GitHub via API.
Chamado pelo atualizar_stats.bat após o fetch_stats.py.
"""

import base64, sys, os
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = Path(__file__).parent
ENV_FILE   = SCRIPT_DIR / ".env"
LOG_FILE   = SCRIPT_DIR / "ricx_update.log"


def append_log(msg):
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def load_env():
    env = {}
    if ENV_FILE.exists():
        for line in open(ENV_FILE, encoding="utf-8"):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    # Environment variables override .env
    env["GITHUB_TOKEN"] = os.environ.get("GITHUB_TOKEN", env.get("GITHUB_TOKEN", ""))
    env["GITHUB_REPO"]  = os.environ.get("GITHUB_REPO",  env.get("GITHUB_REPO", "SE7E666/ricx-trading"))
    return env


def main():
    env   = load_env()
    token = env.get("GITHUB_TOKEN", "")
    repo  = env.get("GITHUB_REPO", "SE7E666/ricx-trading")

    if not token:
        msg = "ERRO: GITHUB_TOKEN nao encontrado no .env"
        print(f"  {msg}")
        append_log(f"GitHub push: {msg}")
        sys.exit(1)

    try:
        import requests
    except ImportError:
        msg = "ERRO: biblioteca 'requests' nao instalada"
        print(f"  {msg}")
        append_log(f"GitHub push: {msg}")
        sys.exit(1)

    stats_file = SCRIPT_DIR / "stats.json"
    if not stats_file.exists():
        msg = "ERRO: stats.json nao encontrado"
        print(f"  {msg}")
        append_log(f"GitHub push: {msg}")
        sys.exit(1)

    with open(stats_file, "rb") as f:
        content = base64.b64encode(f.read()).decode()

    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }

    url = f"https://api.github.com/repos/{repo}/contents/stats.json"

    # Obter SHA atual (necessario para update)
    r = requests.get(url, headers=headers, timeout=15)
    if r.status_code == 401:
        msg = "ERRO: token GitHub invalido ou expirado (401). Gera um novo em https://github.com/settings/tokens"
        print(f"  {msg}")
        append_log(f"GitHub push: {msg}")
        sys.exit(1)

    sha = r.json().get("sha", "") if r.status_code == 200 else ""

    body = {
        "message": "chore: atualizar stats myfxbook " + datetime.now().strftime("%Y-%m-%d %H:%M"),
        "content": content,
    }
    if sha:
        body["sha"] = sha

    r2 = requests.put(url, headers=headers, json=body, timeout=30)
    if r2.status_code in (200, 201):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M")
        print(f"  stats.json publicado com sucesso! ({ts})")
        append_log(f"GitHub push: SUCESSO ({ts})")
    else:
        api_msg = r2.json().get("message", str(r2.status_code))
        msg = f"ERRO {r2.status_code}: {api_msg}"
        print(f"  {msg}")
        append_log(f"GitHub push: {msg}")
        sys.exit(1)


if __name__ == "__main__":
    main()
