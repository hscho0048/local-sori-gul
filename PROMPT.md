```
cd C:\Users\choho\sori-gul

/ponytail full

Goal: build "소리글" as a Tauri v2 desktop app in this folder. Move ONLY the
transcription features out of C:\Users\choho\audio2text (a Tkinter app) and give
them a new sidebar + table UI like a transcription dashboard. Everything else
(minutes/LLM, Q&A, embeddings) stays in audio2text and is out of scope.

Scope (exactly three features, nothing more):
1. File transcription: pick audio -> copy to library/audio -> run NPU/GPU Whisper
   (with the existing speaker diarization) -> save transcript.
2. Real-time transcription: pick mic -> ffmpeg 16kHz PCM stream -> chunk on
   silence -> transcribe chunks live -> append; "⏹ 녹음 마치기" flushes and
   keeps the WAV.
3. Transcript editing/export: edit text, find & replace (Ctrl+H), autosave,
   save as TXT.

Backend: reuse, do not rewrite. Copy from audio2text: engine.py, jobs.py,
diarize.py, library.py (keep only notes/folders/trash/star tables), setup_assets.py,
setup.cmd/setup.ps1, requirements.txt, requirements-whisper-gpu.txt, tools/ffmpeg.exe
(+LICENSE), tests/test_engine.py, tests/test_diarize.py, tests/test_library.py.
The real-time capture loop lives inside audio2text/app.py — extract it into a
module, drop the Tk parts. Leave audio2text untouched; deleting from it is a
separate step after this app works.

Bridge: Python stdlib http.server on 127.0.0.1 with a random port, spawned by
Tauri (shell plugin, sidecar). Endpoints: notes CRUD, folders, star, trash/restore,
transcribe(file), live start/stop, job status. Frontend polls job status every
500 ms. No FastAPI, no websockets, no new Python deps. Skip anything not on
this list.

Frontend: copy the Tauri skeleton from C:\Users\choho\note-taking\frontend
(src-tauri/tauri.conf.json, capabilities/default.json, scripts/build-tauri-assets.cjs,
the static React-via-babel setup, tokens.css, and the engine-bridge.js pattern for
calling the sidecar). Read its HomeScreen.jsx for the left-stacked sidebar
structure. Do NOT bring liquid-glass, pen, haptics, PDF, OCR, or local-ai.

Layout (match this, Korean labels as written):
- Top bar: search "검색어를 입력해 주세요", "필터", primary button "+ 새 받아쓰기",
  bell, help.
- Left sidebar (stacked): section "내 받아쓰기" -> 전체 보드 / 중요 보드 /
  미완료 녹음 / 휴지통; section "폴더" with a "+" and the folder list; collapse button.
- Main: heading "전체 보드", table with checkbox, 보드 이름 (second line = auto
  keyword tags from transcript), 길이, 폴더 위치, 생성일 (sortable, desc default).
  Row click opens the transcript editor (feature 3). "+ 새 받아쓰기" opens a
  chooser: 오디오 전사… / 실시간 전사. Unfinished live recordings show under
  미완료 녹음.

Process:
1. Use superpowers:brainstorming, then lazyweb_search_screens for
   "transcription dashboard sidebar folders trash" to confirm the layout above;
   keep only what the screenshot has.
2. superpowers:writing-plans -> a short plan, then
   superpowers:subagent-driven-development to execute it.
3. Run /init for CLAUDE.md here (setup + run commands only).
4. superpowers:verification-before-completion: npm run tauri:dev boots, the three
   python tests pass, one file transcription and one 10-second live session work
   end to end. Report actual output.

YAGNI rules: no bundler, no state library, no auth, no cloud, no settings screen,
no PDF/slides/quiz/translation nav items, no i18n layer, no theme switcher. One
`ponytail:` comment per deliberate shortcut. Fewest files that work.
```
