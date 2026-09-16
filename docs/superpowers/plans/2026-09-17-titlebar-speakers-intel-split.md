# 소리글 title bar / 화자 분리 / Intel split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Frameless window with note-taking's caption buttons, a 화자 분리 toggle for file transcription, Intel GPU/NPU as separate devices, and the remaining real bugs (mixed-source label, tray label, x64-under-emulation arch, double launch).

**Architecture:** Python bridge (`server.py`) + one model worker per job (`jobs.py`, `engine.py`); React UMD frontend in one `app.jsx` + `bridge.js` + `tokens.css`; Tauri 2.11 shell in `src-tauri/src/main.rs`.

**Tech Stack:** Python 3.12 stdlib + onnxruntime/openvino (already installed), React 18 UMD, Tauri 2.11 (Rust std only for the new bits).

Spec: `docs/superpowers/specs/2026-09-17-titlebar-speakers-intel-split-design.md`.

## Global Constraints

- Repo `C:\Users\choho\sori-gul`, branch `feat/installers`. `C:\Users\choho\note-taking` is READ-ONLY. Never touch `C:\Users\choho\audio2text`.
- Keep every existing behaviour and Korean label. New labels exactly: "화자 분리", "인텔 GPU (OpenVINO)", "인텔 NPU (OpenVINO)", "⏹ 녹음 마치기" (tray while recording), "마이크 + 시스템 소리" (live stage for the mixed source), caption button labels "최소화" / "최대화" / "이전 크기로" / "닫기".
- No new dependencies (Python, npm, Rust crates). No bundler, state library, settings screen, i18n, theme switcher. Nothing from note-taking's liquid-glass, theme.js, i18n or clay-primitives.
- Reuse, do not rewrite. Fewest files. One `ponytail:` comment per deliberate shortcut (name the ceiling and the upgrade path).
- Tests: `.\.venv\Scripts\python.exe -m unittest tests.test_engine tests.test_diarize tests.test_library tests.test_server` must pass after every task (baseline 49 OK). Tests added on this branch (DeviceTests, LayoutTests, SetupAssetTests, ServerTests) may be updated for the new API; tests that existed before the branch (AudioTests, LiveTests, DiarizeTests, LibraryTests except the new concurrency test) must not change.
- Do NOT run `npm run tauri:build:*` (the controller builds at the end).
- Commit after each task; message ends with `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.

## File map

| File | Change |
|---|---|
| `engine.py` | `openvino_kinds()` replaces `openvino_device()`; `WhisperCPU(ov_device=None)`; `load_whisper` ids `cpu`/`intel-gpu`/`intel-npu`; mixed-source live label |
| `server.py` | `ARM64` from `sysconfig`; `probe_devices` lists `intel-gpu`/`intel-npu`; `LABELS`; `/transcribe` `speakers` |
| `jobs.py`, `setup_assets.py` | `ARM64` from `sysconfig` |
| `tests/test_engine.py`, `tests/test_server.py` | updated/new tests |
| `src-tauri/tauri.conf.json`, `src-tauri/capabilities/default.json` | `decorations: false`, window permissions |
| `src-tauri/src/main.rs` | `set_recording` command (tray label), single-instance lock + focus the running window |
| `app.jsx`, `tokens.css`, `bridge.js`, `.gitignore` | caption buttons + drag regions, 화자 분리 checkbox, `setRecording` |

---

### Task 1: Backend — Intel GPU/NPU split, interpreter arch, `speakers`, mixed-source label

**Files:** Modify `engine.py`, `server.py`, `jobs.py`, `setup_assets.py`, `tests/test_engine.py`, `tests/test_server.py`.

**Interfaces:**
- Produces: `engine.openvino_kinds(available=None) -> set[str]`; `engine.WhisperCPU(emit, cancel, model_dir=None, profile=False, ov_device=None)` with `ov_device in (None, "GPU", "NPU")`; `engine.load_whisper(device, emit, cancel, **options)` accepting `npu|gpu|cpu|intel-gpu|intel-npu`; `server.ARM64`, `jobs.ARM64`, `setup_assets.ARM64` (bool); `server.LABELS` with keys `npu, gpu, intel-gpu, intel-npu, cpu`; `POST /transcribe {"path", "device", "speakers": bool = true}`; job payload `"speakers": bool`.

- [ ] **Step 1: Update/add tests.**

In `tests/test_engine.py`:

(a) `LayoutTests.test_worker_python_uses_venvs_in_dev_and_package_dirs_in_the_bundle`: replace the `{"device": "intel"}` payload with `{"device": "intel-gpu"}` and replace the two `patch("jobs.platform.machine", return_value="ARM64"/"AMD64")` context managers with `patch("jobs.ARM64", True)` / `patch("jobs.ARM64", False)`.

(b) `SetupAssetTests.test_required_files_include_the_npu_bundle_only_on_arm64`: replace `patch("setup_assets.platform.machine", return_value="AMD64")` with `patch("setup_assets.ARM64", False)` and the ARM64 one with `patch("setup_assets.ARM64", True)`.

(c) `DeviceTests`: change the helper signature to `def load(self, ov_device=None, available=("CPU", "GPU.0")):` and its construction call to `WhisperCPU(..., model_dir=folder, ov_device=ov_device)`. `test_cpu_device_runs_both_sessions_on_the_cpu_without_qnn` calls `self.load()`. Replace `test_intel_device_puts_the_encoder_on_openvino_gpu`, `test_openvino_device_prefers_gpu_then_npu_then_cpu` and `test_load_whisper_routes_cpu_and_intel` with:

```python
    def test_intel_gpu_puts_the_encoder_on_openvino_gpu_with_its_own_cache(self):
        worker, created, stages = self.load(ov_device="GPU")
        self.assertEqual(created[0].providers,
                         [("OpenVINOExecutionProvider", {"device_type": "GPU",
                                                        "cache_dir": str(ROOT / "models" / "openvino-cache" / "GPU")}),
                          "CPUExecutionProvider"])
        self.assertEqual(created[1].providers, ["CPUExecutionProvider"])
        self.assertIn(("ready", "인텔 GPU (OpenVINO) · CPU (decoder)"), stages)

    def test_intel_npu_puts_the_encoder_on_openvino_npu_with_its_own_cache(self):
        # ponytail: mocked session only — the NPU path is untested on hardware.
        worker, created, stages = self.load(ov_device="NPU", available=("CPU", "NPU"))
        self.assertEqual(created[0].providers,
                         [("OpenVINOExecutionProvider", {"device_type": "NPU",
                                                        "cache_dir": str(ROOT / "models" / "openvino-cache" / "NPU")}),
                          "CPUExecutionProvider"])
        self.assertIn(("ready", "인텔 NPU (OpenVINO) · CPU (decoder)"), stages)

    def test_openvino_kinds_strips_device_indexes(self):
        from engine import openvino_kinds
        self.assertEqual(openvino_kinds(["CPU", "NPU", "GPU.0", "GPU.1"]), {"CPU", "NPU", "GPU"})
        self.assertEqual(openvino_kinds([]), set())

    def test_load_whisper_routes_cpu_and_both_intel_devices(self):
        import engine
        with patch("engine.WhisperCPU", side_effect=lambda *a, **k: k):
            self.assertEqual(engine.load_whisper("cpu", None, None), {})
            self.assertEqual(engine.load_whisper("intel-gpu", None, None), {"ov_device": "GPU"})
            self.assertEqual(engine.load_whisper("intel-npu", None, None), {"ov_device": "NPU"})
        for gone in ("intel", "tpu"):
            with self.assertRaises(ValueError):
                engine.load_whisper(gone, None, None)

    def test_mixed_source_is_labelled_as_mic_plus_system_sound(self):
        import io
        class Producer:
            stdout, stderr, code = io.BytesIO(noise(3).tobytes()), io.BytesIO(b""), None
            def poll(self):
                return self.code
            def terminate(self):
                self.code = 0
            kill = terminate
            def wait(self):
                return 0
        worker = WhisperNPU.__new__(WhisperNPU)
        worker.cancel, stop = threading.Event(), threading.Event()
        stages = []
        worker.emit = lambda kind, value: stages.append(value)
        worker.infer = lambda audio, preview: ("말", False)
        stop.set()
        with patch("engine.subprocess.Popen", return_value=Producer()):
            worker.listen(["py", "loopback.py", "--mic", "Mic"], stop)
        self.assertIn("🎙 녹음 중 · 마이크 + 시스템 소리", stages)
```

In `tests/test_server.py`, below the imports add `REAL_PROBE = server.probe_devices  # setUp replaces it with a mock` and add to `ServerTests`:

```python
    def test_x64_devices_follow_what_openvino_reports(self):
        import sys
        from types import ModuleType, SimpleNamespace
        cases = [(["CPU", "GPU.0"], ["intel-gpu", "cpu"]),
                 (["CPU", "NPU"], ["intel-npu", "cpu"]),
                 (["CPU", "GPU.0", "NPU"], ["intel-gpu", "intel-npu", "cpu"]),
                 (["CPU"], ["cpu"])]
        for available, expected in cases:
            fake = ModuleType("openvino")
            fake.Core = lambda devices=available: SimpleNamespace(available_devices=list(devices))
            with self.subTest(available=available), patch("server.ARM64", False), \
                    patch.dict(sys.modules, {"openvino": fake}):
                self.assertEqual(REAL_PROBE.__wrapped__(), expected)
        with patch("server.ARM64", False), patch.dict(sys.modules, {"openvino": None}):  # no OpenVINO runtime
            self.assertEqual(REAL_PROBE.__wrapped__(), ["cpu"])
        with patch("server.probe_devices", return_value=["intel-gpu", "intel-npu", "cpu"]), \
                patch("server.models_ready", return_value=True):
            status, body = self.request("GET", "/devices")
        self.assertEqual(body["devices"], [{"id": "intel-gpu", "label": "인텔 GPU (OpenVINO)"},
                                           {"id": "intel-npu", "label": "인텔 NPU (OpenVINO)"},
                                           {"id": "cpu", "label": "CPU"}])

    def test_transcribe_passes_the_speakers_choice(self):
        self.assertEqual(self.request("POST", "/transcribe", {"path": self.audio(), "speakers": "yes"})[0], 400)
        self.request("POST", "/transcribe", {"path": self.audio(), "speakers": False})
        self.wait_for("running")
        self.assertIs(self.calls[0][1]["speakers"], False)
        self.release.set()
        self.wait_for("done")
        self.release.clear()
        self.request("POST", "/transcribe", {"path": self.audio()})
        self.wait_for("running")
        self.assertIs(self.calls[1][1]["speakers"], True)
```

- [ ] **Step 2: Run** `.\.venv\Scripts\python.exe -m unittest tests.test_engine tests.test_server` → the new/changed tests FAIL (missing `openvino_kinds`, `ARM64`, `ov_device`, …).

- [ ] **Step 3: engine.py.**

Replace `openvino_device` with:
```python
def openvino_kinds(available=None):
    """Device kinds OpenVINO reports on this PC ('GPU.0' counts as GPU)."""
    if available is None:
        import openvino
        available = openvino.Core().available_devices
    return {name.split(".")[0] for name in available}
```
`WhisperCPU`: docstring → "both sessions on the CPU ('cpu'), or the encoder on Intel graphics / NPU through the OpenVINO execution provider ('intel-gpu' / 'intel-npu')."; signature `def __init__(self, emit, cancel, model_dir=None, profile=False, ov_device=None):`; replace `if intel:` with `if ov_device:`; drop `target = openvino_device()` and use `ov_device` where `target` was; the cache becomes
```python
            cache = ROOT / "models" / "openvino-cache" / ov_device  # compiled encoder blob per device: only the first job compiles
```
label `f"인텔 {ov_device} (OpenVINO) · CPU (decoder)"`; the two later `intel` checks become `ov_device` (the stage text "(처음은 수 분)" and the "OpenVINOExecutionProvider not in get_providers()" guard).

`load_whisper`:
```python
def load_whisper(device, emit, cancel, **options):
    """'npu' = pre-compiled Hexagon bundle; 'gpu' = standard ONNX export on the Adreno GPU via QNN;
    'cpu' = the same export on the CPU; 'intel-gpu' / 'intel-npu' = its encoder on Intel graphics / NPU (OpenVINO)."""
    if device == "gpu":
        return WhisperGPU(emit, cancel, **options)
    if device == "npu":
        return WhisperNPU(emit, cancel, **options)
    if device == "cpu":
        return WhisperCPU(emit, cancel, **options)
    if device in ("intel-gpu", "intel-npu"):
        return WhisperCPU(emit, cancel, ov_device=device.split("-")[1].upper(), **options)
    raise ValueError("device must be 'npu', 'gpu', 'cpu', 'intel-gpu' or 'intel-npu'")
```
CLI `choices=("npu", "gpu", "cpu", "intel-gpu", "intel-npu")`.

In `listen`:
```python
        label = source if isinstance(source, str) else ("마이크 + 시스템 소리" if "--mic" in source else "시스템 소리")
        kind = "마이크" if isinstance(source, str) else label
```

- [ ] **Step 4: interpreter arch.** In `jobs.py`, `setup_assets.py`, `server.py`: replace `import platform` with `import sysconfig` (keep alphabetical import order) and add after the other module constants:
```python
# The interpreter's own architecture: an x64 build running under emulation on an ARM64 PC reports machine() == "ARM64".
ARM64 = sysconfig.get_platform() == "win-arm64"
```
Replace every `platform.machine() == "ARM64"` in these three files with `ARM64`. Leave `engine.py`'s two `platform.machine()` checks (they guard the QNN classes, which only the arm64 bundle can load anyway).

- [ ] **Step 5: server.py.**
```python
LABELS = {"npu": "NPU (Hexagon)", "gpu": "GPU (Adreno)", "intel-gpu": "인텔 GPU (OpenVINO)",
          "intel-npu": "인텔 NPU (OpenVINO)", "cpu": "CPU"}
```
In `probe_devices`, the non-ARM64 branch becomes:
```python
    else:
        try:
            from engine import openvino_kinds
            kinds = openvino_kinds()
        except Exception:
            kinds = set()  # no OpenVINO runtime: CPU only
        ids += [f"intel-{kind.lower()}" for kind in ("GPU", "NPU") if kind in kinds]
```
In `/transcribe`, after `selected = device(body)`:
```python
    speakers = body.get("speakers", True)
    if not isinstance(speakers, bool):
        raise HttpError(400, "speakers must be true or false")
```
and pass `"speakers": speakers` instead of `"speakers": True`.

- [ ] **Step 6: Run all four suites** → PASS (expect 53 tests).
- [ ] **Step 7: Commit** `feat: intel-gpu / intel-npu devices, 화자 분리 flag on /transcribe, interpreter arch, mixed-source label`.

---

### Task 2: Shell — frameless window, caption buttons, drag regions, tray label command, single instance

**Files:** Modify `src-tauri/tauri.conf.json`, `src-tauri/capabilities/default.json`, `src-tauri/src/main.rs`, `app.jsx`, `tokens.css`, `bridge.js`, `.gitignore`.

**Interfaces:**
- Consumes: Tauri JS global `window.__TAURI__.window.getCurrentWindow()` (`minimize`, `toggleMaximize`, `close`, `isMaximized`, `onResized`), `window.__TAURI__.core.invoke`.
- Produces: Rust command `set_recording(recording: bool)`; `window.SoriBridge.setRecording(recording)`; React `WindowCaption` component (no props); CSS classes `.caption`, `.caption-btn`, `.caption-min`, `.caption-max`, `.caption-close`, `.caption-disc`, `.caption-reserve`, `.drag-spacer`, `.setup-drag`.

- [ ] **Step 1: config.** `tauri.conf.json` window object gains `"decorations": false`. `capabilities/default.json` permissions become:
```json
  "permissions": [
    "core:default",
    "dialog:default",
    "core:window:allow-minimize",
    "core:window:allow-toggle-maximize",
    "core:window:allow-close",
    "core:window:allow-is-maximized",
    "core:window:allow-start-dragging",
    "core:window:allow-internal-toggle-maximize"
  ]
```

- [ ] **Step 2: main.rs.**

Add below `bridge`:
```rust
struct RecordItem(MenuItem<tauri::Wry>);

/// The tray's record item follows the app: the frontend reports whenever a live recording starts or ends.
#[tauri::command]
fn set_recording(recording: bool, item: tauri::State<RecordItem>) {
    let _ = item.0.set_text(if recording { "⏹ 녹음 마치기" } else { "녹음 시작" });
}

/// One app per data folder. A second launch (a double double-click) used to come up without a window but with its
/// own tray icon, bridge and hotkey. The OS drops the lock when the process ends, crash included.
fn lock_instance(home: &std::path::Path) -> Option<std::fs::File> {
    use std::os::windows::fs::OpenOptionsExt;
    std::fs::OpenOptions::new().write(true).create(true).share_mode(0).open(home.join("app.lock")).ok()
}

#[link(name = "user32")]
extern "system" {
    fn FindWindowW(class: *const u16, title: *const u16) -> isize;
    fn ShowWindow(window: isize, command: i32) -> i32;
    fn SetForegroundWindow(window: isize) -> i32;
}

/// Brings the already running instance's window to the front.
// ponytail: found by its title "소리글"; another top-level window with exactly that title would be picked instead —
// switch to a named pipe / tauri-plugin-single-instance if that ever happens.
fn focus_running_instance() {
    let title: Vec<u16> = "소리글".encode_utf16().chain(Some(0)).collect();
    unsafe {
        let window = FindWindowW(std::ptr::null(), title.as_ptr());
        if window != 0 {
            ShowWindow(window, 9); // SW_RESTORE
            SetForegroundWindow(window);
        }
    }
}
```
Change `spawn_bridge` to take the paths: `fn spawn_bridge(python: PathBuf, cwd: PathBuf, home: PathBuf) -> Bridge {` and delete its first two lines (`let (python, cwd, home) = bridge_paths();` and `create_dir_all`). In `main`, before the builder:
```rust
    let (python, cwd, home) = bridge_paths();
    std::fs::create_dir_all(&home).expect("cannot create the data folder");
    let Some(_instance) = lock_instance(&home) else {
        focus_running_instance();
        return;
    };
```
(`_instance` lives until `main` ends; `app.run` exits the process, which releases it.) Builder: `.manage(spawn_bridge(python, cwd, home))`, `.invoke_handler(tauri::generate_handler![bridge, set_recording])`; in `setup`, after creating `record`: `app.manage(RecordItem(record.clone()));`. `.gitignore`: add `app.lock`.

Build: `cd src-tauri; cargo build` → no errors. If `MenuItem::set_text` or the `extern` block needs adjusting for tauri 2.11, check the crate source in `~/.cargo/registry/src/*/tauri-2.11.0/src/menu/normal.rs` and keep the behaviour.

- [ ] **Step 3: bridge.js** — add to the frozen object:
```js
    setRecording: (recording) => tauri.core.invoke('set_recording', { recording }).catch(() => {}),
```

- [ ] **Step 4: app.jsx caption component.** Add above `TopBar`:
```jsx
// The window has no OS frame (tauri.conf.json decorations: false). Its caption buttons are ported from note-taking's
// window-caption-buttons.jsx: the same glyphs, 40 px columns the height of the top bar, a 26 px hover disc (yellow /
// green / red), blur after a click. Portalled to the top-right corner above every overlay, so no modal or screen can
// leave the window without a close button.
const currentWindow = () => {
  try { return window.__TAURI__.window.getCurrentWindow(); } catch (e) { return null; }
};
// Inline SVG, not Segoe Fluent Icons: that font is missing on some Windows installs and would render as tofu.
const MinimizeGlyph = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" focusable="false">
    <path d="M0 5h10" stroke="currentColor" strokeWidth="1" fill="none" shapeRendering="crispEdges" />
  </svg>
);
const MaximizeGlyph = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" focusable="false">
    <rect x="0.5" y="0.5" width="9" height="9" rx="1" stroke="currentColor" strokeWidth="1" fill="none" shapeRendering="crispEdges" />
  </svg>
);
const RestoreGlyph = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" focusable="false">
    <path d="M2.5 2.5V1.5a1 1 0 0 1 1-1h5a1 1 0 0 1 1 1v5a1 1 0 0 1-1 1h-1" stroke="currentColor" strokeWidth="1" fill="none" />
    <rect x="0.5" y="2.5" width="7" height="7" rx="1" stroke="currentColor" strokeWidth="1" fill="none" shapeRendering="crispEdges" />
  </svg>
);
const CloseGlyph = () => (
  <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" focusable="false">
    <path d="M0.5 0.5l9 9M9.5 0.5l-9 9" stroke="currentColor" strokeWidth="1.1" fill="none" />
  </svg>
);

const WindowCaption = () => {
  const [maximized, setMaximized] = React.useState(false);
  // The glyph follows the window, not a click counter: Aero Snap, a double-click on the drag region or the taskbar
  // can maximize it too.
  React.useEffect(() => {
    const win = currentWindow();
    if (!win) return undefined;
    let disposed = false;
    let unlisten = null;
    const sync = () => win.isMaximized().then((value) => { if (!disposed) setMaximized(value); }, () => {});
    sync();
    win.onResized(sync).then((remove) => { if (disposed) remove(); else unlisten = remove; }, () => {});
    return () => { disposed = true; if (unlisten) unlisten(); };
  }, []);
  const run = (method) => (event) => {
    event.currentTarget.blur(); // OS caption buttons never keep focus; keyboard users still get :focus-visible
    const win = currentWindow();
    if (win) win[method]().catch((error) => console.warn(`window ${method} failed`, error));
  };
  const button = (className, label, method, glyph) => (
    <button type="button" className={`caption-btn ${className}`} title={label} aria-label={label} onClick={run(method)}>
      <span className="caption-disc" aria-hidden="true">{glyph}</span>
    </button>
  );
  return ReactDOM.createPortal(
    <div className="caption">
      {button('caption-min', '최소화', 'minimize', <MinimizeGlyph />)}
      {button('caption-max', maximized ? '이전 크기로' : '최대화', 'toggleMaximize', maximized ? <RestoreGlyph /> : <MaximizeGlyph />)}
      {/* close(), never destroy(): CloseRequested finishes a live recording and keeps its WAV before the app exits. */}
      {button('caption-close', '닫기', 'close', <CloseGlyph />)}
    </div>,
    document.body,
  );
};
```

- [ ] **Step 5: app.jsx wiring.**
TopBar: `<header className="topbar" data-tauri-drag-region>` and `<div className="brand" data-tauri-drag-region>소리글</div>`; after the `?` icon button, before `</header>`:
```jsx
      {/* Empty drag area, then room for the fixed caption buttons (Tauri drags only on direct clicks on these). */}
      <div className="drag-spacer" data-tauri-drag-region />
      <div className="caption-reserve" aria-hidden="true" />
```
SetupScreen: first child of `.setup-screen` becomes `<div className="setup-drag" data-tauri-drag-region />`.
App: the setup early return becomes
```jsx
  if (setupNeeded) return <React.Fragment><SetupScreen … unchanged props … /><WindowCaption /></React.Fragment>;
```
and add `<WindowCaption />` as the last child of the main `.app` div. Also, next to the other effects in App:
```jsx
  // The tray's 녹음 시작 item reads ⏹ 녹음 마치기 while a live recording runs.
  const recording = job.state === 'running' && job.op === 'listen';
  React.useEffect(() => { window.SoriBridge.setRecording(recording); }, [recording]);
```
(this `useEffect` must sit with the other hooks, before the setup early return).

- [ ] **Step 6: tokens.css** — `.topbar` gets `padding-right: 0;` (the reserve lines up with the fixed cluster); append:
```css
/* Window caption (frameless window): ported from note-taking's window-caption-buttons.jsx */
.caption { position: fixed; top: 0; right: 0; display: flex; align-items: center; z-index: 2147483000; }
.caption-btn { width: 40px; height: 56px; flex: none; border: none; padding: 0; margin: 0; background: transparent; color: var(--text-secondary); display: flex; align-items: center; justify-content: center; cursor: default; border-radius: 0; }
.caption-disc { width: 26px; height: 26px; border-radius: 50%; display: flex; align-items: center; justify-content: center; transition: background 120ms ease; }
.caption-btn:hover { color: rgba(0, 0, 0, 0.72); }
.caption-min:hover .caption-disc { background: #febc2e; }
.caption-max:hover .caption-disc { background: #28c840; }
.caption-close:hover { color: #ffffff; }
.caption-close:hover .caption-disc { background: #ff5f57; }
.caption-btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.caption-reserve { width: 120px; height: 56px; flex: none; }
.drag-spacer { flex: 1 1 24px; align-self: stretch; }
.setup-drag { position: fixed; top: 0; left: 0; right: 0; height: 56px; }
```
Check that `--text-secondary` and `--accent` exist in `:root` (they do in the current file); `@media (prefers-reduced-motion: reduce)` exists? If a reduced-motion block exists, add `.caption-disc { transition: none; }` to it.

- [ ] **Step 7: Verify** — `cd src-tauri; cargo build` OK; `npm run build` → `dist ready`; Python suites still pass. Then `npm run tauri:dev` in the background, wait for the window, and check without screenshots of the user's screen being required: `Get-Process sori-gul` has a `MainWindowTitle` of 소리글; launching `src-tauri\target\debug\sori-gul.exe` a second time exits within 2 s and leaves exactly one `sori-gul` and one `pythonw ... server.py`; close the app with `(Get-Process sori-gul).CloseMainWindow()` and confirm no `pythonw` running `server.py` remains. Record outputs.
- [ ] **Step 8: Commit** `feat(shell): frameless window with caption buttons and drag regions, tray label follows recording, single instance`.

---

### Task 3: Frontend — 화자 분리 checkbox

**Files:** Modify `app.jsx`, `bridge.js`, `tokens.css`.

**Interfaces:**
- Consumes: `POST /transcribe` `speakers` (Task 1).
- Produces: `window.SoriBridge.transcribe(path, device, speakers)`; `sori.live.speakers` (bool; absent = true).

- [ ] **Step 1: bridge.js** — `transcribe: (path, device, speakers = true) => call('POST', '/transcribe', { path, device, speakers }),`
- [ ] **Step 2: Chooser.** State `const [speakers, setSpeakers] = React.useState(true);`; in the open-reset effect add `setSpeakers(loadLive().speakers !== false);`. `pickFile`: `saveLive({ device, speakers });` and `window.SoriBridge.transcribe(path, device, speakers)`. The `choose` step block becomes:
```jsx
        {step === 'choose' && (
          <React.Fragment>
            <label className="modal-check">
              <input type="checkbox" checked={speakers} onChange={(e) => setSpeakers(e.target.checked)} />
              <span>화자 분리</span>
            </label>
            <div className="modal-actions">
              (the two existing buttons, unchanged)
            </div>
          </React.Fragment>
        )}
```
- [ ] **Step 3: Drop queue** — its `transcribe(path, pickDevice(devices, loadLive().device))` call becomes `transcribe(path, pickDevice(devices, loadLive().device), loadLive().speakers !== false)`.
- [ ] **Step 4: tokens.css** — `.modal-check { display: flex; align-items: center; gap: 8px; font-size: 14px; cursor: pointer; }`
- [ ] **Step 5: Verify** — `npm run build` → `dist ready`; Python suites pass.
- [ ] **Step 6: Commit** `feat(ui): 화자 분리 checkbox for file transcription`.

---

### Task 4: Verification + installers (controller)

- [ ] All four suites.
- [ ] `npm run tauri:dev`: screenshots of the title bar normal and maximized; minimize / maximize / restore / close via the custom buttons; close during a live recording keeps the WAV and leaves no pythonw.
- [ ] One file transcription with 화자 분리 on ("화자 N:" labels) and one off (no labels).
- [ ] Fresh `SORIGUL_HOME`: concurrent first requests (no "database is locked") and the "확인 중" stage during setup.
- [ ] x64 bundle `/devices` under emulation.
- [ ] `npm run tauri:build:arm64`, `npm run tauri:build:x64`: paths and sizes.
