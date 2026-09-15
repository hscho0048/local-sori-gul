"""HTTP bridge between the Tauri window and the transcription backend. Stdlib only.

Tauri starts `pythonw server.py`, reads the first stdout line `PORT <n> <token>` and sends the token as X-Bridge-Token
on every request (any web page could otherwise reach a localhost port). The server exits when its stdin closes, i.e.
when the app goes away, cancelling a running job first so the model lock is released."""
from contextlib import closing
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
import threading
from urllib.parse import parse_qs, urlparse
import wave

from engine import EXTENSIONS, audio_devices
from jobs import run_job
from library import Library, keywords

TOKEN = secrets.token_urlsafe(24)
JOB = {"state": "idle"}  # ponytail: read/written across threads with no lock, relying on GIL-atomic dict
                          # reads and whole-dict swaps (start_job); add a lock around reads too if that
                          # assumption ever breaks (e.g. multi-field consistency is needed).
JOB_LOCK = threading.Lock()
FINISH = threading.Event()  # ⏹ 녹음 마치기: stop recording, transcribe the tail, keep text and WAV
CANCEL = threading.Event()  # set only on shutdown
WORKER = None
ROUTES = []
finished = ""  # text of completed chunks only (updated on "text" events, not "preview"); what we save
               # to the note on error/cancel/shutdown instead of the in-progress preview


class HttpError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status


def route(method, pattern):
    def register(function):
        ROUTES.append((method, re.compile(pattern + "$"), function))
        return function
    return register


def save_text(path, text):
    """Replace only after the complete UTF-8 file is safely written (from audio2text app.py)."""
    path = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8-sig", dir=path.parent,
                                         prefix=".sori-gul-", suffix=".tmp", delete=False) as target:
            temporary = Path(target.name)
            target.write(text)
            target.flush()
            os.fsync(target.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def device(body):
    value = body.get("device", "npu")
    if value not in ("npu", "gpu"):
        raise HttpError(400, "device must be 'npu' or 'gpu'")
    return value


def ensure_idle():
    if JOB.get("state") == "running":
        raise HttpError(409, "다른 전사 작업이 진행 중입니다. 끝난 뒤 다시 시작해 주세요.")


def start_job(operation, payload, note_id):
    global WORKER, JOB, finished
    with JOB_LOCK:
        ensure_idle()
        FINISH.clear()
        finished = ""
        JOB = {"state": "running", "op": operation, "note_id": note_id, "stage": "준비 중",
               "text": "", "percent": 0, "error": None}  # new dict, not JOB.clear()+update(), so a
               # concurrent GET /job (reading the JOB global with no lock) never observes {}
    WORKER = threading.Thread(target=run, args=(operation, payload, note_id), daemon=True)
    WORKER.start()


def run(operation, payload, note_id):
    duration = None

    def emit(kind, value):
        nonlocal duration
        global finished
        if kind == "stage":
            JOB["stage"] = value
        elif kind == "duration":
            duration = value
        elif kind == "progress":
            JOB["percent"] = value[0]
        elif kind == "text":
            finished = value
            JOB["text"] = value
        elif kind == "preview":
            JOB["text"] = value[0]
        elif kind == "done":
            write_error = None
            try:
                with closing(Library()) as library:
                    note = library.get(note_id)
                    if operation == "listen" and note and note["audio"]:
                        with wave.open(str(library.audio_path(note)), "rb") as recording:
                            duration = recording.getnframes() / recording.getframerate()
                    library.update(note_id, transcript=value,
                                   **({} if duration is None else {"duration": duration}))
            except Exception as error:
                write_error = str(error)
            # JOB state must land on "done" or "error" even if the write above raised, so the job
            # slot never stays stuck on "running" (fix 3): no bare DB write before the JOB.update.
            if write_error is None:
                JOB.update(state="done", text=value, percent=100)
            else:
                JOB.update(state="error", error=write_error)
        elif kind in ("error", "cancelled"):
            try:
                if finished:  # keep what was transcribed so far, as the Tk app did
                    with closing(Library()) as library:
                        library.update(note_id, transcript=finished)
            except Exception:
                pass  # keep the original error/cancel reason; the job slot still frees up below
            JOB.update(state="error", error=str(value or "취소됐습니다."))

    try:
        run_job(operation, payload, emit, CANCEL, finish=FINISH)
    except Exception as error:
        emit("error", str(error))


@route("GET", r"/notes")
def list_notes(library, body, query):
    return [dict(row, transcript=None, keywords=keywords(row["transcript"]))
            for row in library.list(query.get("view", "all"), query.get("q", ""))]


@route("GET", r"/notes/(\d+)")
def get_note(library, body, query, note_id):
    note = library.get(int(note_id))
    if not note:
        raise HttpError(404, "받아쓰기를 찾을 수 없습니다.")
    return dict(note)


@route("PATCH", r"/notes/(\d+)")
def patch_note(library, body, query, note_id):
    library.update(int(note_id), **body)
    return {"ok": True}


@route("DELETE", r"/notes/(\d+)")
def delete_note(library, body, query, note_id):
    if JOB.get("state") == "running" and JOB.get("note_id") == int(note_id):
        raise HttpError(409, "전사 중인 받아쓰기는 삭제할 수 없습니다.")
    library.delete(int(note_id))
    return {"ok": True}


@route("POST", r"/notes/(\d+)/export")
def export_note(library, body, query, note_id):
    note = get_note(library, body, query, note_id)
    path = Path(body.get("path") or "")
    if path.suffix.lower() != ".txt":
        raise HttpError(400, ".txt 확장자로 저장해 주세요.")
    save_text(path, note["transcript"])
    return {"ok": True}


@route("GET", r"/folders")
def list_folders(library, body, query):
    return [dict(row) for row in library.folders()]


@route("POST", r"/folders")
def create_folder(library, body, query):
    return {"id": library.create_folder(body.get("name") or "")}


@route("DELETE", r"/folders/(\d+)")
def delete_folder(library, body, query, folder_id):
    library.delete_folder(int(folder_id))
    return {"ok": True}


@route("GET", r"/mics")
def mics(library, body, query):
    return audio_devices()


@route("POST", r"/transcribe")
def transcribe(library, body, query):
    path = Path(body.get("path") or "")
    if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
        raise HttpError(400, "지원하는 로컬 오디오 파일을 선택해 주세요.")
    selected = device(body)  # validate before library.create, as /live does, so a bad device doesn't
                              # leave an orphan note + copied audio behind
    ensure_idle()
    note_id = library.create(path.stem, "audio", audio=path)
    start_job("transcribe", {"path": str(library.audio_path(library.get(note_id))), "device": selected,
                             "speakers": True}, note_id)
    return {"note_id": note_id}


@route("POST", r"/live")
def live(library, body, query):
    if not body.get("mic"):
        raise HttpError(400, "마이크를 선택해 주세요.")
    selected = device(body)
    ensure_idle()
    note_id = library.create(f"실시간 전사 {datetime.now():%Y-%m-%d %H:%M}", "live")
    start_job("listen", {"mic": body["mic"], "device": selected, "note_id": note_id}, note_id)
    return {"note_id": note_id}


@route("POST", r"/live/stop")
def stop_live(library, body, query):
    FINISH.set()
    return {"ok": True}


@route("GET", r"/job")
def job(library, body, query):
    return dict(JOB)


class Handler(BaseHTTPRequestHandler):
    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PATCH, DELETE")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Bridge-Token")

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def handle_request(self):
        url = urlparse(self.path)
        try:
            if not secrets.compare_digest(self.headers.get("X-Bridge-Token", ""), TOKEN):
                raise HttpError(403, "forbidden")
            for method, pattern, function in ROUTES:
                match = pattern.match(url.path)
                if match and method == self.command:
                    break
            else:
                raise HttpError(404, "not found")
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length)) if length else {}
            query = {key: values[0] for key, values in parse_qs(url.query).items()}
            # ponytail: a fresh sqlite connection per request, including every 500 ms /job poll — fine
            # for one local user; switch to one shared connection + lock if polling cost ever shows up
            with closing(Library()) as library:
                status, result = 200, function(library, body, query, *match.groups())
        except HttpError as error:
            status, result = error.status, {"error": str(error)}
        except (ValueError, TypeError) as error:
            status, result = 400, {"error": str(error)}
        except Exception as error:
            status, result = 500, {"error": str(error)}
        data = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    do_GET = do_POST = do_PATCH = do_DELETE = handle_request

    def log_message(self, *args):
        pass


def main():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print("PORT", server.server_address[1], TOKEN, flush=True)  # pythonw stdout is a block-buffered pipe
    sys.stdin.buffer.read()  # blocks until Tauri closes the pipe (window closed, app exited or crashed)
    if JOB.get("state") == "running" and finished:
        # a window close during a job must not lose the transcript: save what's finished so far before
        # asking the worker to stop, since it may not exit in time to reach its own "text"/"done" write
        try:
            with closing(Library()) as library:
                library.update(JOB["note_id"], transcript=finished)
        except Exception:
            pass  # best-effort — the process is exiting either way
    CANCEL.set()  # the worker only notices CANCEL between chunks; Tauri kills the process tree ~3 s
                  # after closing stdin regardless, so the join below is best-effort, not a guarantee
    if WORKER:
        WORKER.join(15)
    os._exit(0)  # ponytail: skips interpreter cleanup (atexit/gc) — needed because multiprocessing's
                 # atexit would otherwise try to join a still-running worker; fine, process is exiting


if __name__ == "__main__":
    main()
