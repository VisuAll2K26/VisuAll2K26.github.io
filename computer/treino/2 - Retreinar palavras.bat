@echo off
setlocal EnableExtensions
title VisuAll - Retreinar palavras
cd /d "%~dp0"
call "%~dp0codigo\preparar.bat" || goto :fim

echo.
echo  ============================================================
echo   RETREINAR PALAVRAS
echo  ============================================================
echo   Grave mais vezes as palavras que o app ja conhece, pra ele
echo   acertar melhor. O treino SOMA as gravacoes novas a todas as
echo   que ja existem: nenhuma palavra e esquecida.
echo.
echo   N / P troca a palavra, ESPACO grava 3 segundos, R regrava a
echo   ultima, X apaga a ultima, TAB cria uma palavra nova, Q fecha.
echo   Ao fechar, responda S para treinar.
echo  ============================================================
echo.

"%PY%" codigo\gravar.py palavras || goto :fim
call "%~dp0codigo\treinar.bat" palavras

:fim
echo.
pause
