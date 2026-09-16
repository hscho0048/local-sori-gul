"""One disposable model process at a time; UI never owns model sessions."""
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


def model_worker(connection, cancelled, operation, payload, finish=None, packages=None):
    # spawn copies the parent's sys.path; swap in this worker's own packages (venv site-packages, or the bundle's
    # site-packages / gpu-packages dir) so the GPU child never imports the NPU runtime or vice versa.
    import site
    import sys
    sys.path = [p for p in sys.path if not p.endswith(("site-packages", "gpu-packages"))] + \
        ([packages] if packages else site.getsitepackages())
    try:
        def emit(kind, value):
            connection.send((kind, value))
        # A Windows file lock also prevents two app instances loading models together.
        import msvcrt
        ROOT.mkdir(parents=True, exist_ok=True)
        with (ROOT / ".model.lock").open("a+b") as lock:
            if lock.tell() == 0:
                lock.write(b"0")
                lock.flush()
            lock.seek(0)
            try:
                msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise RuntimeError("다른 소리글 작업이 모델을 사용 중입니다. 해당 작업이 끝난 뒤 다시 실행해 주세요.")
            if operation == "transcribe":
                from engine import load_whisper
                whisper = load_whisper(payload.get("device", "npu"), emit, cancelled)
                speakers = None
                if payload.get("speakers"):
                    from diarize import SpeakerEmbedder
                    # The GPU transcription environment has no HTP session; its speaker model runs on the CPU (~36 ms/window).
                    speakers = SpeakerEmbedder("npu" if payload.get("device", "npu") == "npu" else "cpu", emit=emit)
                result = whisper.transcribe(payload["path"], speakers=speakers)
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
                    if payload.get("note_id") and wav.exists() and wav.stat().st_size > 44:
                        from library import Library
                        library = Library()
                        try:
                            library.attach_audio(payload["note_id"], wav)
                        finally:
                            library.close()
                finally:
                    wav.unlink(missing_ok=True)
            elif operation == "setup":
                import setup_assets
                setup_assets.main(emit, whisper_gpu=True)
                result = None
            else:
                raise ValueError("Unknown operation")
            emit("result", result)
    except Exception as error:
        if cancelled.is_set():
            connection.send(("cancelled", None))
        else:
            connection.send(("error", str(error)))
    finally:
        connection.close()


def run_job(operation, payload, emit, cancel, target=model_worker, finish=None):
    """Deliver completion only after the process (including all model memory) exits.

    `cancel` aborts and discards; `finish` (used by live transcription) asks the worker to wrap up and still return."""
    executable, packages = worker_python(operation, payload)
    if not executable.exists():
        raise RuntimeError("실행 환경이 없습니다. setup.cmd를 실행해 주세요.")
    # A Windows venv python.exe is a redirector that re-launches the base interpreter as a grandchild, so
    # multiprocessing's duplicated Event handles never reach it (bpo-35797). Launch the base interpreter
    # directly and let __PYVENV_LAUNCHER__ select the target venv, exactly as multiprocessing does itself.
    mp.set_executable(str(executable) if packages else getattr(sys, "_base_executable", sys.executable))
    context = mp.get_context("spawn")
    receive, send = context.Pipe(duplex=False)
    stop = context.Event()
    soft = context.Event()
    process = context.Process(target=target, args=(send, stop, operation, payload, soft, packages and str(packages)))
    terminal = None
    cancel_at = None
    if not packages:
        os.environ["__PYVENV_LAUNCHER__"] = str(executable)
    try:
        process.start()
    finally:
        os.environ.pop("__PYVENV_LAUNCHER__", None)
    send.close()
    try:
        while True:
            if finish is not None and finish.is_set():
                soft.set()
            if cancel.is_set():
                stop.set()
                cancel_at = cancel_at or time.monotonic()
                if time.monotonic() - cancel_at > 8:
                    process.terminate()
                    break
            try:
                if receive.poll(0.05):
                    kind, value = receive.recv()
                elif process.is_alive():
                    continue
                else:
                    break
            except (EOFError, OSError):
                break  # writer closed: the child has finished sending
            if kind in ("result", "error", "cancelled"):
                terminal = (kind, value)
            elif not cancel.is_set():
                emit(kind, value)
        # Keep checking cancellation while native destructors release the accelerator.
        while process.is_alive():
            process.join(0.1)
            if cancel.is_set():
                stop.set()
                cancel_at = cancel_at or time.monotonic()
                if time.monotonic() - cancel_at > 8:
                    process.terminate()
        process.join()
        if cancel.is_set():
            emit("cancelled", None)
        elif process.exitcode != 0:
            emit("error", f"작업 프로세스가 종료됐습니다 (코드 {process.exitcode}). 원문은 유지됩니다.")
        elif terminal:
            kind, value = terminal
            emit(RESULT_KIND[operation] if kind == "result" else kind, value)
        else:
            emit("error", "작업이 결과 없이 끝났습니다. 원문은 유지됩니다.")
    finally:
        if process.is_alive():
            stop.set()
            process.join(2)
            if process.is_alive():
                process.terminate()
                process.join()
        receive.close()
        process.close()
