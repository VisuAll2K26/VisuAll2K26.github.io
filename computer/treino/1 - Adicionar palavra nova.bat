@echo off
setlocal EnableExtensions
title VisuAll - Adicionar palavra nova
cd /d "%~dp0"
call "%~dp0codigo\preparar.bat" || goto :fim

echo.
echo  ============================================================
echo   ADICIONAR PALAVRA NOVA
echo  ============================================================
echo   1. Na janela da camera, digite o nome da palavra e tecle ENTER.
echo      Uma pasta com esse nome e criada em gravacoes\palavras\.
echo   2. ESPACO grava 3 segundos. Grave a mesma palavra 20 vezes ou
echo      mais (o minimo e 5), variando um pouco a posicao.
echo   3. R regrava a ultima, X apaga a ultima, TAB comeca outra
echo      palavra nova, Q fecha a camera.
echo   4. Ao fechar, responda S para treinar.
echo  ============================================================
echo.

"%PY%" codigo\gravar.py palavra-nova || goto :fim
call "%~dp0codigo\treinar.bat" palavras

:fim
echo.
pause
