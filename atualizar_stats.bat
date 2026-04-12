@echo off
title RICX Stats Updater
echo.
echo  ===================================
echo   RICX -- Atualizar Stats myfxbook
echo  ===================================
echo.

cd /d "%~dp0"

where python >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instala em https://python.org
    pause
    exit /b 1
)

python -c "import requests" >nul 2>&1
if errorlevel 1 (
    echo A instalar dependencia requests...
    pip install requests
)

echo A buscar dados do myfxbook...
python fetch_stats.py
if errorlevel 1 (
    echo.
    echo ERRO: Nao foi possivel obter dados. Verifica o ficheiro .env
    pause
    exit /b 1
)

echo.
echo A publicar no site...
git add stats.json
git diff --staged --quiet && (echo Nenhuma alteracao nos stats.) || (
    git commit -m "chore: atualizar stats myfxbook"
    git push
    echo.
    echo  SUCESSO\! Site atualizado em https://se7e666.github.io/ricx-trading/
)

echo.
pause
