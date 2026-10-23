@echo off
REM ============================================================
REM  Pergunta se e pra treinar e treina. Chamado pelos .bat da
REM  pasta de cima depois que a camera fecha:
REM      call codigo\treinar.bat palavras
REM      call codigo\treinar.bat letras
REM  Espera o %PY% do preparar.bat.
REM ============================================================
echo.
choice /c SN /n /m "Treinar agora, com TUDO que ja foi gravado? [S/N] "
if errorlevel 2 (
    echo.
    echo Ok, nada foi treinado. As gravacoes ficam guardadas: abra este
    echo mesmo .bat de novo, feche a camera com Q e responda S.
    exit /b 0
)
echo.
"%PY%" "%~dp0treinar_%1.py"
if errorlevel 1 (
    echo.
    echo O treino nao mudou o app. O motivo esta logo acima.
    exit /b 1
)
exit /b 0
