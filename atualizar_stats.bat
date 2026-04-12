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
echo  A publicar no site...
git add stats.json
git diff --staged --quiet && (
    echo  Nenhuma alteracao nos stats.
) || (
    git commit -m "chore: atualizar stats myfxbook"
    git push
    echo.
    echo  SUCESSO\! Site atualizado em:
    echo  https://se7e666.github.io/ricx-trading/
)

echo.
pause
