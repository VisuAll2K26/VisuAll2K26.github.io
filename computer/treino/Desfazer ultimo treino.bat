@echo off
setlocal EnableExtensions
title VisuAll - Desfazer um treino

REM ============================================================
REM  Devolve o modelo que estava no app antes de um treino.
REM
REM  Todo treino guarda antes uma copia do modelo que ia mudar em
REM  computer\treino\modelos_anteriores\ (so neste computador).
REM  Aqui voce escolhe qual devolver. As gravacoes e o banco de
REM  pontos nao mudam: so o modelo volta.
REM ============================================================

cd /d "%~dp0"
call "%~dp0codigo\preparar.bat" || goto :fim
"%PY%" codigo\restaurar.py

:fim
echo.
pause
