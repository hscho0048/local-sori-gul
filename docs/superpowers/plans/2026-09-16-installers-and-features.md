# 소리글 installers + features Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Installable NSIS builds for arm64 and x64 with a bundled embeddable Python, plus intel/cpu devices, file-job cancel, drag & drop, system audio, global shortcut and tray.

**Architecture:** Backend stays a stdlib HTTP bridge (`server.py`) that runs one model worker process at a time (`jobs.py`). A single env var `SORIGUL_HOME` moves all data. Release builds ship `python/` (embeddable CPython + package dirs + backend .py + ffmpeg) as Tauri resources; models download on first run through a `setup` job. Frontend is one `app.jsx` (React UMD, precompiled).

**Tech Stack:** Python 3.12 (stdlib + onnxruntime[-qnn|-openvino], numpy, transformers, onnx, openvino), ctypes WASAPI, Tauri 2.11 (Rust), tauri-plugin-global-shortcut, NSIS, React 18 UMD.

Spec: `docs/superpowers/specs/2026-09-16-installers-and-features-design.md`.

## Global Constraints

- Repo: `C:\Users\choho\sori-gul`, branch `main`. Never touch `C:\Users\choho\audio2text`.
- Keep every existing behaviour and Korean label. New labels exactly: "NPU (Hexagon)", "GPU (Adreno)", "인텔 GPU (OpenVINO)", "CPU", "취소", "오디오 파일을 여기에 끌어 놓으세요", "마이크", "시스템 소리 (Zoom·Teams)", "마이크 + 시스템 소리", "모델을 내려받는 중… (약 4.5 GB, 처음 한 번)", tray "소리글" with "열기" / "녹음 시작" / "종료".
- New Python deps allowed ONLY: `onnxruntime-openvino==1.24.1`, `openvino==2026.0.0` (x64 only). pyaudiowpatch is NOT used.
- No FastAPI, websockets, bundler, state library, settings screen, i18n layer, theme switcher, cloud, PyInstaller.
- Reuse, do not rewrite. Fewest files. One `ponytail:` comment per deliberate shortcut (name the ceiling + upgrade path).
- Tests run with: `.\.venv\Scripts\python.exe -m unittest tests.test_engine tests.test_diarize tests.test_library tests.test_server` — all must pass after every task (test_server exists from Task 4 on).
- Do not edit existing test assertions; add new tests.
- Windows ARM64 host (Snapdragon X Elite). Shell for commands: PowerShell. Python: `.\.venv\Scripts\python.exe`.
- Commit after each task; message ends with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## File map

| File | Change |
|---|---|
| `engine.py` | `ROOT` from `SORIGUL_HOME`, `CODE`; `ffmpeg_path` fallback; `load_text()` helper; `WhisperCPU`; `openvino_device()`; `mic_command()`; `listen(source, …)` accepts str or command list; `load_whisper` cpu/intel |
| `diarize.py`, `library.py` | `ROOT` from `SORIGUL_HOME` |
| `jobs.py` | `ROOT`/`CODE`; `worker_environment` setup→gpu env on ARM64; new `worker_python()`; `model_worker(..., packages)`; `setup` op; live `source` → producer |
| `setup_assets.py` | `ROOT`/`CODE`; `log` reporter; `download(..., emit)`; `required_files()`; `main(emit, whisper_gpu)`; NPU files only on ARM64; skip ffmpeg if bundled |
| `loopback.py` (new) | ctypes WASAPI loopback (+ mic) → 16 kHz mono s16le stdout; `mix()`, `pad()` helpers |
| `server.py` | `probe_devices()`, `GET /devices`, `POST /setup`, `POST /job/cancel`, per-job cancel, `/live` `source`, setup job fields |
| `tests/test_server.py` (new) | endpoint tests with stubbed `run_job` |
| `tests/test_engine.py` | new tests appended (cpu/intel mocked, worker_python, mic_command, loopback mix/pad) |
| `bridge.js`, `app.jsx`, `tokens.css` | devices, source select, cancel, setup screen, drag & drop queue, toggle-recording |
| `src-tauri/Cargo.toml`, `src-tauri/src/main.rs` | SORIGUL_HOME + release python path, tray, global shortcut |
| `scripts/build-python-bundle.ps1` (new), `src-tauri/tauri.arm64.conf.json`, `src-tauri/tauri.x64.conf.json` (new), `package.json`, `.gitignore` | bundle + installers |
| `requirements.txt` → `requirements-arm64.txt`, `requirements-x64.txt` (new), `setup.ps1`, `CLAUDE.md` | per-arch setup + docs |

---

### Task 1: Data dir, ffmpeg fallback, worker environments, per-arch requirements

**Files:**
- Modify: `engine.py` (lines 20, 62-66, 112-114), `diarize.py:17`, `library.py:10`, `setup_assets.py:10`, `jobs.py` (whole top + `model_worker` + `run_job` start)
- Rename: `requirements.txt` → `requirements-arm64.txt`; Create: `requirements-x64.txt`
- Modify: `setup.ps1`
- Test: `tests/test_engine.py` (append)

**Interfaces:**
- Produces: `engine.ROOT`, `engine.CODE` (Path); `engine.ffmpeg_path(ffmpeg=None) -> Path`; `jobs.CODE`; `jobs.worker_environment(op, payload) -> str` (unchanged for existing ops, `"setup"` → `".venv-whisper-gpu"` on ARM64); `jobs.worker_python(op, payload) -> (Path pythonw, Path | None packages)`; `jobs.model_worker(connection, cancelled, operation, payload, finish=None, packages=None)`.

- [ ] **Step 1: Write failing tests** — append to `tests/test_engine.py` (new class at end of file):

```python
class LayoutTests(unittest.TestCase):
    def test_sorigul_home_moves_data_but_not_code(self):
        import importlib, os
        import engine, jobs, library, diarize
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, {"SORIGUL_HOME": home}):
            try:
                for module in (engine, jobs, library, diarize):
                    importlib.reload(module)
                self.assertEqual(engine.ROOT, Path(home))
                self.assertEqual(library.LIBRARY, Path(home) / "library")
                self.assertEqual(diarize.MODEL_DIR, Path(home) / "models" / "speaker")
                self.assertEqual(jobs.CODE, Path(jobs.__file__).resolve().parent)
            finally:
                os.environ.pop("SORIGUL_HOME")
                for module in (engine, jobs, library, diarize):
                    importlib.reload(module)

    def test_ffmpeg_falls_back_to_the_copy_next_to_the_code(self):
        import engine
        with tempfile.TemporaryDirectory() as home, tempfile.TemporaryDirectory() as code:
            (Path(code) / "tools").mkdir()
            (Path(code) / "tools" / "ffmpeg.exe").write_bytes(b"")
            with patch("engine.ROOT", Path(home)), patch("engine.CODE", Path(code)):
                self.assertEqual(engine.ffmpeg_path(), Path(code) / "tools" / "ffmpeg.exe")
                (Path(home) / "tools").mkdir()
                (Path(home) / "tools" / "ffmpeg.exe").write_bytes(b"")
                self.assertEqual(engine.ffmpeg_path(), Path(home) / "tools" / "ffmpeg.exe")
            with patch("engine.ROOT", Path(home) / "x"), patch("engine.CODE", Path(home) / "y"):
                with self.assertRaisesRegex(RuntimeError, "오디오 디코더"):
                    engine.ffmpeg_path()

    def test_worker_python_uses_venvs_in_dev_and_package_dirs_in_the_bundle(self):
        import jobs
        with tempfile.TemporaryDirectory() as code, patch("jobs.CODE", Path(code)):
            self.assertEqual(jobs.worker_python("transcribe", {"device": "gpu"}),
                             (Path(code) / ".venv-whisper-gpu" / "Scripts" / "pythonw.exe", None))
            self.assertEqual(jobs.worker_python("transcribe", {"device": "cpu"}),
                             (Path(code) / ".venv" / "Scripts" / "pythonw.exe", None))
            (Path(code) / "python312._pth").write_text("")
            self.assertEqual(jobs.worker_python("listen", {"device": "gpu"}),
                             (Path(code) / "pythonw.exe", Path(code) / "Lib" / "gpu-packages"))
            self.assertEqual(jobs.worker_python("transcribe", {"device": "intel"}),
                             (Path(code) / "pythonw.exe", Path(code) / "Lib" / "site-packages"))
            with patch("jobs.platform.machine", return_value="ARM64"):
                self.assertEqual(jobs.worker_environment("setup", {}), ".venv-whisper-gpu")
            with patch("jobs.platform.machine", return_value="AMD64"):
                self.assertEqual(jobs.worker_environment("setup", {}), ".venv")
```

- [ ] **Step 2: Run** `.\.venv\Scripts\python.exe -m unittest tests.test_engine.LayoutTests -v` → FAIL (`CODE` / `worker_python` missing).

- [ ] **Step 3: Implement.**

`engine.py` line 20 becomes:
```python
CODE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("SORIGUL_HOME") or CODE)  # models/, tools/, diagnostics/ (installed app: %LOCALAPPDATA%\Sorigul)
```
`ffmpeg_path` becomes:
```python
def ffmpeg_path(ffmpeg=None):
    """Explicit path, else the data dir's tools/ffmpeg.exe, else the copy bundled next to this file."""
    for executable in [Path(ffmpeg)] if ffmpeg else [ROOT / "tools" / "ffmpeg.exe", CODE / "tools" / "ffmpeg.exe"]:
        if executable.is_file():
            return executable
    raise RuntimeError("오디오 디코더가 없습니다. setup.cmd를 실행해 주세요.")
```
In `decode_audio`, replace the three lines
```python
    executable = Path(ffmpeg) if ffmpeg else ROOT / "tools" / "ffmpeg.exe"
    if not executable.is_file():
        raise RuntimeError("오디오 디코더가 없습니다. setup.cmd를 실행해 주세요.")
```
with `    executable = ffmpeg_path(ffmpeg)`.

`diarize.py:17` → `ROOT = Path(os.environ.get("SORIGUL_HOME") or Path(__file__).resolve().parent)` (`os` is already imported).
`library.py:10` → same expression (add `import os` if missing).
`setup_assets.py:10` → 
```python
CODE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("SORIGUL_HOME") or CODE)
```
(add `import os`, `import platform`).

`jobs.py` top:
```python
import multiprocessing as mp
import os
from pathlib import Path
import platform
import sys
import time

CODE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("SORIGUL_HOME") or CODE)
RESULT_KIND = {"transcribe": "done", "listen": "done", "setup": "done"}


def worker_environment(operation, payload):
    gpu = operation in ("transcribe", "listen") and payload.get("device", "npu") == "gpu"
    # setup builds static-shape ONNX files, and only the GPU environment has `onnx` on ARM64
    return ".venv-whisper-gpu" if gpu or (operation == "setup" and platform.machine() == "ARM64") else ".venv"


def worker_python(operation, payload):
    """(pythonw.exe, package dir). Installed app: the embeddable interpreter this file lives next to and one of its
    two package dirs; dev: a venv, which finds its own site-packages (package dir None)."""
    venv = worker_environment(operation, payload)
    if (CODE / "python312._pth").is_file():
        return CODE / "pythonw.exe", CODE / "Lib" / ("gpu-packages" if venv == ".venv-whisper-gpu" else "site-packages")
    return CODE / venv / "Scripts" / "pythonw.exe", None
```
`model_worker` signature and sys.path swap:
```python
def model_worker(connection, cancelled, operation, payload, finish=None, packages=None):
    # spawn copies the parent's sys.path; swap in this worker's own packages (venv site-packages, or the bundle's
    # site-packages / gpu-packages dir) so the GPU child never imports the NPU runtime or vice versa.
    import site
    import sys
    sys.path = [p for p in sys.path if not p.endswith(("site-packages", "gpu-packages"))] + \
        ([packages] if packages else site.getsitepackages())
```
(`packages` is passed as `str`.) `run_job` start:
```python
    executable, packages = worker_python(operation, payload)
    if not executable.exists():
        raise RuntimeError("실행 환경이 없습니다. setup.cmd를 실행해 주세요.")
    # A Windows venv python.exe is a redirector ... (keep the existing comment)
    mp.set_executable(str(executable) if packages else getattr(sys, "_base_executable", sys.executable))
    ...
    process = context.Process(target=target, args=(send, stop, operation, payload, soft, packages and str(packages)))
    ...
    if not packages:
        os.environ["__PYVENV_LAUNCHER__"] = str(executable)
```
Also replace `ROOT / ".model.lock"` stays `ROOT` (data dir) — create the dir first: `ROOT.mkdir(parents=True, exist_ok=True)` right before opening the lock.

Rename: `git mv requirements.txt requirements-arm64.txt`. Create `requirements-x64.txt`:
```
# x64: onnxruntime-openvino provides the `onnxruntime` module (CPU + OpenVINO EPs); do not also install onnxruntime.
onnxruntime-openvino==1.24.1
openvino==2026.0.0
onnx==1.22.0
numpy==2.5.3
transformers==4.57.6
```
`setup.ps1` becomes:
```powershell
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$x64 = $env:PROCESSOR_ARCHITECTURE -eq 'AMD64'
$suffix = if ($x64) { '' } else { '-arm64' }
$pythonCandidates = '312', '311', '313' | ForEach-Object { "$env:LOCALAPPDATA\Programs\Python\Python$_$suffix\python.exe" }
$basePython = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
$machine = if ($x64) { 'AMD64' } else { 'ARM64' }

function Ensure-Venv($name, $requirements) {
    if (-not (Test-Path "$name\Scripts\python.exe")) {
        if (-not $basePython) { throw "Install native Windows $machine Python 3.12 from python.org, then run setup again." }
        & $basePython -m venv $name
        if ($LASTEXITCODE -ne 0) { throw "Could not create $name." }
    }
    $arch = & "$name\Scripts\python.exe" -c "import platform; print(platform.machine())"
    if ($arch -ne $machine) { throw "$name must use native $machine Python." }
    & "$name\Scripts\python.exe" -m pip install -r $requirements
    if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed for $name." }
}

if ($x64) {
    Ensure-Venv '.venv' 'requirements-x64.txt'
    $gpuPython = '.\.venv\Scripts\python.exe'
} else {
    Ensure-Venv '.venv' 'requirements-arm64.txt'
    Ensure-Venv '.venv-whisper-gpu' 'requirements-whisper-gpu.txt'
    $gpuPython = '.\.venv-whisper-gpu\Scripts\python.exe'
}
& .\.venv\Scripts\python.exe setup_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Asset download failed. Run setup again to retry.' }
& $gpuPython setup_assets.py --whisper-gpu
if ($LASTEXITCODE -ne 0) { throw 'GPU asset setup failed. Run setup again to retry.' }
Write-Host 'Ready. Run: npm install; npm run tauri:dev'
```

- [ ] **Step 4: Run all suites** → PASS (27 old + 3 new).
- [ ] **Step 5: Commit** `feat: SORIGUL_HOME data dir, bundled ffmpeg fallback, bundle-aware worker python, per-arch requirements`.

---

### Task 2: CPU / Intel devices, producer-based listen, setup job in the worker

**Files:**
- Modify: `engine.py`, `jobs.py`, `setup_assets.py`
- Test: `tests/test_engine.py` (append)

**Interfaces:**
- Consumes: Task 1 (`ROOT`, `CODE`, `worker_python`).
- Produces: `engine.WhisperCPU(emit, cancel, model_dir=None, profile=False, intel=False)`; `engine.openvino_device(available=None) -> "GPU"|"NPU"|"CPU"`; `engine.mic_command(device, ffmpeg=None) -> list[str]`; `WhisperNPU.listen(source, stop, prefix="", wav_path=None, ffmpeg=None)` where `source` is a dshow mic name (str) or a producer command (list); `engine.load_whisper(device)` accepts `npu|gpu|cpu|intel`; `setup_assets.log(kind, value)`; `setup_assets.download(url, target, sha=None, emit=log)`; `setup_assets.required_files() -> list[str]` (paths relative to `ROOT/"models"`); `setup_assets.main(emit=log, whisper_gpu=False)`; `setup_assets.setup_whisper_gpu(emit=log)`. Job emits for setup: `("file", name)`, `("progress", (percent, received_mib, size_mib))`, `("ready", name)`, `("stage", text)`. jobs payload for listen: `{"mic": str, "source": "mic"|"system"|"both", "device", "note_id"}`.

- [ ] **Step 1: Write failing tests** — append:

```python
class DeviceTests(unittest.TestCase):
    def fake_models(self, folder):
        for name in ("tokenizer.json", "preprocessor_config.json", "generation_config.json",
                     "whisper-gpu/encoder_static_fp16.onnx", "whisper-gpu/decoder_model_merged_fp16.onnx"):
            (Path(folder) / name).parent.mkdir(parents=True, exist_ok=True)
            (Path(folder) / name).write_text("{}")

    def load(self, intel, available=("CPU", "GPU.0")):
        """WhisperCPU with onnxruntime/openvino/tokenizers/transformers mocked; returns (worker, sessions created)."""
        import sys
        from types import ModuleType, SimpleNamespace
        from engine import WhisperCPU
        created = []

        class Session:
            def __init__(self, path, sess_options=None, providers=None):
                self.path, self.providers = path, providers
                created.append(self)
            def get_providers(self):
                return [p if isinstance(p, str) else p[0] for p in self.providers]
            def get_inputs(self):
                return [SimpleNamespace(name="input_features", type="tensor(float)")]
            def get_outputs(self):
                return [SimpleNamespace(name="logits")]

        ort = ModuleType("onnxruntime")
        ort.InferenceSession, ort.SessionOptions = Session, lambda: SimpleNamespace()
        ort.disable_telemetry_events = lambda: None
        tokenizers = ModuleType("tokenizers")
        tokenizers.Tokenizer = SimpleNamespace(from_file=lambda path: SimpleNamespace(
            token_to_id=lambda token: {"<|endoftext|>": 1}.get(token, 5)))
        transformers = ModuleType("transformers")
        transformers.WhisperFeatureExtractor = SimpleNamespace(from_pretrained=lambda *a, **k: "extractor")
        openvino = ModuleType("openvino")
        openvino.__file__ = str(Path(tempfile.gettempdir()) / "openvino" / "__init__.py")
        openvino.Core = lambda: SimpleNamespace(available_devices=list(available))
        stages = []
        with tempfile.TemporaryDirectory() as folder, patch.dict(sys.modules, {
                "onnxruntime": ort, "tokenizers": tokenizers, "transformers": transformers, "openvino": openvino,
                "onnxruntime_qnn": None}), patch("engine.os.add_dll_directory", return_value=None):
            self.fake_models(folder)
            worker = WhisperCPU(lambda kind, value: stages.append((kind, value)), threading.Event(),
                                model_dir=folder, intel=intel)
        return worker, created, stages

    def test_cpu_device_runs_both_sessions_on_the_cpu_without_qnn(self):
        worker, created, stages = self.load(intel=False)
        self.assertEqual([s.providers for s in created], [["CPUExecutionProvider"], ["CPUExecutionProvider"]])
        self.assertEqual(worker.limit, WhisperGPU.LIMIT)
        self.assertEqual(worker.encoder_dtype, np.float32)
        self.assertIn(("ready", "CPU"), stages)

    def test_intel_device_puts_the_encoder_on_openvino_gpu(self):
        # ponytail: mocked session only — untested on Intel hardware.
        worker, created, stages = self.load(intel=True)
        self.assertEqual(created[0].providers,
                         [("OpenVINOExecutionProvider", {"device_type": "GPU"}), "CPUExecutionProvider"])
        self.assertEqual(created[1].providers, ["CPUExecutionProvider"])
        self.assertIn(("ready", "인텔 GPU (OpenVINO) · CPU (decoder)"), stages)

    def test_openvino_device_prefers_gpu_then_npu_then_cpu(self):
        from engine import openvino_device
        self.assertEqual(openvino_device(["CPU", "NPU", "GPU.1"]), "GPU")
        self.assertEqual(openvino_device(["CPU", "NPU"]), "NPU")
        self.assertEqual(openvino_device(["CPU"]), "CPU")

    def test_load_whisper_routes_cpu_and_intel(self):
        import engine
        with patch("engine.WhisperCPU", side_effect=lambda *a, **k: k) as cpu:
            self.assertEqual(engine.load_whisper("cpu", None, None), {"intel": False})
            self.assertEqual(engine.load_whisper("intel", None, None), {"intel": True})
        with self.assertRaises(ValueError):
            engine.load_whisper("tpu", None, None)

    def test_listen_accepts_a_producer_command(self):
        import io
        from engine import mic_command
        with patch("engine.ffmpeg_path", return_value=Path("ffmpeg.exe")):
            command = mic_command("Mic A")
        self.assertIn("audio=Mic A", command)
        self.assertEqual(command[-1], "pipe:1")
        seen = {}

        class Producer:
            stdout, stderr, code = io.BytesIO(noise(3).tobytes()), io.BytesIO(b""), None
            def poll(self):
                return self.code
            def terminate(self):
                self.code = 0
            kill = terminate
            def wait(self):
                return 0

        def popen(command, **kwargs):
            seen["command"] = command
            return Producer()
        worker = WhisperNPU.__new__(WhisperNPU)
        worker.cancel, stop = threading.Event(), threading.Event()
        stages = []
        worker.emit = lambda kind, value: stages.append(value)
        worker.infer = lambda audio, preview: ("말", False)
        stop.set()
        with patch("engine.subprocess.Popen", side_effect=popen):
            self.assertEqual(worker.listen(["py", "loopback.py"], stop), "말")
        self.assertEqual(seen["command"], ["py", "loopback.py"])
        self.assertIn("🎙 녹음 중 · 시스템 소리", stages)
```

Also append a test for the setup reporter and required files:
```python
class SetupAssetTests(unittest.TestCase):
    def test_download_skips_a_verified_file_and_reports_ready(self):
        import hashlib
        import setup_assets
        with tempfile.TemporaryDirectory() as home, patch("setup_assets.ROOT", Path(home)):
            target = Path(home) / "models" / "a.bin"
            target.parent.mkdir(parents=True)
            target.write_bytes(b"abc")
            events = []
            setup_assets.download("http://invalid.example/a", target, hashlib.sha256(b"abc").hexdigest(),
                                  emit=lambda kind, value: events.append((kind, value)))
            self.assertEqual(events, [("ready", "models/a.bin")])

    def test_required_files_include_the_npu_bundle_only_on_arm64(self):
        import setup_assets
        with patch("setup_assets.platform.machine", return_value="AMD64"):
            x64 = setup_assets.required_files()
        with patch("setup_assets.platform.machine", return_value="ARM64"):
            arm = setup_assets.required_files()
        self.assertIn("whisper-gpu/encoder_static_fp16.onnx", x64)
        self.assertIn("speaker/speaker_static_198.onnx", x64)
        self.assertNotIn("encoder/model.bin", x64)
        self.assertIn("encoder/model.bin", arm)
```
(`noise(seconds, seed=0)` is the existing module-level helper in `tests/test_engine.py`, defined before these classes.)

- [ ] **Step 2: Run** `.\.venv\Scripts\python.exe -m unittest tests.test_engine -v` → new tests FAIL.

- [ ] **Step 3: Implement engine.py.**

Add to `WhisperNPU` (after `__init__`) and call it at the end of `WhisperNPU.__init__` and `WhisperGPU.__init__` in place of the duplicated tokenizer block (the lines from `self.tokenizer = Tokenizer.from_file(...)` to `self.suppress = ...`):
```python
    def load_text(self):
        """Tokenizer, feature extractor and Korean prompt, shared by every device."""
        from tokenizers import Tokenizer
        from transformers import WhisperFeatureExtractor
        self.tokenizer = Tokenizer.from_file(str(self.model_dir / "tokenizer.json"))
        self.extractor = WhisperFeatureExtractor.from_pretrained(str(self.model_dir), local_files_only=True)
        self.generation = json.loads((self.model_dir / "generation_config.json").read_text("utf-8"))
        self.prompt = [self.tokenizer.token_to_id(t) for t in
                       ("<|startoftranscript|>", "<|ko|>", "<|transcribe|>", "<|notimestamps|>")]
        self.eos = self.tokenizer.token_to_id("<|endoftext|>")
        if None in self.prompt or self.eos is None:
            raise RuntimeError("한국어 Whisper 토크나이저 구성이 올바르지 않습니다.")
        self.suppress = self.generation.get("suppress_tokens", [])
```
Remove now-unused `from tokenizers import Tokenizer` / `from transformers import WhisperFeatureExtractor` imports inside those two `__init__`s.

Add to `WhisperGPU` a helper and use it in its `__init__` (replacing the two file-check blocks):
```python
    def model_files(self):
        gpu_dir = self.model_dir / "whisper-gpu"
        encoder_file, decoder_file = gpu_dir / "encoder_static_fp16.onnx", gpu_dir / "decoder_model_merged_fp16.onnx"
        if not encoder_file.is_file() or not decoder_file.is_file():
            raise RuntimeError("GPU용 Whisper 모델이 없습니다. setup.cmd를 실행해 주세요.")
        for name in ("tokenizer.json", "preprocessor_config.json", "generation_config.json"):
            if not (self.model_dir / name).is_file():
                raise RuntimeError(f"모델 파일이 없습니다: {name}\n처음 한 번 setup.cmd를 실행해 주세요.")
        return encoder_file, decoder_file
```

New code after `WhisperGPU`:
```python
def openvino_device(available=None):
    """OpenVINO target for the encoder: GPU, else NPU, else CPU, as OpenVINO reports them ('GPU.0' counts as GPU)."""
    if available is None:
        import openvino
        available = openvino.Core().available_devices
    kinds = {name.split(".")[0] for name in available}
    return next((kind for kind in ("GPU", "NPU") if kind in kinds), "CPU")


class WhisperCPU(WhisperGPU):
    """WhisperGPU's model files and infer() without QNN, for any x64 or arm64 PC: both sessions on the CPU ('cpu'),
    or the encoder on Intel graphics through the OpenVINO execution provider ('intel')."""

    def __init__(self, emit, cancel, model_dir=None, profile=False, intel=False):
        self.emit, self.cancel = emit, cancel
        self.model_dir = Path(model_dir) if model_dir else ROOT / "models"
        encoder_file, decoder_file = self.model_files()
        encoder_providers, label = ["CPUExecutionProvider"], "CPU"
        if intel:
            import openvino
            # onnxruntime-openvino loads openvino.dll from PATH, which the pip package does not set up.
            libs = Path(openvino.__file__).parent / "libs"
            os.environ["PATH"] = f"{libs};{os.environ.get('PATH', '')}"
            self.dll_directory = os.add_dll_directory(str(libs)) if libs.is_dir() else None
            target = openvino_device()
            encoder_providers = [("OpenVINOExecutionProvider", {"device_type": target}), "CPUExecutionProvider"]
            label = f"인텔 {target} (OpenVINO) · CPU (decoder)"
        import onnxruntime as ort
        ort.disable_telemetry_events()
        check_cancel(cancel)
        emit("stage", "encoder 모델을 불러오는 중… (처음은 수 분)" if intel else "encoder 모델을 불러오는 중…")
        self.encoder = ort.InferenceSession(str(encoder_file), sess_options=ort.SessionOptions(), providers=encoder_providers)
        if intel and "OpenVINOExecutionProvider" not in self.encoder.get_providers():
            raise RuntimeError("OpenVINO 세션 생성에 실패했습니다. 인텔 그래픽 드라이버를 확인하거나 CPU를 선택해 주세요.")
        self.encoder_dtype = np.float16 if self.encoder.get_inputs()[0].type == "tensor(float16)" else np.float32
        check_cancel(cancel)
        emit("stage", "decoder 모델을 불러오는 중…")
        self.decoder = ort.InferenceSession(str(decoder_file), sess_options=ort.SessionOptions(),
                                            providers=["CPUExecutionProvider"])
        self.sessions = [self.encoder, self.decoder]
        self.decoder_inputs = [item.name for item in self.decoder.get_inputs()]
        self.decoder_outputs = [item.name for item in self.decoder.get_outputs()]
        self.limit = self.LIMIT
        self.load_text()
        emit("ready", label)
```
Note: the intel label in the test is `"인텔 GPU (OpenVINO) · CPU (decoder)"` — matches `f"인텔 {target} (OpenVINO) · CPU (decoder)"` with target GPU. `profile` is accepted and ignored for these devices.

`load_whisper`:
```python
def load_whisper(device, emit, cancel, **options):
    """'npu' = pre-compiled Hexagon bundle; 'gpu' = standard ONNX export on the Adreno GPU via QNN;
    'cpu' / 'intel' = the same export on the CPU / Intel graphics (OpenVINO)."""
    if device == "gpu":
        return WhisperGPU(emit, cancel, **options)
    if device == "npu":
        return WhisperNPU(emit, cancel, **options)
    if device in ("cpu", "intel"):
        return WhisperCPU(emit, cancel, intel=device == "intel", **options)
    raise ValueError("device must be 'npu', 'gpu', 'cpu' or 'intel'")
```
CLI: `choices=("npu", "gpu", "cpu", "intel")`.

Producer-based listen — add above `split_point`:
```python
def mic_command(device, ffmpeg=None):
    """ffmpeg streaming a DirectShow microphone as 16 kHz mono s16le on stdout."""
    return [str(ffmpeg_path(ffmpeg)), "-hide_banner", "-loglevel", "error", "-nostdin", "-f", "dshow",
            "-audio_buffer_size", "50", "-i", f"audio={device}", "-ac", "1", "-ar", str(RATE), "-f", "s16le", "pipe:1"]
```
In `listen`, change the signature and the first lines:
```python
    def listen(self, source, stop, prefix="", wav_path=None, ffmpeg=None):
        """Live transcription: `source` is a microphone name (streamed by ffmpeg) or a producer command writing 16 kHz
        mono s16le to stdout (loopback.py). The buffer is cut at pauses ... (keep the rest of the docstring)"""
        command = mic_command(source, ffmpeg) if isinstance(source, str) else source
        label = source if isinstance(source, str) else "시스템 소리"
```
and `self.emit("stage", f"🎙 녹음 중 · {device}")` → `f"🎙 녹음 중 · {label}"`. Nothing else in `listen` changes.

- [ ] **Step 4: Implement setup_assets.py.**

```python
def log(kind, value):
    """CLI reporter; the app passes the job's emit instead."""
    if kind == "file":
        print(f"Downloading: {value}", flush=True)
    elif kind == "progress":
        print(f"  {value[0]:.0f}% ({value[1]} MiB)", flush=True)
    elif kind in ("ready", "stage"):
        print(f"Ready: {value}" if kind == "ready" else value, flush=True)


def required_files():
    """Model files (relative to models/) the app needs on this machine; the NPU bundle only exists for ARM64."""
    from diarize import FRAMES
    names = ["tokenizer.json", "generation_config.json", "preprocessor_config.json",
             f"speaker/speaker_static_{FRAMES}.onnx",
             "whisper-gpu/encoder_static_fp16.onnx", "whisper-gpu/decoder_model_merged_fp16.onnx"]
    return (list(FILES) if platform.machine() == "ARM64" else []) + names
```
`download(url, target, sha=None, emit=log)`: replace prints —
- skip branch: `emit("ready", target.relative_to(ROOT).as_posix()); return`
- start: `name = target.relative_to(ROOT).as_posix()`, `emit("file", name)`
- progress: compute `progress = received * 100 // size if size else 0`; when `progress != last`: `emit("progress", (progress, received // 1048576, size // 1048576)); last = progress` (every 1 %).
- end (after `partial.replace(target)`): `emit("ready", name)`.

`setup_whisper_gpu(emit=log)`: pass `emit=emit` to both `download` calls; replace the two `print("Ready: GPU encoder with static audio shape", flush=True)` with `emit("ready", "whisper-gpu/encoder_static_fp16.onnx")`; before `onnx.load(str(source))` add `emit("stage", "GPU 인코더를 고정 형태로 변환하는 중…")`.

`main`:
```python
def main(emit=log, whisper_gpu=False):
    """Every model this machine needs, then (with whisper_gpu) the static-shape encoder. Files already present with
    the right checksum are skipped, so an interrupted first run resumes."""
    if platform.machine() == "ARM64":
        for name, sha in FILES.items():
            download(f"{BASE}/{name}", ROOT / "models" / name, sha, emit)
    for name in ("tokenizer.json", "generation_config.json", "preprocessor_config.json"):
        download(f"https://huggingface.co/openai/whisper-large-v3-turbo/resolve/{TOKENIZER_REV}/{name}", ROOT / "models" / name, emit=emit)
    from diarize import FRAMES, MODEL_FILE, static_model
    download(SPEAKER_URL, ROOT / "models" / "speaker" / MODEL_FILE, SPEAKER_SHA, emit)
    static = ROOT / "models" / "speaker" / f"speaker_static_{FRAMES}.onnx"
    if not static.is_file():
        emit("stage", "화자 분리 모델 고정 형태로 변환 중… (처음 한 번)")
        static_model(ROOT / "models" / "speaker" / MODEL_FILE, static)  # both venvs read this fixed-shape copy
    if not (CODE / "tools" / "ffmpeg.exe").is_file():  # the installed app bundles ffmpeg
        (keep the existing wheel download + extraction block, passing emit=emit to download)
    if whisper_gpu:
        setup_whisper_gpu(emit)
    emit("stage", "Setup complete. Inference needs no network.")
```
(Existing message "Setup complete. Run start.cmd. Inference needs no network." becomes the stage line above.)
`__main__`: `if parser.parse_args().whisper_gpu: setup_whisper_gpu() else: main()`.

- [ ] **Step 5: Implement jobs.py.**

In `model_worker`, the listen branch:
```python
            elif operation == "listen":
                import tempfile
                from engine import load_whisper
                source = payload.get("source", "mic")
                producer = payload["mic"] if source == "mic" else \
                    [sys.executable, str(CODE / "loopback.py")] + (["--mic", payload["mic"]] if source == "both" else [])
                wav = Path(tempfile.gettempdir()) / f"audio2text-live-{int(time.time())}.wav"
                try:
                    result = load_whisper(payload.get("device", "npu"), emit, cancelled).listen(
                        producer, finish, prefix=payload.get("prefix", ""), wav_path=wav)
```
(rest unchanged). Add before `else: raise ValueError`:
```python
            elif operation == "setup":
                import setup_assets
                setup_assets.main(emit, whisper_gpu=True)
                result = None
```
(The file lock is taken for `setup` too, so a download never races a model load.) The existing `SpeakerEmbedder("npu" if device == "npu" else "cpu")` already sends cpu/intel diarization to the CPU — leave it.

- [ ] **Step 6: Run all suites** → PASS.
- [ ] **Step 7: Real-model check (this machine):** `$env:SORIGUL_HOME=$PWD; .\.venv\Scripts\python.exe engine.py <some .wav under library\audio or a new 10 s recording> --output $env:TEMP\cpu-check.txt --device cpu` → prints `ready CPU` and `Saved:`. Record the output.
- [ ] **Step 8: Commit** `feat: cpu and intel (OpenVINO) devices, producer-based listen, setup job with progress`.

---

### Task 3: loopback.py (ctypes WASAPI)

**Files:**
- Create: `loopback.py`
- Test: `tests/test_engine.py` (append)

**Interfaces:**
- Consumes: nothing (stdlib ctypes + numpy only).
- Produces: CLI `python loopback.py [--mic NAME]` → endless 16 kHz mono s16le on stdout (system sound; with `--mic`, system + that microphone mixed). Helpers `mix(a, b) -> (np.int16 array, rest_a, rest_b)` and `pad(buffer, produced, expected, slack) -> np.int16 array`.

- [ ] **Step 1: Failing test** — append:
```python
class LoopbackTests(unittest.TestCase):
    def test_mix_averages_the_overlap_and_keeps_the_rest(self):
        from loopback import mix
        a = np.array([30000, 30000, -30000, 4], dtype=np.int16)
        b = np.array([30000, -30000, -30000], dtype=np.int16)
        mixed, rest_a, rest_b = mix(a, b)
        self.assertEqual(mixed.tolist(), [30000, 0, -30000])
        self.assertEqual(rest_a.tolist(), [4])
        self.assertEqual(rest_b.tolist(), [])

    def test_pad_fills_silence_only_when_the_loopback_falls_behind(self):
        from loopback import pad
        chunk = np.ones(10, dtype=np.int16)
        self.assertEqual(len(pad(chunk, produced=100, expected=105, slack=20)), 10)   # jitter: untouched
        padded = pad(np.zeros(0, dtype=np.int16), produced=100, expected=200, slack=20)
        self.assertEqual(len(padded), 100)                                             # idle output: silence
        self.assertFalse(padded.any())
```
- [ ] **Step 2: Run** → FAIL (no module).
- [ ] **Step 3: Implement `loopback.py`:**

```python
"""System sound (WASAPI loopback of the default output device), optionally mixed with a microphone, as 16 kHz mono
s16le on stdout until killed. Stdlib ctypes COM; the engine reads it exactly like its ffmpeg microphone stream.

    python loopback.py              system sound only
    python loopback.py --mic NAME   system sound + the capture device with that name (else the default one)
"""
import argparse
import ctypes
from ctypes import POINTER, byref, c_uint16, c_uint32, c_uint64, c_void_p, c_wchar_p, HRESULT
import sys
import time
import uuid

import numpy as np

RATE = 16000
CLSCTX_ALL = 0x17
E_RENDER, E_CAPTURE, E_CONSOLE, DEVICE_STATE_ACTIVE = 0, 1, 0, 1
LOOPBACK, AUTOCONVERTPCM, SRC_DEFAULT_QUALITY = 0x00020000, 0x80000000, 0x08000000
SILENT = 0x2


class GUID(ctypes.Structure):
    _fields_ = [("data", ctypes.c_ubyte * 16)]

    def __init__(self, text):
        super().__init__()
        ctypes.memmove(self.data, uuid.UUID(text).bytes_le, 16)


class WAVEFORMATEX(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("wFormatTag", c_uint16), ("nChannels", c_uint16), ("nSamplesPerSec", c_uint32),
                ("nAvgBytesPerSec", c_uint32), ("nBlockAlign", c_uint16), ("wBitsPerSample", c_uint16),
                ("cbSize", c_uint16)]


class PROPERTYKEY(ctypes.Structure):
    _fields_ = [("fmtid", GUID), ("pid", c_uint32)]


class PROPVARIANT(ctypes.Structure):
    _fields_ = [("vt", c_uint16), ("reserved", c_uint16 * 3), ("value", c_void_p), ("extra", c_void_p)]


CLSID_MMDeviceEnumerator = GUID("BCDE0395-E52F-467C-8E3D-C4579291692E")
IID_IMMDeviceEnumerator = GUID("A95664D2-9614-4F35-A746-DE8DB63617E6")
IID_IAudioClient = GUID("1CB9AD4C-DBFA-4C32-B178-C2F568A703B2")
IID_IAudioCaptureClient = GUID("C8ADBD64-E71E-48A0-A4DE-185C395CD317")
PKEY_Device_FriendlyName = PROPERTYKEY(GUID("A45C254E-DF1C-4EFD-8020-67D146A850E0"), 14)


def call(this, index, *args):
    """COM vtable call: args are (ctype, value) pairs; raises OSError on a failed HRESULT."""
    vtable = ctypes.cast(this, POINTER(POINTER(c_void_p))).contents
    prototype = ctypes.WINFUNCTYPE(HRESULT, c_void_p, *[kind for kind, _ in args])
    return prototype(vtable[index])(this, *[value for _, value in args])


def release(this):
    if this:
        ctypes.WINFUNCTYPE(c_uint32, c_void_p)(ctypes.cast(this, POINTER(POINTER(c_void_p))).contents[2])(this)


def friendly_name(device):
    store = c_void_p()
    call(device, 4, (c_uint32, 0), (POINTER(c_void_p), byref(store)))  # OpenPropertyStore(STGM_READ)
    try:
        value = PROPVARIANT()
        call(store, 5, (POINTER(PROPERTYKEY), byref(PKEY_Device_FriendlyName)), (POINTER(PROPVARIANT), byref(value)))
        return ctypes.wstring_at(value.value) if value.value else ""
    finally:
        release(store)


def endpoint(enumerator, flow, name=None):
    """The active endpoint whose friendly name matches `name` (DirectShow uses the same names), else the default."""
    if name:
        collection, count = c_void_p(), c_uint32()
        call(enumerator, 3, (c_uint32, flow), (c_uint32, DEVICE_STATE_ACTIVE), (POINTER(c_void_p), byref(collection)))
        call(collection, 3, (POINTER(c_uint32), byref(count)))
        try:
            for index in range(count.value):
                device = c_void_p()
                call(collection, 4, (c_uint32, index), (POINTER(c_void_p), byref(device)))
                label = friendly_name(device)
                if label == name or label.startswith(name) or name.startswith(label):
                    return device
                release(device)
        finally:
            release(collection)
    device = c_void_p()
    call(enumerator, 4, (c_uint32, flow), (c_uint32, E_CONSOLE), (POINTER(c_void_p), byref(device)))
    return device


class Capture:
    """Shared-mode WASAPI capture that lets Windows convert to 16 kHz mono 16-bit PCM (AUTOCONVERTPCM)."""

    def __init__(self, device, loopback):
        self.client, self.capture = c_void_p(), c_void_p()
        call(device, 3, (POINTER(GUID), byref(IID_IAudioClient)), (c_uint32, CLSCTX_ALL), (c_void_p, None),
             (POINTER(c_void_p), byref(self.client)))  # IMMDevice::Activate
        pcm = WAVEFORMATEX(1, 1, RATE, RATE * 2, 2, 16, 0)
        flags = AUTOCONVERTPCM | SRC_DEFAULT_QUALITY | (LOOPBACK if loopback else 0)
        call(self.client, 3, (c_uint32, 0), (c_uint32, flags), (ctypes.c_int64, 2_000_000), (ctypes.c_int64, 0),
             (POINTER(WAVEFORMATEX), byref(pcm)), (c_void_p, None))  # Initialize: shared, 200 ms buffer
        call(self.client, 14, (POINTER(GUID), byref(IID_IAudioCaptureClient)), (POINTER(c_void_p), byref(self.capture)))
        call(self.client, 10)  # Start

    def read(self):
        chunks = []
        size = c_uint32()
        while True:
            call(self.capture, 5, (POINTER(c_uint32), byref(size)))  # GetNextPacketSize
            if not size.value:
                break
            data, frames, flags = c_void_p(), c_uint32(), c_uint32()
            call(self.capture, 3, (POINTER(c_void_p), byref(data)), (POINTER(c_uint32), byref(frames)),
                 (POINTER(c_uint32), byref(flags)), (POINTER(c_uint64), None), (POINTER(c_uint64), None))
            if flags.value & SILENT or not data.value:
                chunks.append(np.zeros(frames.value, dtype=np.int16))
            else:
                chunks.append(np.frombuffer(ctypes.string_at(data.value, frames.value * 2), dtype=np.int16).copy())
            call(self.capture, 4, (c_uint32, frames.value))  # ReleaseBuffer
        return np.concatenate(chunks) if chunks else np.zeros(0, dtype=np.int16)


def mix(a, b):
    """Average the overlapping samples of two streams; return the mix and what is left of each."""
    n = min(len(a), len(b))
    mixed = ((a[:n].astype(np.int32) + b[:n].astype(np.int32)) // 2).astype(np.int16)
    return mixed, a[n:], b[n:]


def pad(chunk, produced, expected, slack):
    """WASAPI loopback delivers nothing while no sound plays; append silence once the stream is more than `slack`
    samples behind the wall clock, so the output keeps real-time pace."""
    missing = expected - produced - len(chunk)
    return np.concatenate([chunk, np.zeros(missing, dtype=np.int16)]) if missing > slack else chunk


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mic")
    args = parser.parse_args()
    ole32 = ctypes.OleDLL("ole32")
    ole32.CoInitializeEx(None, 0)
    enumerator = c_void_p()
    ole32.CoCreateInstance(byref(CLSID_MMDeviceEnumerator), None, CLSCTX_ALL, byref(IID_IMMDeviceEnumerator),
                           byref(enumerator))
    system = Capture(endpoint(enumerator, E_RENDER), loopback=True)
    mic = Capture(endpoint(enumerator, E_CAPTURE, args.mic), loopback=False) if args.mic is not None else None
    out = sys.stdout.buffer
    start, produced = time.monotonic(), 0
    pending_system = pending_mic = np.zeros(0, dtype=np.int16)
    # ponytail: 10 ms polling instead of event handles; switch to SetEventHandle if CPU use ever shows up.
    while True:
        time.sleep(0.01)
        chunk = pad(system.read(), produced, int((time.monotonic() - start) * RATE), RATE // 10)
        produced += len(chunk)
        if mic is None:
            block = chunk
        else:
            pending_system = np.concatenate([pending_system, chunk])
            pending_mic = np.concatenate([pending_mic, mic.read()])
            block, pending_system, pending_mic = mix(pending_system, pending_mic)
        if len(block):
            try:
                out.write(block.tobytes())
                out.flush()
            except (BrokenPipeError, OSError):
                return


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run all suites** → PASS.
- [ ] **Step 5: Hardware check on this machine:** play any sound (e.g. `Start-Process ms-settings:sound` is NOT sound — instead run `(New-Object Media.SoundPlayer "C:\Windows\Media\Alarm01.wav").PlayLooping()` in another PowerShell), then:
```powershell
$p = Start-Process .\.venv\Scripts\python.exe -ArgumentList 'loopback.py' -RedirectStandardOutput $env:TEMP\loop.pcm -PassThru -NoNewWindow; Start-Sleep 3; Stop-Process $p
.\.venv\Scripts\python.exe -c "import numpy as n,os; a=n.fromfile(os.environ['TEMP']+'/loop.pcm',dtype='<i2'); print(len(a)/16000,'s', int(n.abs(a).max()))"
```
Expected: about 3 s (±0.5) and a non-zero peak while sound plays; about 3 s of zeros when nothing plays. Repeat with `--mic ""` style real mic name from `GET /mics` (or `.\.venv\Scripts\python.exe -c "from engine import audio_devices; print(audio_devices())"`). If `Initialize` fails with AUTOCONVERTPCM in loopback mode, fall back to `GetMixFormat` (vtable 8) + `np.interp` resampling and downmix inside `Capture.read()`; record which path was needed.
- [ ] **Step 6: Commit** `feat: loopback.py - WASAPI system sound (+ mic mix) via ctypes`.

---

### Task 4: server endpoints — /devices, /setup, /job/cancel, /live source

**Files:**
- Modify: `server.py`
- Create: `tests/test_server.py`

**Interfaces:**
- Consumes: `jobs.worker_python`, `engine.openvino_device`, `setup_assets.required_files`, `setup_assets.ROOT`.
- Produces (HTTP, all need `X-Bridge-Token`):
  - `GET /devices` → `{"devices": [{"id": "npu", "label": "NPU (Hexagon)"}, …], "models_ready": bool}`
  - `POST /setup` `{}` → `{"ok": true}`; 409 while a job runs. Job fields while running: `op: "setup"`, `file`, `ready` (list), `progress` (`[percent, mib, total_mib]`), `percent`, `stage`.
  - `POST /job/cancel` `{}` → `{"ok": true}` (cancels a running `transcribe` job only).
  - `POST /live` `{"mic", "device", "source": "mic"|"system"|"both"}`.
  - `device` omitted → first probed device; unknown → 400.
  - `server.probe_devices() -> list[str]` (cached).

- [ ] **Step 1: Write `tests/test_server.py`:**
```python
import json
import tempfile
import threading
import time
import unittest
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import server


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        home = Path(self.folder.name)
        self.patches = [patch("library.LIBRARY", home / "library"), patch("library.DB", home / "library" / "notes.db"),
                        patch("server.probe_devices", return_value=["npu", "cpu"])]
        for p in self.patches:
            p.start()
        self.calls = []
        self.release = threading.Event()

        def fake_run_job(operation, payload, emit, cancel, finish=None):
            self.calls.append((operation, payload))
            while not (self.release.is_set() or cancel.is_set() or (finish and finish.is_set())):
                time.sleep(0.01)
            emit("text", "부분")
            emit("cancelled" if cancel.is_set() else "done", None if cancel.is_set() else "완료")
        self.patches.append(patch("server.run_job", fake_run_job))
        self.patches[-1].start()
        server.JOB = {"state": "idle"}
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def tearDown(self):
        self.release.set()
        if server.WORKER:
            server.WORKER.join(5)
        self.httpd.shutdown()
        self.httpd.server_close()
        for p in self.patches:
            p.stop()
        self.folder.cleanup()

    def request(self, method, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(f"http://127.0.0.1:{self.httpd.server_address[1]}{path}", data=data,
                                         method=method, headers={"X-Bridge-Token": server.TOKEN,
                                                                 "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def wait_for(self, state):
        for _ in range(300):
            if server.JOB.get("state") == state:
                return
            time.sleep(0.01)
        self.fail(f"job never reached {state}: {server.JOB}")

    def audio(self):
        path = Path(self.folder.name) / "회의.wav"
        path.write_bytes(b"RIFF")
        return str(path)

    def test_devices_lists_probed_ids_with_labels_and_model_state(self):
        with patch("server.models_ready", return_value=False):
            status, body = self.request("GET", "/devices")
        self.assertEqual(status, 200)
        self.assertEqual(body, {"devices": [{"id": "npu", "label": "NPU (Hexagon)"}, {"id": "cpu", "label": "CPU"}],
                                "models_ready": False})

    def test_models_ready_checks_every_required_file(self):
        with tempfile.TemporaryDirectory() as home, patch("server.ROOT", Path(home)), \
                patch("server.required_files", return_value=["a.onnx", "speaker/b.onnx"]):
            self.assertFalse(server.models_ready())
            (Path(home) / "models" / "speaker").mkdir(parents=True)
            (Path(home) / "models" / "a.onnx").write_text("")
            (Path(home) / "models" / "speaker" / "b.onnx").write_text("")
            self.assertTrue(server.models_ready())

    def test_transcribe_rejects_unprobed_device_and_defaults_to_the_first(self):
        self.assertEqual(self.request("POST", "/transcribe", {"path": self.audio(), "device": "gpu"})[0], 400)
        status, body = self.request("POST", "/transcribe", {"path": self.audio()})
        self.assertEqual(status, 200)
        self.wait_for("running")
        self.assertEqual(self.calls[0][1]["device"], "npu")

    def test_cancel_stops_only_the_running_transcription_and_keeps_its_text(self):
        status, body = self.request("POST", "/transcribe", {"path": self.audio(), "device": "cpu"})
        self.wait_for("running")
        self.assertEqual(self.request("POST", "/job/cancel", {}), (200, {"ok": True}))
        self.wait_for("error")
        self.assertEqual(server.JOB["error"], "취소됐습니다.")
        self.assertFalse(server.CANCEL.is_set())  # shutdown flag untouched
        from library import Library
        library = Library()
        try:
            self.assertEqual(library.get(body["note_id"])["transcript"], "부분")
        finally:
            library.close()
        # the next job gets a fresh cancel event
        self.request("POST", "/transcribe", {"path": self.audio(), "device": "cpu"})
        self.wait_for("running")
        self.release.set()
        self.wait_for("done")

    def test_cancel_does_not_touch_a_live_recording(self):
        self.request("POST", "/live", {"mic": "Mic", "source": "mic"})
        self.wait_for("running")
        self.request("POST", "/job/cancel", {})
        time.sleep(0.1)
        self.assertEqual(server.JOB["state"], "running")
        self.request("POST", "/live/stop", {})
        self.wait_for("done")

    def test_live_source_validation_and_payload(self):
        self.assertEqual(self.request("POST", "/live", {"source": "radio", "mic": "Mic"})[0], 400)
        self.assertEqual(self.request("POST", "/live", {"source": "both"})[0], 400)
        status, _ = self.request("POST", "/live", {"source": "system"})
        self.assertEqual(status, 200)
        self.wait_for("running")
        self.assertEqual(self.calls[0][0], "listen")
        self.assertEqual(self.calls[0][1]["source"], "system")
        self.request("POST", "/live/stop", {})
        self.wait_for("done")

    def test_setup_runs_as_a_job_without_a_note(self):
        self.assertEqual(self.request("POST", "/setup", {}), (200, {"ok": True}))
        self.wait_for("running")
        self.assertEqual(server.JOB["op"], "setup")
        self.assertEqual(server.JOB["ready"], [])
        self.assertEqual(self.request("POST", "/setup", {})[0], 409)
        self.release.set()
        self.wait_for("done")
        self.assertEqual(self.calls[0], ("setup", {}))

    def test_setup_progress_fields(self):
        emit = server.job_emitter("setup", None)
        server.JOB = {"state": "running", "op": "setup", "ready": [], "file": "", "progress": [], "percent": 0}
        emit("file", "models/a.bin")
        emit("progress", (40, 4, 10))
        emit("ready", "models/a.bin")
        self.assertEqual((server.JOB["file"], server.JOB["percent"], server.JOB["progress"], server.JOB["ready"]),
                         ("models/a.bin", 40, [40, 4, 10], ["models/a.bin"]))
```
`Library.__init__` reads the module-level `library.DB` at call time (`Path(path or DB)`), and audio copies live under `library.LIBRARY`, so patching those two names keeps every `Library()` in server.py inside the temp dir.

- [ ] **Step 2: Run** `.\.venv\Scripts\python.exe -m unittest tests.test_server -v` → FAIL.

- [ ] **Step 3: Implement server.py.**

Imports: add `import functools`, `import importlib.util`, `import platform`; `from jobs import run_job, worker_python`; `from setup_assets import ROOT, required_files`.

Globals:
```python
CANCEL = threading.Event()  # set only on shutdown: no new jobs after that
JOB_CANCEL = threading.Event()  # the running job's own cancel (취소 or shutdown); replaced per job
LABELS = {"npu": "NPU (Hexagon)", "gpu": "GPU (Adreno)", "intel": "인텔 GPU (OpenVINO)", "cpu": "CPU"}
```

Probe + readiness:
```python
@functools.cache
def probe_devices():
    """Devices usable on this PC, probed once without loading a model or importing QNN on x64."""
    ids = []
    if platform.machine() == "ARM64":
        spec = importlib.util.find_spec("onnxruntime")
        if spec and (Path(spec.origin).parent / "capi" / "QnnHtp.dll").is_file():
            ids.append("npu")
        python, packages = worker_python("transcribe", {"device": "gpu"})
        if python.is_file() and (packages is None or packages.is_dir()):
            ids.append("gpu")
    else:
        try:
            from engine import openvino_device
            if openvino_device() in ("GPU", "NPU"):
                ids.append("intel")
        except Exception:
            pass  # no OpenVINO runtime or no Intel device: CPU only
    return ids + ["cpu"]


def models_ready():
    return all((ROOT / "models" / name).is_file() for name in required_files())
```
`device(body)`:
```python
def device(body):
    available = probe_devices()
    value = body.get("device") or available[0]
    if value not in available:
        raise HttpError(400, f"device must be one of {', '.join(available)}")
    return value
```
`start_job` — add `global JOB_CANCEL`, and inside the lock after `ensure_idle()`:
```python
        if CANCEL.is_set():
            raise HttpError(503, "앱을 종료하는 중입니다.")
        FINISH.clear()
        JOB_CANCEL = threading.Event()
        finished = ""
        JOB = {"state": "running", "op": operation, "note_id": note_id, "stage": "준비 중", "text": "", "percent": 0,
               "error": None, "file": "", "ready": [], "progress": []}
    WORKER = threading.Thread(target=run, args=(operation, payload, note_id, JOB_CANCEL), daemon=True)
```
Split `run` into an emitter factory (so the test can drive it) and the thread body:
```python
def job_emitter(operation, note_id):
    duration = None

    def emit(kind, value):
        (existing body, plus these branches, before `elif kind == "done"`:)
        elif kind == "file":
            JOB["file"] = value
            JOB["stage"] = f"{value} 내려받는 중"
        elif kind == "ready":
            JOB["ready"] = JOB.get("ready", []) + [value]
        ...
    return emit
```
The existing `progress` branch becomes:
```python
        elif kind == "progress":
            JOB["percent"] = value[0]
            JOB["progress"] = list(value)
```
and the `done` branch starts with:
```python
        elif kind == "done":
            if operation == "setup":
                JOB.update(state="done", percent=100)
                return
            (existing code)
```
The error/cancel branch: `if finished and note_id is not None:`.
```python
def run(operation, payload, note_id, cancel):
    emit = job_emitter(operation, note_id)
    try:
        run_job(operation, payload, emit, cancel, finish=FINISH)
    except Exception as error:
        emit("error", str(error))
```
(`nonlocal duration` stays inside `emit`; `global finished` stays.)

Routes:
```python
@route("GET", r"/devices")
def devices(library, body, query):
    return {"devices": [{"id": d, "label": LABELS[d]} for d in probe_devices()], "models_ready": models_ready()}


@route("POST", r"/setup")
def setup(library, body, query):
    start_job("setup", {}, None)
    return {"ok": True}


@route("POST", r"/job/cancel")
def cancel_job(library, body, query):
    if JOB.get("state") == "running" and JOB.get("op") == "transcribe":
        JOB_CANCEL.set()
    return {"ok": True}
```
`/live`:
```python
@route("POST", r"/live")
def live(library, body, query):
    source = body.get("source", "mic")
    if source not in ("mic", "system", "both"):
        raise HttpError(400, "source must be 'mic', 'system' or 'both'")
    if source != "system" and not body.get("mic"):
        raise HttpError(400, "마이크를 선택해 주세요.")
    selected = device(body)
    ensure_idle()
    note_id = library.create(f"실시간 전사 {datetime.now():%Y-%m-%d %H:%M}", "live")
    start_job("listen", {"mic": body.get("mic", ""), "source": source, "device": selected, "note_id": note_id}, note_id)
    return {"note_id": note_id}
```
`main()`: after printing PORT add `threading.Thread(target=probe_devices, daemon=True).start()  # warm the cache (OpenVINO import can take seconds)`; at shutdown replace `CANCEL.set()` block with:
```python
    CANCEL.set()  # no new jobs from here on
    if JOB.get("state") == "running" and JOB.get("op") == "listen":
        FINISH.set()  # same as ⏹ 녹음 마치기: the tail is transcribed and jobs.py attaches the WAV to the note
    else:
        JOB_CANCEL.set()  # other jobs are discarded; the worker notices between chunks
```
Update the module docstring's last sentence if needed; nothing else changes.

- [ ] **Step 4: Run all four suites** → PASS.
- [ ] **Step 5: Commit** `feat: /devices, /setup, /job/cancel, live source; per-job cancel event`.

---

### Task 5: Frontend — devices, source, cancel, first-run screen, drag & drop, toggle-recording

**Files:**
- Modify: `bridge.js`, `app.jsx`, `tokens.css`

**Interfaces:**
- Consumes: Task 4 endpoints; Tauri events `tauri://drag-enter|drag-over|drag-leave|drag-drop` (payload `{paths: string[], position}`) and app event `toggle-recording` (Task 6).
- Produces: `window.SoriBridge.devices()`, `.setup()`, `.cancelJob()`, `.startLive(mic, device, source)`, `.onDrag(handler(type, payload))`, `.onToggleRecording(handler)`, `.isAudio(path)`; errors thrown by `call` carry `.status`. localStorage key `sori.live` = `{device, mic, source}`.

- [ ] **Step 1: bridge.js** — in `call`, replace the throw with:
```js
    if (!response.ok) {
      const error = new Error(data.error || response.statusText);
      error.status = response.status;
      throw error;
    }
```
Replace `startLive` and add entries:
```js
    devices: () => call('GET', '/devices'),
    setup: () => call('POST', '/setup', {}),
    cancelJob: () => call('POST', '/job/cancel', {}),
    startLive: (mic, device, source) => call('POST', '/live', { mic, device, source }),
    // Tauri's native drag & drop (paths, not File objects); type is enter | over | leave | drop.
    onDrag: (handler) => ['enter', 'over', 'leave', 'drop'].forEach((type) =>
      tauri.event.listen(`tauri://drag-${type}`, (event) => handler(type, event.payload || {}))),
    onToggleRecording: (handler) => tauri.event.listen('toggle-recording', handler),
    isAudio: (path) => AUDIO.includes(String(path).split('.').pop().toLowerCase()),
```

- [ ] **Step 2: app.jsx helpers** — replace `const DEVICES = …` (line 45) with:
```jsx
const SOURCES = [['mic', '마이크'], ['system', '시스템 소리 (Zoom·Teams)'], ['both', '마이크 + 시스템 소리']];
// Last live-recording choice, reused by the chooser and by Ctrl+Shift+R / the tray.
const loadLive = () => { try { return JSON.parse(localStorage.getItem('sori.live')) || {}; } catch (e) { return {}; } };
const saveLive = (value) => { try { localStorage.setItem('sori.live', JSON.stringify({ ...loadLive(), ...value })); } catch (e) { /* private mode: not remembered */ } };
const pickDevice = (devices, wanted) => (devices.some((d) => d.id === wanted) ? wanted : (devices[0] ? devices[0].id : ''));
const errorText = (err) => err.message || String(err);
```

- [ ] **Step 3: Chooser** — signature `({ open, job, devices, onClose, startPolling, openNote })`. State: `device` init `''`; add `const [source, setSource] = React.useState('mic');`. In the open-reset effect add `setSource(loadLive().source || 'mic');`. New effect:
```jsx
  React.useEffect(() => {
    if (open && devices) setDevice((current) => pickDevice(devices, current || loadLive().device));
  }, [open, devices]);
```
`pickFile`: first line inside the `.then((path) => {` after the `!path` check: `saveLive({ device });`.
`goLive` mics success: `(list) => { setMics(list); const saved = loadLive().mic; setMic(list.includes(saved) ? saved : (list[0] ?? '')); },` (keep the existing comment).
`startRecording`:
```jsx
  const startRecording = () => {
    setErrorMsg('');
    saveLive({ device, mic, source });
    window.SoriBridge.startLive(source === 'system' ? '' : mic, device, source).then(
      ({ note_id }) => { onClose(); startPolling(); openNote(note_id); },
      (err) => setErrorMsg(errorText(err)),
    );
  };
```
Device select:
```jsx
          <select value={device} disabled={!devices} onChange={(e) => setDevice(e.target.value)}>
            {(devices || []).map((d) => <option key={d.id} value={d.id}>{d.label}</option>)}
          </select>
```
Choose buttons: `disabled={busy || !device}`.
Mic step body becomes:
```jsx
          <div className="modal-mic">
            <label className="modal-field">
              <span>소리 입력</span>
              <select value={source} onChange={(e) => setSource(e.target.value)}>
                {SOURCES.map(([v, label]) => <option key={v} value={v}>{label}</option>)}
              </select>
            </label>
            {source !== 'system' && (mics == null ? (
              <div className="modal-hint">마이크 목록을 불러오는 중…</div>
            ) : mics.length === 0 ? (
              <div className="modal-hint">(existing no-mic text unchanged)</div>
            ) : (
              <select value={mic} onChange={(e) => setMic(e.target.value)}>
                {mics.map((m) => <option key={m} value={m}>{m}</option>)}
              </select>
            ))}
            {source !== 'mic' && <p className="modal-hint">회의 앱 소리를 그대로 받아씁니다. 스피커 볼륨과 관계없이 기록됩니다.</p>}
            <p className="modal-hint">(existing hint unchanged)</p>
            <button className="btn btn-primary" disabled={busy || !device || (source !== 'system' && (!mics || mics.length === 0))} onClick={startRecording}>녹음 시작</button>
          </div>
```

- [ ] **Step 4: Cancel UI.** Add above `Editor`:
```jsx
const CancelButton = () => {
  const [busy, setBusy] = React.useState(false);
  return (
    <button className="btn-cancel" disabled={busy} onClick={() => { setBusy(true); window.SoriBridge.cancelJob().catch(() => setBusy(false)); }}>
      {busy ? '취소 중…' : '취소'}
    </button>
  );
};
```
Editor job-status block:
```jsx
      {jobRunningHere && (
        <div className="job-status">
          <span className="job-stage">{job.stage}{job.op === 'transcribe' ? ` · ${job.percent.toFixed(1)}%` : ''}</span>
          {job.op === 'transcribe' && <CancelButton />}
        </div>
      )}
```
Add after `LivePill`:
```jsx
const JobPill = ({ job, queued }) => {
  if (!(job.state === 'running' && job.op === 'transcribe') && !queued) return null;
  return (
    <div className="live-pill job-pill">
      {job.state === 'running' && job.op === 'transcribe' ? (
        <React.Fragment>
          <span className="live-stage">{job.stage} · {job.percent.toFixed(1)}%</span>
          <CancelButton key={job.note_id} />
        </React.Fragment>
      ) : <span className="live-stage">전사 대기 중</span>}
      {queued > 0 && <span className="job-queue">대기 {queued}개</span>}
    </div>
  );
};

const SetupScreen = ({ job, onRetry }) => {
  const mine = job.op === 'setup';
  const failed = mine && job.state === 'error';
  const progress = (mine && job.progress) || [];
  return (
    <div className="setup-screen">
      <div className="setup-card" role="status" aria-live="polite">
        <h1 className="setup-title">모델을 내려받는 중… (약 4.5 GB, 처음 한 번)</h1>
        <p className="modal-hint">모델은 이 PC에만 저장되며, 이후 전사는 인터넷 없이 동작합니다. 중간에 닫아도 다음 실행 때 이어서 받습니다.</p>
        <ul className="setup-files">
          {(mine && job.ready ? job.ready : []).map((name) => <li key={name} className="setup-file setup-done">✓ {name}</li>)}
          {mine && job.state === 'running' && job.file && !(job.ready || []).includes(job.file) && (
            <li className="setup-file">
              <span className="setup-name">{job.file}</span>
              <progress max="100" value={job.percent || 0} />
              <span className="setup-size">{progress.length ? `${progress[1]} / ${progress[2]} MiB` : ''}</span>
            </li>
          )}
        </ul>
        {mine && job.state === 'running' && <div className="job-status"><span className="job-stage">{job.stage}</span></div>}
        {failed && <div className="modal-error">{job.error}</div>}
        {(failed || !mine) && <button className="btn btn-primary" onClick={onRetry}>{failed ? '다시 시도' : '내려받기 시작'}</button>}
      </div>
    </div>
  );
};
```

- [ ] **Step 5: App wiring.** New state + refs in `App` (after `job`):
```jsx
  const [devices, setDevices] = React.useState(null);
  const [setupNeeded, setSetupNeeded] = React.useState(false);
  const [dragging, setDragging] = React.useState(false);
  const [queue, setQueue] = React.useState([]);
  const jobRef = React.useRef(job);
  jobRef.current = job;
  const devicesRef = React.useRef(devices);
  devicesRef.current = devices;
```
Device loading + setup start (define before `startPolling` is used in effects; place after `startPolling`):
```jsx
  const loadDevices = () => window.SoriBridge.devices().then(
    (d) => { setDevices(d.devices); setSetupNeeded(!d.models_ready); return d; },
    (err) => { showError(errorText(err)); return null; },
  );
  const startSetup = () => window.SoriBridge.setup().then(
    () => startPolling(),
    (err) => { if (err.status === 409) startPolling(); else showError(errorText(err)); },
  );
  React.useEffect(() => {
    loadDevices().then((d) => { if (d && !d.models_ready) startSetup(); });
  }, []);
```
In `startPolling`'s `setJob` updater, inside the `if (j.state !== 'running' && (first || prev.state === 'running'))` block, add first line: `if (j.op === 'setup') loadDevices();` and change the error line to `if (j.state === 'error' && j.op !== 'setup') showError(j.error || '작업이 실패했습니다.');` (the setup screen shows its own error).
Drag & drop (effects):
```jsx
  React.useEffect(() => {
    window.SoriBridge.onDrag((type, payload) => {
      setDragging(type === 'enter' || type === 'over');
      if (type !== 'drop') return;
      const paths = payload.paths || [];
      const audio = paths.filter(window.SoriBridge.isAudio);
      if (audio.length) setQueue((q) => [...q, ...audio]);
      if (audio.length < paths.length) showError('오디오 파일만 전사할 수 있습니다.');
    });
  }, []);
  // Dropped files run one after another (one model job at a time). The job is marked running optimistically so
  // this effect never double-starts before the first poll lands; a 409 (another job) just waits for it to end.
  const startingRef = React.useRef(false);
  React.useEffect(() => {
    if (!queue.length || !devices || setupNeeded || job.state === 'running' || startingRef.current) return;
    startingRef.current = true;
    const path = queue[0];
    window.SoriBridge.transcribe(path, pickDevice(devices, loadLive().device)).then(
      ({ note_id }) => {
        startingRef.current = false;
        setQueue((q) => q.slice(1));
        setJob((prev) => ({ ...prev, state: 'running', op: 'transcribe', note_id, stage: '준비 중', percent: 0, text: '' }));
        startPolling();
        refresh();
      },
      (err) => {
        startingRef.current = false;
        if (err.status === 409) { startPolling(); return; }
        setQueue((q) => q.slice(1));
        showError(`${path.split(/[\\/]/).pop()}: ${errorText(err)}`);
      },
    );
  }, [queue, job.state, devices, setupNeeded]);
```
toggle-recording:
```jsx
  // Ctrl+Shift+R and the tray's 녹음 시작: stop a live recording, or start one with the last chooser choice.
  // ponytail: the LivePill's "마지막 구간 전사 중…" state only appears for its own button; lift `stopping` into App if needed.
  React.useEffect(() => {
    window.SoriBridge.onToggleRecording(() => {
      const current = jobRef.current;
      if (current.state === 'running') {
        if (current.op === 'listen') window.SoriBridge.stopLive().catch((err) => showError(errorText(err)));
        else showError('다른 전사 작업이 진행 중입니다. 끝난 뒤 다시 시작해 주세요.');
        return;
      }
      const list = devicesRef.current;
      if (!list || !list.length) return;
      const saved = loadLive();
      const source = saved.source || 'mic';
      const begin = (mic) => window.SoriBridge.startLive(mic, pickDevice(list, saved.device), source).then(
        ({ note_id }) => { setChooserOpen(false); startPolling(); openNote(note_id); refresh(); },
        (err) => showError(errorText(err)),
      );
      if (source === 'system') { begin(''); return; }
      window.SoriBridge.mics().then((mics) => {
        const mic = mics.includes(saved.mic) ? saved.mic : mics[0];
        if (mic) begin(mic); else showError('사용할 수 있는 마이크를 찾지 못했습니다.');
      }, (err) => showError(errorText(err)));
    });
  }, []);
```
Render: at the very top of `App`'s return, before the main layout:
```jsx
  if (setupNeeded) return <SetupScreen job={job} onRetry={startSetup} />;
```
(place this `if` after all hooks, right before `return (`). In the main layout pass `devices={devices}` to `<Chooser …>`, and after `<LivePill job={job} />` add:
```jsx
      {!openNoteId && <JobPill job={job} queued={queue.length} />}
      {dragging && (
        <div className="drop-overlay" aria-hidden="true">
          <div className="drop-hint">오디오 파일을 여기에 끌어 놓으세요</div>
        </div>
      )}
```

- [ ] **Step 6: tokens.css** — read the existing `.live-pill`, `.job-status`, `.btn`, `.modal-error` rules and colour tokens first; append rules using existing tokens only (no new colours except where a token for danger/red already exists — use it; if none exists, add one token `--danger` next to the other colour tokens in both themes):
```css
.job-status { display: flex; align-items: center; gap: 12px; }
.job-stage { flex: 1; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.btn-cancel { flex: none; border: 1px solid var(--danger); color: var(--danger); background: transparent; border-radius: 999px; padding: 4px 12px; font: inherit; cursor: pointer; }
.btn-cancel:hover:not(:disabled) { background: var(--danger); color: #fff; }
.btn-cancel:disabled { opacity: .6; cursor: default; }
.job-pill { bottom: 72px; }            /* sits above the live pill if both ever show */
.job-queue { flex: none; opacity: .75; }
.drop-overlay { position: fixed; inset: 0; z-index: 100; pointer-events: none; display: grid; place-items: center; background: color-mix(in srgb, var(--bg, #000) 70%, transparent); border: 3px dashed var(--accent, currentColor); }
.drop-hint { font-size: 20px; font-weight: 600; padding: 16px 24px; border-radius: 12px; background: var(--surface, #fff); }
.setup-screen { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
.setup-card { width: min(560px, 100%); display: grid; gap: 12px; }
.setup-title { font-size: 22px; margin: 0; }
.setup-files { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
.setup-file { display: grid; grid-template-columns: 1fr 160px auto; gap: 8px; align-items: center; font-variant-numeric: tabular-nums; }
.setup-done { grid-template-columns: 1fr; opacity: .7; }
.setup-name { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
```
`--danger`, `--bg`, `--accent`, `--surface` exist in `tokens.css :root` (drop the `, #…` fallbacks). `.job-status` already exists at line ~114 (`font-size: 12px; color: var(--text-secondary);`): add the flex properties to that rule instead of a second one. Check `.live-pill`'s positioning (line ~122) so `.job-pill` stacks correctly, and check whether a dark-theme block redefines tokens (then nothing else is needed).

- [ ] **Step 7: Build check** — `npm run build` → `dist ready` (Babel compiles app.jsx without errors).
- [ ] **Step 8: Python suites** → PASS (unchanged).
- [ ] **Step 9: Commit** `feat(ui): device list from /devices, live source, cancel, first-run download, drag & drop queue, toggle-recording`.

---

### Task 6: Tauri shell — SORIGUL_HOME, release python, tray, Ctrl+Shift+R

**Files:**
- Modify: `src-tauri/Cargo.toml`, `src-tauri/src/main.rs`

**Interfaces:**
- Consumes: `server.py` protocol (unchanged); frontend listens for event `toggle-recording` (payload `null`).
- Produces: env `SORIGUL_HOME` for the bridge; tray + shortcut emitting `toggle-recording`.

- [ ] **Step 1: Cargo.toml** dependencies:
```toml
tauri = { version = "2", features = ["tray-icon"] }
tauri-plugin-dialog = "2"
tauri-plugin-global-shortcut = "2"
```
- [ ] **Step 2: main.rs** — replace `spawn_bridge` head and `main`:
```rust
use std::path::PathBuf;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::TrayIconBuilder;
use tauri::{AppHandle, Emitter, Manager, RunEvent, WindowEvent};
use tauri_plugin_global_shortcut::{GlobalShortcutExt, ShortcutState};

/// (pythonw.exe, working dir with server.py, SORIGUL_HOME). Debug: the repo's .venv and data, so dev data keeps
/// working. Release: the embeddable Python bundled as the `python` resource (resource dir = the exe's dir on
/// Windows) and %LOCALAPPDATA%\Sorigul for models, library and the model lock.
fn bridge_paths() -> (PathBuf, PathBuf, PathBuf) {
    if cfg!(debug_assertions) {
        let root = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().to_path_buf();
        (root.join(".venv").join("Scripts").join("pythonw.exe"), root.clone(), root)
    } else {
        let python = std::env::current_exe().expect("no exe path").parent().unwrap().join("python");
        let home = PathBuf::from(std::env::var_os("LOCALAPPDATA").expect("LOCALAPPDATA is not set")).join("Sorigul");
        (python.join("pythonw.exe"), python, home)
    }
}

fn spawn_bridge() -> Bridge {
    let (python, cwd, home) = bridge_paths();
    std::fs::create_dir_all(&home).expect("cannot create the data folder");
    let mut child = Command::new(&python)
        .arg("server.py")
        .current_dir(&cwd)
        .env("SORIGUL_HOME", &home)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap_or_else(|e| panic!("cannot start {}: {e} (dev: run setup.cmd first)", python.display()));
    (rest of the existing function unchanged)
}

fn show_main(app: &AppHandle) {
    if let Some(window) = app.get_webview_window("main") {
        let _ = window.unminimize();
        let _ = window.show();
        let _ = window.set_focus();
    }
}

fn main() {
    let app = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        let _ = app.emit("toggle-recording", ());
                    }
                })
                .build(),
        )
        .manage(spawn_bridge())
        .invoke_handler(tauri::generate_handler![bridge])
        .setup(|app| {
            // ponytail: if another program owns Ctrl+Shift+R the shortcut is silently unavailable (tray still works).
            if let Err(error) = app.global_shortcut().register("ctrl+shift+r") {
                eprintln!("Ctrl+Shift+R unavailable: {error}");
            }
            let open = MenuItem::with_id(app, "open", "열기", true, None::<&str>)?;
            let record = MenuItem::with_id(app, "record", "녹음 시작", true, None::<&str>)?;
            let quit = MenuItem::with_id(app, "quit", "종료", true, None::<&str>)?;
            TrayIconBuilder::with_id("main")
                .icon(app.default_window_icon().unwrap().clone())
                .tooltip("소리글")
                .menu(&Menu::with_items(app, &[&open, &record, &quit])?)
                .on_menu_event(|app, event| match event.id().as_ref() {
                    "open" => show_main(app),
                    "record" => {
                        let _ = app.emit("toggle-recording", ());
                    }
                    "quit" => app.exit(0),
                    _ => {}
                })
                .build(app)?;
            Ok(())
        })
        .on_window_event(... existing, unchanged ...)
        .build(tauri::generate_context!())
        .expect("failed to build tauri app");
    app.run(... existing, unchanged ...);
}
```
Remove the old `// ponytail: dev layout only …` comment (now resolved). Keep `stop_bridge` and the window-close handler exactly as they are.
- [ ] **Step 3: Build** `cd src-tauri; cargo build` → compiles with no errors (warnings OK). If the `window.title` main label is not `main`, check `tauri.conf.json` — the default label for the first config window is `main`.
- [ ] **Step 4: Dev smoke** — `npm run tauri:dev`: app opens with the dashboard (models already present on this machine), tray icon "소리글" visible, Ctrl+Shift+R starts a live note, second press stops it. Close the app.
- [ ] **Step 5: Commit** `feat(shell): SORIGUL_HOME + bundled python path, tray (열기/녹음 시작/종료), Ctrl+Shift+R`.

---

### Task 7: Python bundle script, per-arch Tauri config, npm scripts, docs

**Files:**
- Create: `scripts/build-python-bundle.ps1`, `src-tauri/tauri.arm64.conf.json`, `src-tauri/tauri.x64.conf.json`
- Modify: `package.json`, `.gitignore`, `CLAUDE.md`

**Interfaces:**
- Consumes: `requirements-arm64.txt`, `requirements-whisper-gpu.txt`, `requirements-x64.txt`, `tools/ffmpeg.exe` (from setup), `.venv\Scripts\python.exe` (host pip).
- Produces: `src-tauri/python-<arch>/` layout (`pythonw.exe`, `python312._pth`, backend .py, `tools/ffmpeg.exe`, `Lib/site-packages`, arm64: `Lib/gpu-packages`); installers at `src-tauri/target/<triple>/release/bundle/nsis/Sorigul_0.1.0_<arm64|x64>-setup.exe`.

- [ ] **Step 1: `scripts/build-python-bundle.ps1`:**
```powershell
# Builds src-tauri\python-<arch>\: python.org embeddable CPython, backend .py files, ffmpeg, app-local VC++ runtime,
# and wheels for that arch (pip download --platform, no PyInstaller). Run from any directory.
param([Parameter(Mandatory = $true)][ValidateSet('arm64', 'x64')][string]$Arch)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root "src-tauri\python-$Arch"
$cache = Join-Path $root "src-tauri\target\python-cache"
$version = '3.12.10'
$platform = @{ arm64 = 'win_arm64'; x64 = 'win_amd64' }[$Arch]
$embed = @{ arm64 = 'arm64'; x64 = 'amd64' }[$Arch]
$hostPython = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $hostPython)) { throw 'Run setup.cmd first (the build uses .venv''s pip).' }
if (-not (Test-Path (Join-Path $root 'tools\ffmpeg.exe'))) { throw 'tools\ffmpeg.exe is missing: run setup.cmd first.' }

New-Item -ItemType Directory -Force $cache | Out-Null
if (Test-Path $out) { Remove-Item -Recurse -Force $out }
New-Item -ItemType Directory -Force $out | Out-Null

$zip = Join-Path $cache "python-$version-embed-$embed.zip"
if (-not (Test-Path $zip)) {
    Invoke-WebRequest "https://www.python.org/ftp/python/$version/python-$version-embed-$embed.zip" -OutFile $zip
}
Expand-Archive -LiteralPath $zip -DestinationPath $out
# '.' puts the backend modules on sys.path (an embeddable build ignores the script dir and PYTHONPATH).
[IO.File]::WriteAllText((Join-Path $out 'python312._pth'), "python312.zip`r`n.`r`nLib\site-packages`r`n")

function Add-Packages([string]$requirements, [string]$target) {
    $name = [IO.Path]::GetFileNameWithoutExtension($requirements)
    $wheels = Join-Path $cache "wheels-$Arch-$name"
    $common = @('--only-binary=:all:', '--platform', $platform, '--python-version', '3.12', '--implementation', 'cp')
    & $hostPython -m pip download @common -r (Join-Path $root $requirements) -d $wheels --quiet
    if ($LASTEXITCODE -ne 0) { throw "pip download failed for $requirements" }
    & $hostPython -m pip install @common --no-index --find-links $wheels --target $target --no-compile --quiet -r (Join-Path $root $requirements)
    if ($LASTEXITCODE -ne 0) { throw "pip install --target failed for $requirements" }
    Remove-Item -Recurse -Force (Join-Path $target 'bin') -ErrorAction SilentlyContinue
}
Add-Packages "requirements-$Arch.txt" (Join-Path $out 'Lib\site-packages')
if ($Arch -eq 'arm64') { Add-Packages 'requirements-whisper-gpu.txt' (Join-Path $out 'Lib\gpu-packages') }

foreach ($file in 'server.py', 'engine.py', 'jobs.py', 'diarize.py', 'library.py', 'setup_assets.py', 'loopback.py') {
    Copy-Item (Join-Path $root $file) $out
}
New-Item -ItemType Directory (Join-Path $out 'tools') | Out-Null
Copy-Item (Join-Path $root 'tools\ffmpeg.exe'), (Join-Path $root 'tools\LICENSE') (Join-Path $out 'tools')

# onnxruntime needs msvcp140 / vcruntime140_1; ship them app-locally instead of requiring the VC++ redistributable.
$vs = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -latest -property installationPath
$crt = Get-ChildItem "$vs\VC\Redist\MSVC\*\$Arch\Microsoft.VC*.CRT" -Directory | Sort-Object FullName | Select-Object -Last 1
if (-not $crt) { throw "No $Arch VC++ runtime under $vs\VC\Redist\MSVC" }
Copy-Item (Join-Path $crt.FullName 'msvcp140*.dll'), (Join-Path $crt.FullName 'vcruntime140*.dll') $out -Force

$bytes = (Get-ChildItem $out -Recurse -File | Measure-Object Length -Sum).Sum
foreach ($dir in 'Lib\site-packages', 'Lib\gpu-packages') {
    $path = Join-Path $out $dir
    if (Test-Path $path) { '{0,-18} {1,8:N0} MB' -f $dir, ((Get-ChildItem $path -Recurse -File | Measure-Object Length -Sum).Sum / 1MB) }
}
'python-{0} total    {1,8:N0} MB' -f $Arch, ($bytes / 1MB)
```
- [ ] **Step 2: configs** — `src-tauri/tauri.arm64.conf.json`: `{ "bundle": { "resources": { "python-arm64/": "python/" } } }`; `src-tauri/tauri.x64.conf.json`: `{ "bundle": { "resources": { "python-x64/": "python/" } } }`.
- [ ] **Step 3: package.json scripts** add:
```json
    "bundle:python": "powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-python-bundle.ps1",
    "tauri:build:arm64": "npm run bundle:python -- arm64 && tauri build --target aarch64-pc-windows-msvc --bundles nsis --config src-tauri/tauri.arm64.conf.json",
    "tauri:build:x64": "npm run bundle:python -- x64 && tauri build --target x86_64-pc-windows-msvc --bundles nsis --config src-tauri/tauri.x64.conf.json"
```
(Remove nothing.) If `npm run bundle:python -- arm64` does not forward the argument to the `-File` script, inline the full powershell command in both build scripts instead.
- [ ] **Step 4: .gitignore** add `src-tauri/python-*/`.
- [ ] **Step 5: Run** `npm run bundle:python -- arm64` → prints sizes; check `src-tauri\python-arm64\python.exe -c "import server, engine, jobs, loopback, onnxruntime; print(onnxruntime.get_available_providers())"` lists `QNNExecutionProvider`; and `src-tauri\python-arm64\python.exe -c "import sys; sys.path=[p for p in sys.path if not p.endswith('site-packages')]+[r'src-tauri\python-arm64\Lib\gpu-packages']; import onnxruntime, onnxruntime_qnn; print(onnxruntime.__version__)"` → `1.30.0`. Record sizes.
- [ ] **Step 6: CLAUDE.md** — rewrite to:
```markdown
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

Output: `src-tauri\target\<triple>\release\bundle\nsis\Sorigul_0.1.0_<arch>-setup.exe`. The installed app keeps
models, library and the model lock in `%LOCALAPPDATA%\Sorigul` (`SORIGUL_HOME`) and downloads models on first run.
```
(Update the ARM64-only wording if Task 1 changed setup text.)
- [ ] **Step 7: Commit** `build: embeddable python bundle script, per-arch NSIS targets, docs`.

---

### Task 8: Build installers + verification (controller, not a subagent)

- [ ] `npm run tauri:build:arm64` → installer path + size.
- [ ] `npm run tauri:build:x64` → installer path + size (fix cross-build issues if any).
- [ ] x64 emulated smoke: `$env:SORIGUL_HOME=$PWD; src-tauri\python-x64\python.exe -c "..."` loads `WhisperCPU` and transcribes a short file; also report `openvino_device()` under emulation.
- [ ] Install arm64 installer (`/S /D=<clean dir>`), temporarily point first run at a fresh `%LOCALAPPDATA%\Sorigul` (move an existing one aside or copy models to exercise the skip path), launch, and verify: first-run screen, file transcription, 10 s live (마이크), 시스템 소리 live, cancel, drag & drop (2 files), Ctrl+Shift+R, tray 열기/녹음 시작/종료, no `pythonw`/`server.py` left after quit.
- [ ] All four Python suites + loopback check output captured.
