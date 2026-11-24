@echo off
cd /d "%~dp0"
echo Cotton advisor: starting

set PY=
for %%v in (3.11 3.10 3.9) do (
  if not defined PY (
    py -%%v -c "import sys" >nul 2>&1 && set PY=py -%%v
  )
)
if not defined PY (
  echo Python 3.9, 3.10 or 3.11 is needed. Install one from https://www.python.org/downloads/ and tick "Add Python to PATH", then run this again.
  pause
  exit /b 1
)

where ollama >nul 2>&1
if errorlevel 1 (
  echo Ollama is not installed. Install it from https://ollama.com, open it once, then run this again.
  pause
  exit /b 1
)

if not exist uploads mkdir uploads
if not exist audio_output mkdir audio_output
if not exist logs mkdir logs

if not exist venv (
  %PY% -m venv venv
  if errorlevel 1 (
    pause
    exit /b 1
  )
)
call venv\Scripts\activate.bat

if not exist venv\.packages_installed (
  echo Installing packages ^(first time only, needs internet, a few minutes^)
  python -m pip install --upgrade pip
  python -m pip install -r backend\requirements.txt
  if errorlevel 1 (
    echo Package install failed. Check the internet connection and the message above, then run this again.
    pause
    exit /b 1
  )
  echo done> venv\.packages_installed
)

curl -s -m 5 http://localhost:11434/api/tags >nul 2>&1
if errorlevel 1 (
  echo Ollama is not running. Open the Ollama app and run this again.
  pause
  exit /b 1
)

ollama list | findstr /b /c:"llama3.1:" >nul
if errorlevel 1 (
  echo Downloading the language model llama3.1:8b ^(about 5 GB, first time only^)
  ollama pull llama3.1:8b
)
ollama list | findstr /b /c:"nomic-embed-text" >nul
if errorlevel 1 (
  echo Downloading the search model nomic-embed-text ^(about 0.3 GB, first time only^)
  ollama pull nomic-embed-text
)

echo.
echo When it says the server is running, open http://127.0.0.1:8080 in your browser.
echo The Kapas site with photo check, guide chat, diseases and history is that same page. The old voice page is http://127.0.0.1:8080/legacy
echo To stop: press Control+C in this window.
echo.
python backend\app.py
pause
