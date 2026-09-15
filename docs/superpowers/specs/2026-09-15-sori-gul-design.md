# 소리글 (sori-gul) — design

Tauri v2 desktop app that carries ONLY the transcription features of `C:\Users\choho\audio2text`:
file transcription (NPU/GPU Whisper + speaker diarization), real-time microphone transcription, and transcript
editing/export. Minutes/LLM, Q&A and embeddings stay in audio2text. audio2text is not modified.

## Decisions (approved 2026-09-15)
- Bridge process: Rust `std::process` in `main.rs` starts `<repo>/.venv/Scripts/pythonw.exe server.py`, reads the first
  stdout line `PORT <n> <token>` (server prints with `flush=True`), exposes it via `invoke('bridge')`. On
  `WindowEvent::CloseRequested` and `RunEvent::Exit` it closes the child's stdin, waits ≤3 s, then kills it, so no
  stray python keeps `.model.lock`. No shell plugin, no sidecar exe.
- Library: `library.py` trimmed to `notes` + `folders`; notes gain `folder_id` (FK, ON DELETE SET NULL), `starred`,
  `trashed` (timestamp/NULL), `duration`. chunks/vectors/FTS/search removed. Top-bar search = `LIKE` on title/transcript.
- Assets: `models/` and `tools/` copied from audio2text; venvs created by the trimmed `setup.ps1` (no `.venv-llm`, no e5).
- 미완료 녹음: a live session creates a note with `source='live'`; the existing `jobs.py` listen branch attaches the WAV on
  a clean finish, which flips `source` to `'audio'`. Error/crash leaves it `'live'`.
- 필터: folder-only dropdown. No date range.
- Checked-row action bar: 중요 / 폴더 이동 / 휴지통; in 휴지통: 복원 / 영구 삭제.
- `tests/test_engine.py`: the `worker_environment("correct")` assertion is dropped, not replaced.
- The real-time capture loop already lives in `engine.WhisperNPU.listen()` (no Tk); nothing to extract from app.py.

## Bridge API (127.0.0.1, random port, header `X-Bridge-Token` required)
| Method | Path | Body → Response |
|---|---|---|
| GET | `/notes?view=all\|starred\|live\|trash\|folder:<id>&q=` | → `[{id,title,created,source,duration,starred,trashed,folder_id,folder,keywords}]` |
| GET | `/notes/<id>` | → note row incl. `transcript`, `audio` |
| PATCH | `/notes/<id>` | `{title?,transcript?,folder_id?,starred?,trashed?}` → `{ok}` |
| DELETE | `/notes/<id>` | → `{ok}` (permanent) |
| POST | `/notes/<id>/export` | `{path}` (.txt only, UTF-8 BOM) → `{ok}` |
| GET/POST | `/folders` | `{name}` → `[{id,name}]` / `{id}` |
| DELETE | `/folders/<id>` | → `{ok}` |
| GET | `/mics` | → `["마이크 이름", …]` |
| POST | `/transcribe` | `{path, device:'npu'\|'gpu'}` → `{note_id}` (copies audio into library/audio, diarization on) |
| POST | `/live` | `{mic, device}` → `{note_id}` |
| POST | `/live/stop` | → `{ok}` (⏹ 녹음 마치기: flush tail, keep WAV) |
| GET | `/job` | → `{state:'idle'\|'running'\|'done'\|'error', op, note_id, stage, text, percent, error}` |

One job slot (the model lock allows one anyway); a second start → 409. Frontend polls `/job` every 500 ms while running.

## UI
- Top bar: search "검색어를 입력해 주세요", "필터" (folder dropdown), primary "+ 새 받아쓰기", bell, help.
- Sidebar: "내 받아쓰기" → 전체 보드 / 중요 보드 / 미완료 녹음 / 휴지통; "폴더" with "+" and folder list; collapse button.
- Main: heading = current view name; table: checkbox, 보드 이름 (2nd line keyword chips), 길이, 폴더 위치, 생성일
  (sortable, 생성일 desc default). Row click → editor.
- "+ 새 받아쓰기" chooser: 오디오 전사… (file dialog) / 실시간 전사 (mic select), each with NPU/GPU select.
- Editor: title, textarea (read-only while its job runs, showing streamed text), autosave (800 ms debounce),
  Ctrl+H find & replace (다음 찾기 / 바꾸기 / 모두 바꾸기), "TXT로 저장".
- Live pill (bottom center, any screen while recording): timer + stage + "⏹ 녹음 마치기".
- Lazyweb references: Otter (sidebar + folders "+", trash list with checkbox/keyword line/restore),
  Zoho WorkDrive (sortable table header, floating recording pill).

## Out of scope
Bundler, state library, auth, cloud, settings screen, PDF/slides/quiz/translation, i18n, theme switcher,
job cancel button, release packaging of python.
