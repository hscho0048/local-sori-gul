import json
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

import server

REAL_PROBE = server.probe_devices  # setUp replaces it with a mock


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
            # ffmpeg is downloaded by the same first-run setup (the installer does not bundle it)
            with patch("server.ffmpeg_path", side_effect=RuntimeError("오디오 디코더가 없습니다.")):
                self.assertFalse(server.models_ready())

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

    def test_setup_is_refused_while_shutting_down(self):
        server.CANCEL.set()
        try:
            self.assertEqual(self.request("POST", "/setup", {})[0], 503)
        finally:
            server.CANCEL.clear()

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

    def test_setup_progress_fields(self):
        emit = server.job_emitter("setup", None)
        server.JOB = {"state": "running", "op": "setup", "ready": [], "file": "", "progress": [], "percent": 0}
        emit("file", "models/a.bin")
        emit("progress", (40, 4, 10))
        emit("ready", "models/a.bin")
        self.assertEqual((server.JOB["file"], server.JOB["percent"], server.JOB["progress"], server.JOB["ready"]),
                         ("models/a.bin", 40, [40, 4, 10], ["models/a.bin"]))
