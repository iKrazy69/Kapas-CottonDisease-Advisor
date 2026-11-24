# Cotton advisor (BTP): how to run it on another computer

This folder is the whole project: the photo classifier for cotton leaf diseases, the question-answering advisor built on the CICR guide (English and Hindi, with sources), the test and benchmark code, and the finished search database. Nothing has to be rebuilt.

**If you downloaded it from GitHub:** the CICR guide, the search database and the voice models are not in the repository. Before the first start, put the guide in `documents/` (see `documents/README.md`) and, for spoken answers, download the two voices (see `backend/tts_models/README.md`). The first start then builds the search database by itself, which takes a few minutes.

## What the computer needs
- Python 3.9, 3.10 or 3.11. Newer versions (3.12, 3.13) do not work with the pinned packages.
- Ollama (free, https://ollama.com). It runs the language model on the computer itself.
- About 10 GB of free disk space and 16 GB of memory (the language model needs about 6 GB of memory; 8 GB computers will be slow or fail).
- Internet only for the first start: packages, the two Ollama models (about 5.3 GB), and the speech model the voice part downloads (about 0.5 GB). After that the advisor runs offline, except the internet fallback.

## Start it
Mac or Linux: open a terminal in this folder and run

    bash start_mac_linux.sh

Windows: double-click `start_windows.bat`.

The first start installs everything and downloads the models, so it takes a while. Later starts take seconds. When the window says the server is running, open http://127.0.0.1:8080 in a browser. That is the Kapas site: leaf-photo check, questions answered from the guide, and sections on cotton, seasons, history and every disease in the guide. The old link http://127.0.0.1:8080/diagnose opens the same page, and http://127.0.0.1:8080/legacy opens the earlier voice-only page. Stop with Control+C.

Open the Ollama app before starting (on Mac and Windows it sits in the menu bar or tray).

## What to expect
- The first answer after starting is slow (the model is loading). After that an answer takes about 9 to 11 seconds on a laptop (median in the final measurements).
- It answers only from the CICR guide and shows the sources. If the guide has no answer it says so; for farming questions the guide does not cover it may search the internet and labels those answers. To stay fully offline, set `ENABLE_WEB_LOOKUP = False` in `backend/config.py`.
- The photo classifier gives a diagnosis only when it is at least 70% sure. It works for single leaves on a plain background like the training photos, and it can be wrong on other photos.

## Problems
- "Python 3.9, 3.10 or 3.11 is needed": install one of those from https://www.python.org/downloads/ (on Windows tick "Add Python to PATH").
- On Linux, if it fails on `sounddevice`: run `sudo apt install libportaudio2` and start again.
- "Address already in use" on port 8080: another copy is running. Close it.
- A package fails to install: check the internet connection and start again; it continues where it stopped.

## What is in the folder
- `backend/`: the app (Flask), the search engine, the classifier and its saved model, the voice models.
- `frontend/`: the web pages.
- `documents/`: the CICR guide and the other documents. `chroma_data/`: the finished search database (built with the nomic-embed-text model; do not delete).
- `eval/` and `tests/`: the benchmark, the tests and the results so far. `INTEGRATION.md` explains how the parts fit.
- Not included (too large or only for the original Mac): the Python environment `venv/`, the old database backups, the `_pre_*` backup folders, and the photo datasets. The benchmark and the tests that read photo datasets need those datasets; the app does not.

## Measurements (only when asked)
`bash eval/final_run.sh` repeats all the measurements (2 to 3 hours). It is for the thesis, not for showing the app.
