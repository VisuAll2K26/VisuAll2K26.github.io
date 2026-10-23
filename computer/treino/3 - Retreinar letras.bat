@echo off
setlocal EnableExtensions
title VisuAll - Retreinar letras
cd /d "%~dp0"
call "%~dp0codigo\preparar.bat" || goto :fim

echo.
echo  ============================================================
echo   RETREINAR LETRAS
echo  ============================================================
echo   Grave mais vezes as letras que o app erra. O treino SOMA as
echo   gravacoes novas a todas as que ja existem.
echo.
echo   N / P troca a letra, ESPACO grava 3 segundos, R regrava a
echo   ultima, X apaga a ultima, Q fecha.
echo   Depois do Z vem o NADA: mexa a mao SEM fazer letra (trocar
echo   de letra, levantar a mao, cocar a cabeca). E o que ensina o
echo   app a nao inventar letra com movimento.
echo   Ao fechar, responda S para treinar.
echo  ============================================================
echo.

"%PY%" codigo\gravar.py letras || goto :fim
call "%~dp0codigo\treinar.bat" letras

:fim
echo.
pause
