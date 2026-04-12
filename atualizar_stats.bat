@echo off
title RICX Stats Updater
chcp 65001 >nul 2>&1
echo.
echo  ===================================
echo   RICX -- Atualizar Stats myfxbook
echo  ===================================
echo.

cd /d "%~dp0"

:: Descobrir qual comando Python usar (python ou py)
set PYTHON=
python --version >nul 2>&1 && set PYTHON=python
if "%PYTHON%"=="" (
    py --version >nul 2>&1 && set PYTHON=py
)

if "%PYTHON%"=="" (
    echo  ERRO: Python nao encontrado na tua maquina.
    echo.
    echo  Para instalar:
    echo  1. Vai a https://www.python.org/downloads/
    echo  2. Clica em "Download Python"
    echo  3. IMPORTANTE: marca a caixa "Add Python to PATH"
    echo  4. Instala e depois corre este ficheiro novamente
    echo.
    start https://www.python.org/downloads/
    pause
    exit /b 1
)

echo  Python encontrado: %PYTHON%
echo.

:: Instalar requests se necessario
%PYTHON% -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo  A instalar dependencia requests...
    %PYTHON% -m pip install requests
    echo.
)

echo  A buscar dados do myfxbook...
%PYTHON% fetch_stats.py
if errorlevel 1 (
    echo.
    echo  ERRO ao obter dados.
    echo  Verifica se o ficheiro .env tem o email e password corretos.
    echo.
    pause
    exit /b 1
)

echo.
echo  A publicar stats.json no GitHub...
%PYTHON% -c "
import json, base64, os, sys

# Ler .env
env = {}
with open('.env') as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()

token = env.get('GITHUB_TOKEN', '')
repo  = env.get('GITHUB_REPO', 'SE7E666/ricx-trading')

if not token:
    print('  ERRO: GITHUB_TOKEN nao encontrado no .env')
    sys.exit(1)

try:
    import requests
except ImportError:
    print('  ERRO: requests nao instalado')
    sys.exit(1)

headers = {
    'Authorization': f'token {token}',
    'Accept': 'application/vnd.github.v3+json'
}

# Ler stats.json local
with open('stats.json', 'rb') as f:
    content = base64.b64encode(f.read()).decode()

# Obter SHA atual do ficheiro no GitHub (necessario para update)
url = f'https://api.github.com/repos/{repo}/contents/stats.json'
r = requests.get(url, headers=headers)
sha = r.json().get('sha', '') if r.status_code == 200 else ''

# Fazer update via API
body = {
    'message': 'chore: atualizar stats myfxbook',
    'content': content,
}
if sha:
    body['sha'] = sha

r2 = requests.put(url, headers=headers, json=body)
if r2.status_code in (200, 201):
    print('  Stats publicados com sucesso\!')
else:
    print(f'  ERRO ao publicar: {r2.status_code} {r2.json().get(\"message\",\"\")}')
    sys.exit(1)
"

if errorlevel 1 (
    echo.
    echo  ERRO ao publicar no GitHub.
    echo  Verifica se o GITHUB_TOKEN no .env e valido.
    echo.
    pause
    exit /b 1
)

echo.
echo  =========================================
echo   SUCESSO\! Site atualizado em:
echo   https://se7e666.github.io/ricx-trading/
echo  =========================================
echo.
pause
