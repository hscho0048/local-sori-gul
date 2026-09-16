# 소리글: custom title bar, 화자 분리 toggle, Intel GPU/NPU split, open bugs

Builds on `2026-09-16-installers-and-features-design.md`. Every existing behaviour and Korean label stays.
No new dependencies (Python, npm or Rust).

## 1. Custom title bar

- `tauri.conf.json` window: `"decorations": false`. Windows 11 keeps the DWM rounded corners and shadow for an
  undecorated Tauri window (`shadow` default true); no custom shadow layer.
- `capabilities/default.json` adds exactly note-taking's window permissions: `core:window:allow-minimize`,
  `allow-toggle-maximize`, `allow-close`, `allow-is-maximized`, `allow-start-dragging`,
  `allow-internal-toggle-maximize`.
- `app.jsx` gets a `WindowCaption` component ported from
  `note-taking/frontend/screens/window-caption-buttons.jsx` (read-only source):
  - three 40 px wide × 56 px (the topbar height) buttons, portalled to `position: fixed; top: 0; right: 0` above
    every overlay (so the chooser modal and the setup screen can never cover them);
  - inline SVG glyphs identical to the source (minimize line, maximize rounded square, restore double square,
    close X at stroke 1.1);
  - hover = a 26 px circular fill inside the column, 120 ms background transition: minimize `#febc2e`, maximize
    `#28c840`, close `#ff5f57`; glyph `rgba(0,0,0,0.72)` on yellow/green and white on red; resting glyph
    `var(--text-secondary)`;
  - no press effect (the source has none for these buttons); focus: the click blurs the button, keyboard focus shows
    a 2 px accent `:focus-visible` outline (offset 2 px) — the source's global rule, scoped here to the buttons;
  - maximize/restore glyph and label follow the real window: `isMaximized()` on mount and on every `onResized`;
  - labels 최소화 / 최대화 / 이전 크기로 / 닫기;
  - close calls `getCurrentWindow().close()` (never `destroy()`), so the existing `CloseRequested` handler runs:
    a live recording is finished and its WAV kept, then the bridge exits.
  - All styling is CSS in `tokens.css` (`.caption`, `.caption-btn`, `.caption-disc`); nothing from liquid-glass,
    theme.js, i18n or clay-primitives.
- Drag: `data-tauri-drag-region` on the `.topbar` header itself and on the brand "소리글" (Tauri 2.11 treats a
  bare attribute as "direct clicks on this element only", so the inputs and buttons inside stay clickable), plus a
  flexible empty spacer before a 120 px caption reserve at the right end of the row. Double-click on any drag
  region toggles maximize (Tauri's built-in handler). The search / 필터 / + 새 받아쓰기 / 🔔 / ? row keeps its order
  and position.
- The first-run setup screen has no topbar: it gets a fixed 56 px transparent drag strip at the top; the portalled
  caption buttons sit on it.

## 2. 화자 분리 on/off

- Chooser `choose` step: a checkbox "화자 분리" under the device select, checked by default; its value is saved in
  `sori.live` as `speakers` (default true when absent) and used by the chooser's 오디오 전사 and by dropped files.
- `bridge.transcribe(path, device, speakers)`; `POST /transcribe` accepts `speakers` (bool, default true; a non-bool
  is 400) and passes it into the job payload; `jobs.py` already skips diarization when it is false, and
  `engine.render` then returns plain paragraphs.
- 실시간 전사 unchanged.

## 3. Open items

Verify (no re-fix): the first-run "database is locked" race and the "확인 중" setup stage (e29afb3) on a fresh
`SORIGUL_HOME`.

Fix:
- Live stage label: `engine.listen` labels a producer command that has `--mic` as "마이크 + 시스템 소리"
  (system only stays "시스템 소리").
- Tray: the 녹음 시작 item reads "⏹ 녹음 마치기" while a live recording runs. The frontend invokes a new
  `set_recording(recording: bool)` command whenever "a listen job is running" changes; `main.rs` keeps the
  `MenuItem` in managed state and calls `set_text`.
- x64 build on an ARM64 PC (emulation): `platform.machine()` returns ARM64 there, so the x64 bundle took the ARM64
  paths (probe, required NPU files, `setup` in a non-existent `gpu-packages`). Use the interpreter's own platform
  (`sysconfig.get_platform() == "win-arm64"`) in `jobs.py`, `setup_assets.py`, `server.py`.
- Second app instance (double launch) came up without a window but with a tray icon and a hotkey. `main.rs` takes an
  exclusive lock file `<SORIGUL_HOME>/app.lock` (std `OpenOptionsExt::share_mode(0)`) before anything else; a
  second instance exits immediately.

Skipped (polish, not bugs): setup job ignores 취소 (no UI exists; shutdown still stops it); loopback exits when the
audio device is removed (the engine reports it); WINFUNCTYPE rebuilt per call (~1 % core); functools.cache double
probe; JobPill hidden while another note is open; drops during setup start after setup; bundles not pruned;
data dir equals the NSIS default install dir (kept per the earlier spec).

## 4. Intel GPU / NPU as separate devices

- `engine.openvino_kinds(available=None) -> set[str]` ("GPU.0" → "GPU"); replaces `openvino_device`.
- Device ids `intel-gpu` / `intel-npu` (labels "인텔 GPU (OpenVINO)" / "인텔 NPU (OpenVINO)"); `intel` removed.
  `probe_devices()` on x64 lists `intel-gpu` when OpenVINO reports a GPU.*, `intel-npu` when it reports an NPU.*,
  then `cpu`.
- `load_whisper('intel-gpu'|'intel-npu')` → `WhisperCPU(ov_device="GPU"|"NPU")`; the OpenVINO `device_type` is that
  value; cache dir `models/openvino-cache/<GPU|NPU>`; ready label `인텔 GPU (OpenVINO) · CPU (decoder)` /
  `인텔 NPU (OpenVINO) · CPU (decoder)`. Diarization stays on the CPU.
- The chooser already remembers the last device (`sori.live.device`); an unavailable saved id falls back to the
  first listed device.
- Tests: `/devices` with mocked `available_devices` = `['CPU','GPU.0']`, `['CPU','NPU']`, both, none (x64 branch);
  `intel-npu` untested on hardware.

## 5. Verification

Tests; `npm run tauri:dev` screenshots (normal + maximized title bar); minimize / maximize / close through the custom
buttons (close during a live recording keeps the WAV and leaves no pythonw); one transcription with 화자 분리 on
("화자 N:") and one off; first-run race on a fresh `SORIGUL_HOME`; the x64 bundle's `/devices` under emulation;
then `npm run tauri:build:arm64` and `npm run tauri:build:x64` with paths and sizes.
