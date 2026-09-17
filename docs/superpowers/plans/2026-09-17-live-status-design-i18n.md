# Live status, Apple-style pass, ko/en switch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** One user-language live status (the pill), structured job `phase`/`source`/`recorded_seconds`, error `code`s, an Apple-style CSS pass, and an instant 한/EN switch (UI, tray, window title).

**Architecture:** The backend emits structured fields next to the unchanged Korean `stage`; the frontend localizes only from those fields through one `STRINGS`/`t()` table in app.jsx. The tray follows via the existing `set_recording` command, extended with `lang`.

**Tech Stack:** Python stdlib HTTP bridge, React 18 UMD (precompiled by Babel, no bundler), Tauri v2 (Rust).

## Global Constraints

- No new Python/npm/Rust dependencies; no bundler, state library, settings screen, or theme switcher.
- Keep `stage` strings exactly as they are (logs/details). Korean UI copy stays exactly as today except the live/file status wording in the spec.
- One `ponytail:` comment per deliberate shortcut.
- Tests: `.\.venv\Scripts\python.exe -m unittest tests.test_engine tests.test_diarize tests.test_library tests.test_server` stay green.

## Spec (job/error contract)

`GET /job` gains:
- `phase`: `"loading"` initially for every job. Live: `"recording" | "transcribing" | "finishing"`. File: `"decoding" | "diarizing" | "transcribing"`. Setup: `"downloading"` (on a `file` event), `"checking"` (on a `ready` event), `"converting"` (emitted by setup_assets before a static-shape conversion).
- `source`: `"mic" | "system" | "both"` for listen jobs (from the payload), else `None`.
- `recorded_seconds`: float. `0` until the first `phase == "recording"`; after that, seconds since that moment (computed at `GET /job` time); frozen when phase becomes `"finishing"`.
- `code`: `None`, `"cancelled"` (job cancelled), `"setup_failed"` (a setup job errored), or `"failed"` (any other job error).

HTTP error bodies gain `code` where listed: `busy` (409 from ensure_idle), `invalid_file` (400 on /transcribe path), `no_mic` (400 "마이크를 선택해 주세요."), `shutting_down` (503). Other errors have no `code` key.

`POST /live/stop` sets `phase = "finishing"` immediately (and freezes `recorded_seconds`) when a listen job is running.

---

### Task 1: Backend structured fields and error codes

**Files:** Modify `server.py`, `engine.py`, `setup_assets.py`; Test `tests/test_server.py`.

- [ ] Step 1: add tests to `tests/test_server.py` (ServerTests):

```python
    def test_live_job_reports_phase_source_and_recorded_seconds(self):
        self.request("POST", "/live", {"mic": "Mic", "source": "both"})
        self.wait_for("running")
        status, job = self.request("GET", "/job")
        self.assertEqual((job["phase"], job["source"], job["recorded_seconds"]), ("loading", "both", 0))
        emit = server.job_emitter("listen", job["note_id"])
        emit("phase", "recording")
        time.sleep(0.2)
        job = self.request("GET", "/job")[1]
        self.assertEqual(job["phase"], "recording")
        self.assertGreaterEqual(job["recorded_seconds"], 0.15)
        self.assertNotIn("recording_since", job)
        self.request("POST", "/live/stop", {})
        frozen = server.JOB["recorded_seconds"]
        self.assertEqual(server.JOB["phase"], "finishing")
        time.sleep(0.1)
        self.assertEqual(self.request("GET", "/job")[1]["recorded_seconds"], frozen)
        self.wait_for("done")

    def test_file_job_phase_and_cancel_code(self):
        self.request("POST", "/transcribe", {"path": self.audio()})
        self.wait_for("running")
        job = self.request("GET", "/job")[1]
        self.assertEqual((job["phase"], job["source"], job["code"]), ("loading", None, None))
        server.job_emitter("transcribe", job["note_id"])("phase", "decoding")
        self.assertEqual(self.request("GET", "/job")[1]["phase"], "decoding")
        self.request("POST", "/job/cancel", {})
        self.wait_for("error")
        self.assertEqual(server.JOB["code"], "cancelled")

    def test_job_error_codes(self):
        server.JOB = {"state": "running", "op": "setup"}
        server.job_emitter("setup", None)("error", "boom")
        self.assertEqual((server.JOB["error"], server.JOB["code"]), ("boom", "setup_failed"))
        server.JOB = {"state": "running", "op": "transcribe"}
        server.job_emitter("transcribe", None)("error", "boom")
        self.assertEqual(server.JOB["code"], "failed")

    def test_setup_phase_follows_files(self):
        emit = server.job_emitter("setup", None)
        server.JOB = {"state": "running", "op": "setup", "ready": [], "phase": "loading"}
        emit("file", "models/a.bin")
        self.assertEqual(server.JOB["phase"], "downloading")
        emit("ready", "models/a.bin")
        self.assertEqual(server.JOB["phase"], "checking")
        emit("phase", "converting")
        self.assertEqual(server.JOB["phase"], "converting")

    def test_error_bodies_carry_codes(self):
        self.assertEqual(self.request("POST", "/transcribe", {"path": "nope.wav"}),
                         (400, {"error": "지원하는 로컬 오디오 파일을 선택해 주세요.", "code": "invalid_file"}))
        self.assertEqual(self.request("POST", "/live", {"source": "mic"})[1]["code"], "no_mic")
        self.request("POST", "/live", {"mic": "Mic"})
        self.wait_for("running")
        status, body = self.request("POST", "/transcribe", {"path": self.audio()})
        self.assertEqual((status, body["code"]), (409, "busy"))
        self.request("POST", "/live/stop", {})
        self.wait_for("done")
        server.CANCEL.set()
        try:
            self.assertEqual(self.request("POST", "/setup", {})[1]["code"], "shutting_down")
        finally:
            server.CANCEL.clear()
        self.assertNotIn("code", self.request("GET", "/notes/999")[1])
```

- [ ] Step 2: run `.\.venv\Scripts\python.exe -m unittest tests.test_server` → the new tests fail.
- [ ] Step 3: implement in `server.py`:
  - `HttpError(status, message, code=None)` stores `self.code`; `handle_request` builds `{"error": str(error)}` plus `"code": error.code` only when it is set.
  - `ensure_idle` → `code="busy"`; the 503 in `start_job` → `"shutting_down"`; /transcribe path 400 → `"invalid_file"`; /live "마이크를 선택해 주세요." → `"no_mic"`.
  - `start_job`: JOB also gets `"phase": "loading", "source": payload.get("source") if operation == "listen" else None, "recorded_seconds": 0, "code": None`. `start_job` puts `source` into the listen payload (it is already there as `payload["source"]`).
  - A module-level helper `set_phase(value)`: `if value == "recording" and JOB.get("recording_since") is None: JOB["recording_since"] = time.monotonic()`; `if value == "finishing" and JOB.get("recording_since") is not None: JOB["recorded_seconds"] = time.monotonic() - JOB["recording_since"]; JOB["recording_since"] = None` — careful: finishing must also stop later recomputation; use a separate flag (e.g. keep `recording_since` but set `"recording_stopped": True`) or simply pop it after freezing, and make `set_phase("recording")` not restart once frozen (guard with `JOB.get("recorded_seconds")` being 0). Then `JOB["phase"] = value`.
  - `job_emitter`: `kind == "phase"` → `set_phase(value)`; for `file` also `JOB["phase"] = "downloading"`; for `ready` also `JOB["phase"] = "checking"`; on error/cancelled set `code` = `"cancelled"` if kind == "cancelled" else (`"setup_failed"` if operation == "setup" else `"failed"`).
  - `stop_live`: `if JOB.get("state") == "running" and JOB.get("op") == "listen": set_phase("finishing")` before `FINISH.set()`.
  - `GET /job`: `result = dict(JOB); since = result.pop("recording_since", None); if since is not None: result["recorded_seconds"] = time.monotonic() - since; return result`.
  - `import time`.
- [ ] Step 4: `engine.py`:
  - `transcribe()`: `self.emit("phase", "decoding")` before decode; `self.emit("phase", "diarizing")` before `diarize`; `self.emit("phase", "transcribing")` once, right before the `while pending` loop.
  - `listen()`: `self.emit("phase", "recording")` next to the existing `🎙 녹음 중 · {label}` stage. In `transcribe_segment`, after the silence check: `self.emit("phase", "finishing" if stop.is_set() else "transcribing")`; at its end: `if not stop.is_set(): self.emit("phase", "recording")`. After the loop (before `process.terminate()`): `self.emit("phase", "finishing")`.
- [ ] Step 5: `setup_assets.py`: `emit("phase", "converting")` right before each of the two `emit("stage", "…변환…")` calls (GPU encoder and speaker model). Do not touch `download()` (tests assert its exact events).
- [ ] Step 6: run all four suites → all green.
- [ ] Step 7: commit `feat(server): structured job phase/source/recorded_seconds and error codes`.

### Task 2: Tray and window title follow the language

**Files:** Modify `src-tauri/src/main.rs`.

- [ ] `set_recording(recording: bool, lang: String, tray: State<TrayItems>, window: WebviewWindow)`: TrayItems holds open/record/quit `MenuItem`s. en: `Open`, `Start recording` / `⏹ Stop recording`, `Quit`, title+tooltip `Sorigul`; ko: `열기`, `녹음 시작` / `⏹ 녹음 마치기`, `종료`, `소리글`. Set window title with `window.set_title` and tray tooltip via `app.tray_by_id("main")`.
- [ ] `focus_running_instance` tries both titles "소리글" and "Sorigul".
- [ ] `cargo check` in src-tauri passes.
- [ ] Commit `feat(tray): tray labels and window title follow the UI language`.

### Task 3: Frontend (controller does this one)

**Files:** Modify `app.jsx`, `bridge.js`, `tokens.css`.

- `STRINGS = { ko, en }`, `t(key, vars)`, module `lang` from localStorage `sori.lang` else `navigator.language`; App state re-renders; `LangToggle` in top bar and on the setup screen; `document.documentElement.lang`.
- bridge.js: `error.code = data.code`; `pickAudio(filterName)`, `pickSavePath(name, filterName)`, `setRecording(recording, lang)`.
- LivePill from `phase/source/recorded_seconds`; editor status line only for file jobs; `받아쓰는 중 · 42%` wording in editor and JobPill; setup hint from `phase === 'converting'`.
- Errors as `{ key, vars, detail }` rendered with a Details disclosure.
- tokens.css: pill material, pulse, spring enter/exit (`linear()`), press feedback, reduced motion/transparency, modal/setup restraint.
- `npm run build` passes; screenshots via a fake-bridge preview harness.
