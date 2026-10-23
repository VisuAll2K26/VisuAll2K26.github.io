@echo off
setlocal EnableExtensions
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
title VisuAll - Voltar um modelo anterior

REM ============================================================
REM  Desfaz um treino: devolve o modelo que existia antes.
REM
REM  Sempre que um treino SUBSTITUI um modelo geral (TreinarCorpo,
REM  ou Treinar sem --reforcar), o anterior e guardado em
REM  computer\treino\modelos_anteriores\. Aqui voce escolhe qual devolver.
REM
REM  (Reforcar.bat nao aparece aqui porque ele nao substitui nada
REM  -- acrescenta modelos por letra sem apagar o que existia.)
REM ============================================================

cd /d "%~dp0.."

REM Prefere o Python do ambiente do projeto (computer\.venv, Python 3.11):
REM o "python" do PATH pode ser uma versao que o treino nao aceita (3.13+).
REM Como criar o ambiente: computer\treino\RETREINO_FINAL.md, passo 0.
set "PY=python"
if exist "%CD%\.venv\Scripts\python.exe" set "PY=%CD%\.venv\Scripts\python.exe"

"%PY%" "%~dp0restaurar.py"

echo.
pause
exit /b 0
