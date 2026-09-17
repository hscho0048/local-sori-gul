import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from engine import Cancelled, RATE, ROOT, WhisperNPU, WhisperGPU, check_cancel, chunks, decode_audio
from jobs import worker_environment


class AudioTests(unittest.TestCase):
    def test_gpu_worker_does_not_load_the_old_npu_runtime(self):
        self.assertEqual(worker_environment("transcribe", {"device": "gpu"}), ".venv-whisper-gpu")
        self.assertEqual(worker_environment("transcribe", {}), ".venv")
        self.assertEqual(worker_environment("transcribe", {"device": "npu"}), ".venv")
        self.assertEqual(worker_environment("index", {"device": "gpu"}), ".venv")

    def test_gpu_decoder_preserves_cross_cache_and_advances_self_cache(self):
        from types import SimpleNamespace
        worker = WhisperGPU.__new__(WhisperGPU)
        worker.cancel = threading.Event()
        worker.prompt, worker.eos, worker.limit = [9, 10, 11, 12], 8, 12
        worker.suppress, worker.generation = [], {}
        worker.encoder_dtype = np.float32
        worker.extractor = lambda *a, **k: {"input_features": np.zeros((1, 128, 3000))}
        worker.encoder = SimpleNamespace(run=lambda *a: [np.zeros((1, 1500, 1280))])
        worker.decoder_inputs = ["past_key_values.0.decoder.key", "past_key_values.0.encoder.key"]
        worker.decoder_outputs = ["logits", "present.0.decoder.key", "present.0.encoder.key"]
        seen = []
        def run(_, feed):
            seen.append((feed["input_ids"].tolist(), bool(feed["use_cache_branch"][0]),
                         feed[worker.decoder_inputs[1]].copy(), feed[worker.decoder_inputs[0]].copy()))
            logits = np.zeros((1, 1, 20), dtype=np.float32)
            logits[0, 0, 2 if len(seen) == 1 else 8] = 10
            return [logits, np.full((1, 20, len(seen), 64), len(seen)), np.ones((1, 20, 1500, 64))]
        worker.decoder = SimpleNamespace(run=run)
        worker.tokenizer = SimpleNamespace(decode=lambda ids, **kwargs: str(ids))
        self.assertEqual(worker.infer(np.zeros(RATE), lambda *a: None), ("[2]", False))
        self.assertEqual(seen[0][0], [[9, 10, 11, 12]])
        self.assertEqual(seen[1][0], [[2]])
        self.assertEqual([row[1] for row in seen], [False, True])
        self.assertEqual(seen[0][2].shape[2], 0)
        self.assertEqual(seen[1][2].shape[2], 1500)
        self.assertTrue(np.all(seen[1][3] == 1))

    def test_chunks_cover_long_audio_once_and_prefer_silence(self):
        pcm = np.full(63 * RATE + 123, 3000, dtype=np.int16)
        pcm[18 * RATE:19 * RATE] = 0
        spans = list(chunks(pcm))
        self.assertEqual(spans[0][0], 0)
        self.assertTrue(18 * RATE <= spans[0][1] <= 19 * RATE)
        self.assertEqual(spans[-1][1], len(pcm))
        self.assertTrue(all(a[1] == b[0] for a, b in zip(spans, spans[1:])))
        self.assertTrue(all(0 < end - start <= 20 * RATE for start, end in spans))

    def test_cancel_before_work(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(Cancelled):
            check_cancel(cancel)

    def test_reject_remote_and_missing_inputs(self):
        with tempfile.TemporaryDirectory() as folder:
            for name in ("https://example.com/private.mp3", "missing.wav", "playlist.m3u"):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    decode_audio(name, Path(folder) / "audio.pcm", threading.Event())

    def test_early_cancel_terminates_audio_process(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "input.wav"
            source.touch()
            cancel = threading.Event()
            cancel.set()
            with patch("engine.subprocess.Popen") as spawn, self.assertRaises(Cancelled):
                decode_audio(source, Path(folder) / "audio.pcm", cancel, ffmpeg=source)
            spawn.assert_not_called()

    def test_long_transcription_retries_token_limit_without_losing_tail(self):
        worker = WhisperNPU.__new__(WhisperNPU)
        worker.cancel = threading.Event()
        events = []
        worker.emit = lambda kind, value: events.append((kind, value))
        calls = []
        def infer(audio, preview):
            calls.append(len(audio))
            return ("discard this truncated output", True) if len(calls) == 1 else (f"part {len(calls)}", False)
        worker.infer = infer
        def decode(path, target, cancel):
            np.full(35 * RATE, 2000, dtype=np.int16).tofile(target)
        with patch("engine.decode_audio", decode):
            result = worker.transcribe("unused.wav")
        self.assertNotIn("discard", result)
        self.assertEqual(len(result.split("\n\n")), len(calls) - 1)
        percentages = [value[0] for kind, value in events if kind == "progress"]
        self.assertEqual(percentages, sorted(percentages))
        self.assertEqual(percentages[-1], 100)
        self.assertEqual(sum(calls[1:]), 35 * RATE)

    def test_short_segment_loop_is_collapsed_instead_of_failing(self):
        from engine import collapse_repeats
        self.assertEqual(collapse_repeats("오늘은 " + "수업을 위한 " * 30 + "수"), "오늘은 수업을 위한 수")
        self.assertEqual(collapse_repeats("네 네 좋아요"), "네 네 좋아요")
        worker = WhisperNPU.__new__(WhisperNPU)
        worker.cancel, worker.emit = threading.Event(), lambda *args: None
        worker.infer = lambda audio, preview: ("수업을 위한 " * 30, True)
        def decode(path, target, cancel):
            np.full(2 * RATE, 2000, dtype=np.int16).tofile(target)
        with patch("engine.decode_audio", decode):
            self.assertEqual(worker.transcribe("unused.wav"), "수업을 위한")

    def test_silence_does_not_hallucinate_or_call_model(self):
        worker = WhisperNPU.__new__(WhisperNPU)
        worker.cancel = threading.Event()
        worker.emit = lambda *args: None
        worker.infer = lambda *args: self.fail("Silence should not run the model")
        def decode(path, target, cancel):
            np.zeros(3 * RATE, dtype=np.int16).tofile(target)
        with patch("engine.decode_audio", decode):
            self.assertEqual(worker.transcribe("unused.wav"), "")

    def test_transcription_with_speakers_cuts_chunks_at_speaker_changes_and_labels_paragraphs(self):
        worker = WhisperNPU.__new__(WhisperNPU)
        worker.cancel = threading.Event()
        worker.emit = lambda *args: None
        seen = []
        def infer(audio, preview):
            seen.append(len(audio))
            return f"{len(seen)}번 구간", False
        worker.infer = infer
        def decode(path, target, cancel):
            np.full(30 * RATE, 2000, dtype=np.int16).tofile(target)
        spans = [(0, 7 * RATE, 0), (7 * RATE, 9 * RATE, 1), (9 * RATE, 30 * RATE, 0)]
        with patch("engine.decode_audio", decode), patch("diarize.diarize", return_value=spans):
            result = worker.transcribe("unused.wav", speakers=object())
        self.assertEqual(seen[:2], [7 * RATE, 2 * RATE])                       # chunk edges follow the speaker spans
        self.assertTrue(all(length <= 20 * RATE for length in seen))            # long spans still respect the 20 s cap
        self.assertTrue(result.startswith("화자 1: 1번 구간\n\n화자 2: 2번 구간\n\n화자 1: 3번 구간"))
        self.assertEqual(result.count("화자 1:"), 2)                            # consecutive same-speaker chunks merge

    def test_generation_uses_language_prompt_and_updated_cache(self):
        from types import SimpleNamespace
        worker = WhisperNPU.__new__(WhisperNPU)
        worker.cancel = threading.Event()
        worker.prompt, worker.eos, worker.limit = [9, 10, 11, 12], 8, 12
        worker.suppress, worker.generation = [], {}
        worker.inputs = {"k_cache_self_0_in": SimpleNamespace(shape=(1,))}
        worker.extractor = lambda *a, **k: {"input_features": np.zeros((1, 128, 3000))}
        worker.encoder = SimpleNamespace(run=lambda *a: [], get_outputs=lambda: [])
        seen = []
        def run(_, feed):
            seen.append((int(feed["input_ids"].item()), int(feed["position_ids"].item()), float(feed["k_cache_self_0_in"].item())))
            logits = np.zeros((1, 20, 1, 1), dtype=np.float16)
            logits[0, 2 if len(seen) == 4 else 8, 0, 0] = 10
            return [logits, np.array([len(seen)], dtype=np.float16)]
        worker.decoder = SimpleNamespace(run=run, get_outputs=lambda: [SimpleNamespace(name="logits"), SimpleNamespace(name="k_cache_self_0_out")])
        worker.tokenizer = SimpleNamespace(decode=lambda ids, **kwargs: str(ids))
        self.assertEqual(worker.infer(np.zeros(RATE), lambda *a: None), ("[2]", False))
        self.assertEqual([x[0] for x in seen], [9, 10, 11, 12, 2])
        self.assertEqual([x[2] for x in seen], [0, 1, 2, 3, 4])


def noise(seconds, seed=0):
    return (np.random.default_rng(seed).standard_normal(int(seconds * RATE)) * 3000).astype(np.int16)


class LiveTests(unittest.TestCase):
    def test_split_point_waits_then_cuts_at_the_first_pause_or_the_quietest_window(self):
        from engine import split_point
        speech_pause_speech = np.concatenate([noise(7), np.zeros(int(0.6 * RATE), dtype=np.int16), noise(3, 1)])
        self.assertIsNone(split_point(noise(5)))                      # too short to cut
        cut = split_point(speech_pause_speech)
        self.assertTrue(7 * RATE <= cut <= 7.6 * RATE)                # inside the pause
        self.assertIsNone(split_point(noise(15)))                     # continuous speech: keep growing...
        cut = split_point(noise(21))
        self.assertTrue(6 * RATE <= cut <= 21 * RATE)                 # ...until the maximum, then the quietest window

    def test_listen_transcribes_closed_segments_then_the_tail_on_stop_and_keeps_the_recording(self):
        import io
        pcm = np.concatenate([noise(7), np.zeros(int(0.6 * RATE), dtype=np.int16), noise(4, 1)])

        class FakeFfmpeg:
            def __init__(self):
                self.stdout, self.stderr, self.code = io.BytesIO(pcm.tobytes()), io.BytesIO(b""), None
            def poll(self):
                return self.code
            def terminate(self):
                self.code = 0
            kill = terminate
            def wait(self):
                return 0

        worker = WhisperNPU.__new__(WhisperNPU)
        worker.cancel, stop = threading.Event(), threading.Event()
        texts = []
        worker.emit = lambda kind, value: (texts.append(value), stop.set()) if kind == "text" else None
        worker.infer = lambda audio, preview: (f"{int(len(audio) / RATE)}초 구간", False)
        with tempfile.TemporaryDirectory() as folder, patch("engine.subprocess.Popen", return_value=FakeFfmpeg()), \
                patch("engine.ffmpeg_path", return_value=Path("ffmpeg.exe")):
            wav = Path(folder) / "live.wav"
            result = worker.listen("mic", stop, prefix="기존 본문.", wav_path=wav)
            import wave
            with wave.open(str(wav)) as saved:
                self.assertEqual(saved.getnframes(), len(pcm))
        self.assertEqual(result, "기존 본문.\n\n7초 구간\n\n4초 구간")  # first pause closes a segment; stop flushes the tail
        self.assertEqual(texts[0], "기존 본문.\n\n7초 구간")

    def test_listen_skips_silence_and_reports_a_dead_microphone(self):
        import io

        class DeadFfmpeg:
            stdout, stderr, code = io.BytesIO(np.zeros(7 * RATE, dtype=np.int16).tobytes()), io.BytesIO(b"device busy"), None
            def poll(self):
                return self.code
            def terminate(self):
                self.code = 1
            kill = terminate
            def wait(self):
                return 1

        worker = WhisperNPU.__new__(WhisperNPU)
        worker.cancel, worker.emit = threading.Event(), lambda *a: None
        worker.infer = lambda *a: self.fail("silence must not reach the model")
        fake = DeadFfmpeg()
        def wait(seconds):  # the mic dies after the silent buffer is drained
            fake.code = 1
        worker.cancel.wait = wait
        with patch("engine.subprocess.Popen", return_value=fake), patch("engine.ffmpeg_path", return_value=Path("ffmpeg.exe")):
            with self.assertRaisesRegex(RuntimeError, "device busy"):
                worker.listen("mic", threading.Event())

    def test_audio_devices_parses_ffmpeg_listing(self):
        from types import SimpleNamespace
        from engine import audio_devices
        listing = ('[dshow] "Surface Camera Front" (video)\n[dshow] "Microphone Array(Qualcomm)" (audio)\n'
                   '[dshow]   Alternative name "@device_cm_x"\n[dshow] "Headset Mic" (audio)\n')
        with patch("engine.subprocess.run", return_value=SimpleNamespace(stderr=listing)), \
                patch("engine.ffmpeg_path", return_value=Path("ffmpeg.exe")):
            self.assertEqual(audio_devices(), ["Microphone Array(Qualcomm)", "Headset Mic"])
        self.assertEqual(worker_environment("listen", {"device": "gpu"}), ".venv-whisper-gpu")
        self.assertEqual(worker_environment("listen", {}), ".venv")

    def test_audio_devices_reads_korean_names_as_utf8(self):
        # ffmpeg writes DirectShow names as UTF-8; on Korean Windows the locale codec (cp949) garbled them.
        import subprocess
        import sys
        from engine import audio_devices
        name = "마이크 배열(인텔® 스마트 사운드 기술)"
        script = f"import sys; sys.stderr.buffer.write('[dshow] \"{name}\" (audio)\\n'.encode('utf-8'))"
        real_run = subprocess.run
        with patch("engine.subprocess.run", side_effect=lambda command, **kwargs: real_run([sys.executable, "-c", script], **kwargs)), \
                patch("engine.ffmpeg_path", return_value=Path("ffmpeg.exe")):
            self.assertEqual(audio_devices(), [name])


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
            self.assertEqual(jobs.worker_python("transcribe", {"device": "intel-gpu"}),
                             (Path(code) / "pythonw.exe", Path(code) / "Lib" / "site-packages"))
            with patch("jobs.ARM64", True):
                self.assertEqual(jobs.worker_environment("setup", {}), ".venv-whisper-gpu")
            with patch("jobs.ARM64", False):
                self.assertEqual(jobs.worker_environment("setup", {}), ".venv")


class DeviceTests(unittest.TestCase):
    def fake_models(self, folder):
        for name in ("tokenizer.json", "preprocessor_config.json", "generation_config.json",
                     "whisper-gpu/encoder_static_fp16.onnx", "whisper-gpu/decoder_model_merged_fp16.onnx"):
            (Path(folder) / name).parent.mkdir(parents=True, exist_ok=True)
            (Path(folder) / name).write_text("{}")

    def load(self, ov_device=None, available=("CPU", "GPU.0")):
        """WhisperCPU with onnxruntime/openvino/tokenizers/transformers mocked; returns (worker, sessions created)."""
        import sys
        from types import ModuleType, SimpleNamespace
        from engine import WhisperCPU
        created = []

        class Session:
            def __init__(self, path, sess_options=None, providers=None, disabled_optimizers=None):
                self.path, self.providers, self.disabled = path, providers, disabled_optimizers
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
                "onnxruntime_qnn": None}), patch("engine.os.add_dll_directory", return_value=None), \
                patch.dict(os.environ):
            self.fake_models(folder)
            worker = WhisperCPU(lambda kind, value: stages.append((kind, value)), threading.Event(),
                                model_dir=folder, ov_device=ov_device)
        return worker, created, stages

    def test_cpu_device_runs_both_sessions_on_the_cpu_without_qnn(self):
        worker, created, stages = self.load()
        self.assertEqual([s.providers for s in created], [["CPUExecutionProvider"], ["CPUExecutionProvider"]])
        # onnxruntime 1.24 (x64) fails to build this fp16 encoder with the fusion enabled
        self.assertEqual(created[0].disabled, ["SimplifiedLayerNormFusion"])
        self.assertEqual(worker.limit, WhisperGPU.LIMIT)
        self.assertEqual(worker.encoder_dtype, np.float32)
        self.assertIn(("ready", "CPU"), stages)

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


class SetupAssetTests(unittest.TestCase):
    def test_setup_reports_its_three_steps_in_order_and_the_download_size(self):
        import setup_assets
        events = []
        with tempfile.TemporaryDirectory() as home, patch("setup_assets.ROOT", Path(home)), \
                patch("setup_assets.CODE", Path(home)), patch("setup_assets.ARM64", False), \
                patch("setup_assets.download", side_effect=lambda url, target, *a, **k: events.append(("download", target.name))), \
                patch("setup_assets.setup_whisper_gpu", side_effect=lambda emit: events.append(("download", "whisper-gpu"))), \
                patch("diarize.static_model"):
            (Path(home) / "tools").mkdir()
            (Path(home) / "tools" / "ffmpeg.exe").write_bytes(b"")  # already present: no ffmpeg download
            setup_assets.main(lambda kind, value: events.append((kind, value)) if kind in ("step", "size") else None,
                              whisper_gpu=True)
        steps = [value for kind, value in events if kind == "step"]
        self.assertEqual(steps, ["speech", "speaker", "audio"])
        self.assertEqual(events[0], ("size", 1640))
        self.assertLess(events.index(("download", "whisper-gpu")), events.index(("step", "speaker")))

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
            self.assertEqual(events, [("stage", "models/a.bin 확인 중…"), ("ready", "models/a.bin")])

    def test_required_files_include_the_npu_bundle_only_on_arm64(self):
        import setup_assets
        with patch("setup_assets.ARM64", False):
            x64 = setup_assets.required_files()
        with patch("setup_assets.ARM64", True):
            arm = setup_assets.required_files()
        self.assertIn("whisper-gpu/encoder_static_fp16.onnx", x64)
        self.assertIn("speaker/speaker_static_198.onnx", x64)
        self.assertNotIn("encoder/model.bin", x64)
        self.assertIn("encoder/model.bin", arm)


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


if __name__ == "__main__":
    unittest.main()
