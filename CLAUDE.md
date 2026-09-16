# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Setup (Windows ARM64 or x64, once)

```powershell
.\setup.cmd        # ARM64: .venv (QNN) + .venv-whisper-gpu; x64: .venv (OpenVINO); downloads models/ and tools/ffmpeg.exe
npm install
```

## Run

```powershell
npm run tauri:dev  # builds dist/, compiles src-tauri (debug), starts .venv\Scripts\pythonw.exe server.py with SORIGUL_HOME=<repo>
npm run build      # dist/ only: copies static files, precompiles app.jsx
```

## Tests

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_engine tests.test_diarize tests.test_library tests.test_server
.\.venv\Scripts\python.exe -m unittest tests.test_library.LibraryTests.test_keywords_strip_particles_and_skip_filler
```

## Installers (NSIS; build both on the ARM64 dev machine)

From a clean checkout: `.\setup.cmd`, `npm install`, then

```powershell
npm run tauri:build:arm64  # scripts\build-python-bundle.ps1 arm64, then tauri build --target aarch64-pc-windows-msvc
npm run tauri:build:x64    # scripts\build-python-bundle.ps1 x64, then tauri build --target x86_64-pc-windows-msvc (MSVC x64 cross tools)
```

Output: `src-tauri\target\<triple>\release\bundle\nsis\Sorigul_0.1.0_<arch>-setup.exe`. The bundle script puts embeddable
CPython + wheels + backend .py + ffmpeg + VC++ runtime in `src-tauri\python-<arch>\` (shipped as `python\`). The installed app
keeps models, library and the model lock in `%LOCALAPPDATA%\Sorigul` (`SORIGUL_HOME`) and downloads models on first run.
