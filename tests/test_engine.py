import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from engine import Cancelled, RATE, WhisperNPU, WhisperGPU, check_cancel, chunks, decode_audio
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


if __name__ == "__main__":
    unittest.main()
