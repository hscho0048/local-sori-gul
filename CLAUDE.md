# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup (Windows ARM64, once)

```powershell
.\setup.cmd        # creates .venv + .venv-whisper-gpu (native ARM64 Python 3.12), downloads models/ and tools/ffmpeg.exe
npm install
```

## Run

```powershell
npm run tauri:dev  # builds dist/ (npm run build), compiles src-tauri, starts .venv\Scripts\pythonw.exe server.py
npm run build      # dist/ only: copies static files, precompiles app.jsx
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_engine tests.test_diarize tests.test_library
.\.venv\Scripts\python.exe -m unittest tests.test_library.LibraryTests.test_keywords_strip_particles_and_skip_filler
```
