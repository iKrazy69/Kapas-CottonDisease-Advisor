#!/bin/bash
cd "$(dirname "$0")" || exit 1
echo "Cotton advisor: starting"

PY=""
for c in python3.11 python3.10 python3.9 python3 python; do
  if command -v "$c" >/dev/null 2>&1; then
    v=$("$c" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)
    case "$v" in
      3.9|3.10|3.11) PY="$c"; break ;;
    esac
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.9, 3.10 or 3.11 is needed (newer versions do not work with the pinned packages)."
  echo "Install one from https://www.python.org/downloads/ and run this again."
  exit 1
fi

if ! command -v ollama >/dev/null 2>&1; then
  echo "Ollama is not installed. Install it from https://ollama.com, open it once, then run this again."
  exit 1
fi

mkdir -p uploads audio_output logs

if [ ! -d venv ]; then
  "$PY" -m venv venv || exit 1
fi
source venv/bin/activate

if [ ! -f venv/.packages_installed ]; then
  echo "Installing packages (first time only, needs internet, a few minutes)"
  python -m pip install --upgrade pip
  if python -m pip install -r backend/requirements.txt; then
    touch venv/.packages_installed
  else
    echo "Package install failed. Check the internet connection and the message above, then run this again."
    exit 1
  fi
fi

if ! curl -s -m 5 http://localhost:11434/api/tags >/dev/null 2>&1; then
  echo "Ollama is not running. Open the Ollama app (or run 'ollama serve' in another window) and run this again."
  exit 1
fi

if ! ollama list | awk 'NR>1{print $1}' | grep -q -E '^llama3\.1:(8b|latest)'; then
  echo "Downloading the language model llama3.1:8b (about 5 GB, first time only)"
  ollama pull llama3.1:8b || exit 1
fi
if ! ollama list | awk 'NR>1{print $1}' | grep -q '^nomic-embed-text'; then
  echo "Downloading the search model nomic-embed-text (about 0.3 GB, first time only)"
  ollama pull nomic-embed-text || exit 1
fi

echo ""
echo "When it says the server is running, open http://127.0.0.1:8080 in your browser."
echo "The Kapas site (photo check, guide chat, diseases, history) is that same page. The old voice page is http://127.0.0.1:8080/legacy"
echo "To stop: press Control+C in this window."
echo ""
python backend/app.py
