@echo off
setlocal EnableExtensions
title VisuAll - Coletar letra com movimento pelo app
cd /d "%~dp0"
call "%~dp0codigo\preparar.bat" || goto :fim

echo.
echo  ============================================================
echo   COLETAR LETRA COM MOVIMENTO PELO APP  (H J K X Z e NADA)
echo  ============================================================
echo   Use quando uma letra com movimento sai errada NO CELULAR
echo   (ex.: faz o Z e sai X). A webcam e o app nao veem a mao do
echo   mesmo jeito, entao aqui voce treina com o que o proprio app
echo   entrega.
echo.
echo   1. Celular no cabo, depuracao USB ligada, app instalado pelo
echo      Android Studio e aberto no modo ALFABETO.
echo   2. Escolha a letra, faca o movimento no app por uns 30 s e
echo      tecle ENTER aqui.
echo   3. Repita para as letras que erram, e tambem para NADA
echo      (mexer a mao SEM fazer letra).
echo   4. Depois rode o "3 - Retreinar letras.bat".
echo  ============================================================
echo.

"%PY%" codigo\coletar.py

:fim
echo.
pause
