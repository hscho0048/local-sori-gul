# 소리글: installers (arm64 + x64) and six features

Builds on `2026-09-15-sori-gul-design.md`. Every existing behaviour and Korean label stays.

## Decisions (brainstorming)

- **pyaudiowpatch has no win_arm64 wheel and no sdist** (PyPI checked 2026-09-16). System audio uses WASAPI
  through stdlib `ctypes` in `loopback.py` on both arches. pyaudiowpatch is not used.
- **onnxruntime-openvino needs the `openvino` pip package** (the wheel only ships
  `onnxruntime_providers_openvino.dll`; `onnxruntime/tools/add_openvino_win_libs.py` looks for
  `site-packages/openvino/libs`). `openvino` is allowed as an extra dependency. `onnxruntime-openvino`
  provides the `onnxruntime` module itself, so x64 does not also install plain `onnxruntime`.
- **arm64 bundle = one embeddable Python + two package dirs** (`Lib\site-packages` = QNN 1.22 set,
  `Lib\gpu-packages` = ORT 1.30 + QNN 2.6 set).
- **ffmpeg is bundled**; lookup is `$SORIGUL_HOME/tools/ffmpeg.exe`, then `<backend dir>/tools/ffmpeg.exe`.

## 1. Data dir

`ROOT = Path(os.environ.get("SORIGUL_HOME") or Path(__file__).resolve().parent)` in engine, diarize, library,
jobs, setup_assets. It covers models/, tools/, library/, .model.lock, diagnostics/.

| build | SORIGUL_HOME | python | cwd |
|---|---|---|---|
| debug | repo root | `<repo>\.venv\Scripts\pythonw.exe` | repo |
| release | `%LOCALAPPDATA%\Sorigul` (created) | `<resource_dir>\python\pythonw.exe` | `<resource_dir>\python` |

## 2. Bundle (`scripts/build-python-bundle.ps1 <arm64|x64>`)

Produces `src-tauri/python-<arch>/` (git-ignored):

- python.org 3.12.10 embeddable zip for the arch;
- `python312._pth`: `python312.zip`, `.`, `Lib\site-packages`, `import site` removed (not needed);
- backend files in the root: server.py, engine.py, jobs.py, diarize.py, library.py, setup_assets.py, loopback.py;
- `tools\ffmpeg.exe` (+ its LICENSE);
- app-local VC++ runtime (`msvcp140*.dll`, `vcruntime140*.dll`) from the Visual Studio redist folder for the arch;
- `Lib\site-packages` from `pip download --platform win_<arch> --python-version 3.12 --only-binary=:all:
  -r requirements-<arch>.txt`, wheels unzipped;
- arm64 only: `Lib\gpu-packages` from `requirements-whisper-gpu.txt`.

Requirements files: `requirements-arm64.txt` (renamed `requirements.txt`), `requirements-whisper-gpu.txt`
(unchanged), `requirements-x64.txt` (onnxruntime-openvino, openvino pinned to its build, numpy, transformers,
onnx; onnx is already used by setup_assets/diarize to make static-shape models).

npm scripts: `tauri:build:arm64` / `tauri:build:x64` = bundle script, then
`tauri build --target <aarch64|x86_64>-pc-windows-msvc --bundles nsis --config src-tauri/tauri.<arch>.conf.json`.
The per-arch config only adds `bundle.resources: {"python-<arch>/": "python/"}`.
x64 is cross-built on this ARM64 machine with the MSVC x64 tools.

`setup.ps1` branches on `$env:PROCESSOR_ARCHITECTURE`: ARM64 = today's two venvs; AMD64 = one `.venv` from
requirements-x64.txt with x64 Python.

## 3. Worker environments

`jobs.worker_environment(op, payload) -> (pythonw, packages_dir | None)`.

- Dev (a `.venv` exists under ROOT's code dir): `.venv` or `.venv-whisper-gpu` as today (arm64); x64 dev has
  only `.venv`.
- Bundle (`sys.executable` dir has `python312._pth`): that interpreter; packages dir `gpu-packages` for
  `device == "gpu"` and for `op == "setup"` on arm64 (it has onnx), else `site-packages`.
- `model_worker` removes every `site-packages`/`gpu-packages` entry from `sys.path` and appends the
  selected dir (venv: `site.getsitepackages()`). `__PYVENV_LAUNCHER__` is only set for venvs.

## 4. Devices

`load_whisper(device)`: `npu`, `gpu` unchanged; `cpu` and `intel` = `WhisperCPU(WhisperGPU)`, which
overrides only `__init__` (same model files under models/whisper-gpu, same `infer()`):

- `cpu`: encoder and decoder on `CPUExecutionProvider`.
- `intel`: `add_openvino_libs_to_path()`, then encoder on `OpenVINOExecutionProvider` with `device_type` =
  first of GPU, NPU, CPU present in `openvino.Core().available_devices`; decoder on CPU. Untested on hardware.

Speaker embedding runs on CPU for `cpu` and `intel`.

`server.py` probes once at startup (`probe_devices()`):
- arm64: `npu` if `QNNExecutionProvider` is available in the server's onnxruntime; `gpu` if the GPU env exists
  (venv or `gpu-packages`); `cpu`.
- x64: QNN is never imported; `intel` if `openvino` reports GPU or NPU; `cpu`.

`GET /devices` → `{"devices": [{"id", "label"}], "models_ready": bool}`; labels "NPU (Hexagon)",
"GPU (Adreno)", "인텔 GPU (OpenVINO)", "CPU". `models_ready` = required files for this arch exist (no hashing).
`device()` validation accepts only probed ids. The chooser lists only these.

## 5. First-run setup

`POST /setup` starts op `setup` through `start_job` (note_id None). The worker calls `setup_assets.main(emit)`;
`download()` reports `("file", name)` and `("progress", (percent, received_mib, size_mib))` instead of printing
(CLI keeps printing). Existing files with matching sha256 are skipped. x64 skips the NPU bundle. On completion
the job state is `done` (no library write). The app checks `models_ready` at start; when false it shows a
full-window card "모델을 내려받는 중… (약 4.5 GB, 처음 한 번)" with the current file, its percent, and the list of
finished files; on error it shows the message and 다시 시도.

## 6. Cancel

`start_job` creates a per-job `threading.Event` (`JOB_CANCEL`); `run()` passes it to `run_job`. Shutdown sets
`CANCEL` and `JOB_CANCEL`. `POST /job/cancel` sets `JOB_CANCEL` when a job runs. The existing cancel path keeps
the finished text. UI: red 취소 button next to `.job-status` in the editor and a small pill on the dashboard while
op is `transcribe`.

## 7. Drag & drop

`bridge.js` exposes `onDrag(cb)` over `tauri://drag-enter|drag-over|drag-leave|drag-drop`. App shows an overlay
"오디오 파일을 여기에 끌어 놓으세요" while dragging; dropped paths with audio extensions go to a queue; the head is
started with `transcribe(path, device)` whenever the job is not running; on 409 it waits for the next tick.

## 8. System audio

Chooser live step gets a source `<select>`: 마이크 / 시스템 소리 (Zoom·Teams) / 마이크 + 시스템 소리
(`mic` / `system` / `both`). `/live` accepts `source` (default `mic`); mic is required for `mic` and `both`.

`engine.listen(command, stop, prefix, wav_path, label)` runs the given producer; `engine.mic_command(device)`
returns today's ffmpeg dshow line. jobs.py builds `[sys.executable, loopback.py] (+ ["--mic", name])` for
`system`/`both`.

`loopback.py`: ctypes COM → default render endpoint with `AUDCLNT_STREAMFLAGS_LOOPBACK`, optional capture
endpoint whose friendly name equals the dshow name (else default capture); shared mode, mix format; polling every
10 ms; downmix to mono, resample to 16 kHz (`np.interp`); pad silence when loopback delivers nothing (by elapsed
time); both = average of the two streams, clipped; s16le to stdout until killed.

## 9. Shortcut and tray

`tauri-plugin-global-shortcut`: Ctrl+Shift+R emits `toggle-recording` to the window. Tray "소리글": 열기 (show +
focus), 녹음 시작 (emits `toggle-recording`), 종료 (`app.exit(0)` → `stop_bridge`). The frontend handles
`toggle-recording`: running live job → `stopLive()`; idle → `startLive` with the last chooser choice
(localStorage `sori.live`), falling back to first mic / first device. Window close keeps today's behaviour.

## 10. Tests

Keep test_engine, test_diarize, test_library green. New `tests/test_server.py` (run_job stubbed, no model load):
/devices, /setup, /job/cancel, /live source validation, /transcribe device validation. test_engine: WhisperCPU
cpu and intel with a mocked onnxruntime/openvino; worker_environment for bundle layout. loopback: mixing/resample
helper self-check.

## 11. Verification

arm64: build installer, install to a clean dir, run: first-run setup (or skip), one file transcription, 10 s live
(마이크), cancel, drag & drop, Ctrl+Shift+R, tray; no pythonw left after quit. x64: installer builds; not
testable on Intel hardware here. The x64 bundle's `cpu` path may be smoke-tested under Prism x64 emulation.
