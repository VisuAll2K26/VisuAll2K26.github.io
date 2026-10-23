@echo off
REM ============================================================
REM  Deixa pronto o Python do treino e devolve o caminho em %PY%.
REM  Chamado pelos .bat da pasta de cima (call), nunca sozinho.
REM
REM  Na primeira vez num computador ele cria computer\.venv com
REM  Python 3.11 (ou 3.12/3.10) e instala as bibliotecas do
REM  computer\requirements.txt. Demora (o TensorFlow tem ~600 MB);
REM  das outras vezes e instantaneo.
REM
REM  Por que um ambiente proprio: o MediaPipe, o TensorFlow e o
REM  ONNX so funcionam juntos em Python 3.10 a 3.12, e o "python"
REM  do computador pode ser outra versao.
REM ============================================================
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set "GLOG_minloglevel=2"
set "TF_CPP_MIN_LOG_LEVEL=2"
for %%I in ("%~dp0..\..") do set "COMPUTER=%%~fI"
set "PY=%COMPUTER%\.venv\Scripts\python.exe"
if exist "%PY%" goto :confere

echo.
echo Primeira vez neste computador: preparando o Python do treino...
set "BASE="
for %%V in (3.11 3.12 3.10) do (
    if not defined BASE (
        py -%%V -c "pass" >nul 2>&1 && set "BASE=py -%%V"
    )
)
if not defined BASE (
    python -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 12) else 1)" >nul 2>&1 && set "BASE=python"
)
if not defined BASE (
    echo.
    echo ERRO: precisa do Python 3.11 instalado.
    echo Baixe em https://www.python.org/downloads/release/python-3119/
    echo ^(no instalador, marque "Add python.exe to PATH"^) e rode de novo.
    exit /b 1
)
%BASE% -m venv "%COMPUTER%\.venv"
if errorlevel 1 (
    echo ERRO ao criar o ambiente em %COMPUTER%\.venv
    exit /b 1
)

:confere
"%PY%" -c "import importlib.util as u, sys; sys.exit(any(u.find_spec(m) is None for m in ('cv2', 'mediapipe', 'sklearn', 'skl2onnx', 'onnxruntime', 'tensorflow')))" >nul 2>&1
if not errorlevel 1 exit /b 0

echo.
echo Instalando as bibliotecas do treino (so na primeira vez, demora)...
"%PY%" -m pip install --upgrade pip >nul 2>&1
"%PY%" -m pip install -r "%COMPUTER%\requirements.txt"
if errorlevel 1 (
    echo.
    echo ERRO ao instalar as bibliotecas. Confira a internet e rode de novo.
    exit /b 1
)
exit /b 0
