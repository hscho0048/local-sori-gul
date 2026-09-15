"""Offline Whisper on QNN HTP or Adreno GPU with bounded audio chunks."""
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import tempfile
import threading
import wave

# Set before importing Hugging Face; inference never downloads assets.
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import numpy as np

ROOT = Path(__file__).resolve().parent
RATE = 16000
EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".aac", ".ogg", ".opus", ".wma", ".mp4"}


class Cancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel.is_set():
        raise Cancelled()


def collapse_repeats(text):
    """Greedy decoding can loop ("수업을 위한 수업을 위한 …"); keep one copy of any phrase repeated 5+ times in a row."""
    # ponytail: only used on token-limited output, where a run of 5+ identical phrases is a loop, not speech.
    return re.sub(r"(.{1,30}?)(?:\s*\1){4,}", r"\1", text).strip()


def chunks(pcm, start=0, total=None):
    """Partition every sample of pcm[start:total] once, preferring quiet 200 ms windows near boundaries."""
    total = len(pcm) if total is None else total
    while start < total:
        end = min(start + 20 * RATE, total)
        if end < total:
            lo = start + 12 * RATE
            window = RATE // 5
            signal = np.asarray(pcm[lo:end], dtype=np.float32)
            energy = np.mean(signal.reshape(-1, window) ** 2, axis=1)
            quiet = np.flatnonzero(energy < max(32.0 ** 2, float(np.median(energy)) * 0.08))
            index = int(quiet[-1]) if len(quiet) else int(np.argmin(energy))
            end = lo + index * window + window // 2
        yield start, end
        start = end


# ---- live microphone ------------------------------------------------------------------------------------------------
SILENCE_RMS = 64  # int16 units (about -54 dBFS); quieter segments are not sent to Whisper, which hallucinates on silence
# ponytail: fixed gate; make it adaptive (noise-floor tracking) if a quiet microphone never triggers transcription.


def ffmpeg_path(ffmpeg=None):
    executable = Path(ffmpeg) if ffmpeg else ROOT / "tools" / "ffmpeg.exe"
    if not executable.is_file():
        raise RuntimeError("오디오 디코더가 없습니다. setup.cmd를 실행해 주세요.")
    return executable


def audio_devices(ffmpeg=None):
    """Microphone names as DirectShow reports them to ffmpeg (Windows)."""
    listing = subprocess.run([str(ffmpeg_path(ffmpeg)), "-hide_banner", "-list_devices", "true", "-f", "dshow", "-i", "dummy"],
                             capture_output=True, text=True, errors="replace", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    return re.findall(r'"([^"]+)" \(audio\)', listing.stderr)


def split_point(pcm, min_seconds=6, max_seconds=20):
    """Where to cut a growing live buffer: the last quiet 200 ms window after min_seconds, the quietest window once
    max_seconds is reached, or None while the buffer should keep growing. Same energy rule as chunks()."""
    if len(pcm) < min_seconds * RATE:
        return None
    window = RATE // 5
    usable = len(pcm) - len(pcm) % window
    energy = np.mean(np.asarray(pcm[:usable], dtype=np.float32).reshape(-1, window) ** 2, axis=1)
    first = min_seconds * RATE // window
    quiet = np.flatnonzero(energy[first:] < max(32.0 ** 2, float(np.median(energy)) * 0.08))
    if len(quiet):
        return (first + int(quiet[-1])) * window + window // 2
    if len(pcm) >= max_seconds * RATE:
        return (first + int(np.argmin(energy[first:]))) * window + window // 2
    return None


def render(parts):
    """Transcript text from (speaker label, text) pairs: consecutive chunks of one speaker form one paragraph headed
    '화자 N:'; a recording with a single detected speaker (or no diarization) is plain paragraphs."""
    labels = {label for label, _ in parts if label is not None}
    if len(labels) < 2:
        return "\n\n".join(text for _, text in parts)
    paragraphs = []
    for label, text in parts:
        if paragraphs and paragraphs[-1][0] == label:
            paragraphs[-1][1].append(text)
        else:
            paragraphs.append((label, [text]))
    return "\n\n".join(f"화자 {label + 1}: " + " ".join(texts) for label, texts in paragraphs)


def decode_audio(path, target, cancel, ffmpeg=None):
    path = Path(path).resolve()
    if not path.is_file() or path.suffix.lower() not in EXTENSIONS:
        raise ValueError("지원하는 로컬 오디오 파일을 선택해 주세요.")
    executable = Path(ffmpeg) if ffmpeg else ROOT / "tools" / "ffmpeg.exe"
    if not executable.is_file():
        raise RuntimeError("오디오 디코더가 없습니다. setup.cmd를 실행해 주세요.")
    command = [str(executable), "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
               "-protocol_whitelist", "file,pipe", "-i", str(path), "-map", "0:a:0",
               "-vn", "-ac", "1", "-ar", str(RATE), "-f", "s16le", str(target)]
    check_cancel(cancel)
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command, stdout=subprocess.DEVNULL, stderr=errors,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        try:
            while process.poll() is None:
                if cancel.wait(0.1):
                    raise Cancelled()
            check_cancel(cancel)
            if process.returncode:
                errors.seek(max(0, errors.tell() - 3000))
                detail = errors.read().decode("utf-8", errors="replace")
                raise RuntimeError("오디오를 읽지 못했습니다.\n" + detail)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
    if not target.stat().st_size:
        raise ValueError("오디오 파일에 소리가 없습니다.")


class WhisperNPU:
    def __init__(self, emit, cancel, model_dir=None, profile=False):
        if platform.machine().lower() != "arm64":
            raise RuntimeError("Windows ARM64 Python으로 실행해야 NPU를 사용할 수 있습니다. setup.cmd를 실행해 주세요.")
        import onnxruntime as ort
        from tokenizers import Tokenizer
        from transformers import WhisperFeatureExtractor

        self.emit, self.cancel = emit, cancel
        self.model_dir = Path(model_dir) if model_dir else ROOT / "models"
        for name in ("encoder/model.onnx", "encoder/model.bin", "decoder/model.onnx", "decoder/model.bin",
                     "tokenizer.json", "preprocessor_config.json", "generation_config.json"):
            if not (self.model_dir / name).is_file():
                raise RuntimeError(f"모델 파일이 없습니다: {name}\n처음 한 번 setup.cmd를 실행해 주세요.")
        if "QNNExecutionProvider" not in ort.get_available_providers():
            raise RuntimeError("QNN 런타임이 없습니다. ARM64 가상환경에서 setup.cmd를 실행해 주세요.")
        ort.disable_telemetry_events()
        capi = Path(ort.__file__).parent / "capi"
        self.dll_directory = os.add_dll_directory(str(capi))
        provider = [("QNNExecutionProvider", {"backend_path": str(capi / "QnnHtp.dll"),
                                             "htp_performance_mode": "burst"})]
        self.sessions = []
        for name in ("encoder", "decoder"):
            check_cancel(cancel)
            emit("stage", f"NPU {name} 모델을 불러오는 중…")
            options = ort.SessionOptions()
            options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
            options.enable_profiling = profile
            if profile:
                folder = ROOT / "diagnostics"
                folder.mkdir(exist_ok=True)
                options.profile_file_prefix = str(folder / name)
            session = ort.InferenceSession(str(self.model_dir / name / "model.onnx"),
                                           sess_options=options, providers=provider)
            session.disable_fallback()
            if "QNNExecutionProvider" not in session.get_providers():
                raise RuntimeError("NPU 세션 생성에 실패했습니다. Snapdragon NPU 드라이버를 확인해 주세요.")
            self.sessions.append(session)
        self.encoder, self.decoder = self.sessions
        self.inputs = {item.name: item for item in self.decoder.get_inputs()}
        self.limit = self.inputs["attention_mask"].shape[-1]
        self.tokenizer = Tokenizer.from_file(str(self.model_dir / "tokenizer.json"))
        self.extractor = WhisperFeatureExtractor.from_pretrained(str(self.model_dir), local_files_only=True)
        self.generation = json.loads((self.model_dir / "generation_config.json").read_text("utf-8"))
        self.prompt = [self.tokenizer.token_to_id(t) for t in
                       ("<|startoftranscript|>", "<|ko|>", "<|transcribe|>", "<|notimestamps|>")]
        self.eos = self.tokenizer.token_to_id("<|endoftext|>")
        if None in self.prompt or self.eos is None:
            raise RuntimeError("한국어 Whisper 토크나이저 구성이 올바르지 않습니다.")
        self.suppress = self.generation.get("suppress_tokens", [])
        emit("ready", "Snapdragon NPU · QNN HTP · CPU 대체 실행 차단")

    def infer(self, audio, preview):
        check_cancel(self.cancel)
        features = self.extractor(audio, sampling_rate=RATE, return_tensors="np")["input_features"]
        cross = self.encoder.run(None, {"input_features": features.astype(np.float16)})
        feed = {name: np.zeros(meta.shape, dtype=np.float16)
                for name, meta in self.inputs.items() if "_self_" in name}
        feed.update({meta.name: value for meta, value in zip(self.encoder.get_outputs(), cross)})
        mask = np.full((1, 1, 1, self.limit), -100, dtype=np.float16)
        token, generated = self.prompt[0], []
        output_names = [meta.name for meta in self.decoder.get_outputs()]
        for position in range(self.limit - 1):
            check_cancel(self.cancel)
            mask[..., self.limit - position - 1] = 0
            feed.update(input_ids=np.array([[token]], dtype=np.int32), attention_mask=mask,
                        position_ids=np.array([position], dtype=np.int32))
            output = self.decoder.run(None, feed)
            for name, value in zip(output_names[1:], output[1:]):
                feed[name.removesuffix("_out") + "_in"] = value
            if position < len(self.prompt) - 1:
                token = self.prompt[position + 1]
                continue
            logits = output[0].reshape(-1).astype(np.float32)
            # Special language/task/timestamp tokens are not transcript text.
            logits[self.eos + 1:] = -np.inf
            logits[self.suppress] = -np.inf
            if not generated:
                logits[self.generation.get("begin_suppress_tokens", [])] = -np.inf
            token = int(np.argmax(logits))
            if token == self.eos:
                return self.tokenizer.decode(generated, skip_special_tokens=True).strip(), False
            generated.append(token)
            if len(generated) % 4 == 0:
                preview(self.tokenizer.decode(generated, skip_special_tokens=True).strip(), len(generated))
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip(), True

    def transcribe(self, path, speakers=None):
        """Whole-file transcription. With `speakers` (a diarize.SpeakerEmbedder) the recording is first split into
        speaker spans and Whisper chunks never cross a speaker change, so each paragraph can carry its speaker."""
        self.emit("stage", "오디오를 16 kHz 모노로 변환하는 중…")
        with tempfile.TemporaryDirectory(prefix="audio2text-") as folder:
            pcm_path = Path(folder) / "audio.pcm"
            decode_audio(path, pcm_path, self.cancel)
            pcm = np.memmap(pcm_path, dtype="<i2", mode="r")
            try:
                total = len(pcm)
                self.emit("duration", total / RATE)
                if speakers is not None:
                    from diarize import diarize
                    self.emit("stage", "화자 분석 중…")
                    spans = diarize(pcm, speakers, self.emit, self.cancel)
                    pending = [(start, end, label) for a, b, label in spans for start, end in chunks(pcm, a, b)]
                else:
                    pending = [(start, end, None) for start, end in chunks(pcm)]
                completed = []  # (speaker label or None, text)
                while pending:
                    check_cancel(self.cancel)
                    start, end, label = pending.pop(0)
                    self.emit("progress", (start / total * 100, start / RATE, total / RATE))
                    self.emit("stage", f"{start / RATE:.1f}–{end / RATE:.1f}초 구간 전사 중")
                    audio = np.asarray(pcm[start:end], dtype=np.float32) / 32768.0
                    if np.max(np.abs(audio)) < 1e-4:
                        text, truncated = "", False
                    else:
                        text, truncated = self.infer(audio, lambda text, count: self.emit(
                            "preview", (render(completed + [(label, text)]), count)))
                    if truncated and end - start <= 2 * RATE:  # too short to be dense speech: a decoding loop
                        text = collapse_repeats(text)
                    elif truncated:
                        middle = (start + end) // 2
                        pending[0:0] = [(start, middle, label), (middle, end, label)]
                        self.emit("preview", (render(completed), 0))
                        continue
                    if text:
                        completed.append((label, text))
                    self.emit("text", render(completed))
                    self.emit("progress", (end / total * 100, end / RATE, total / RATE))
                check_cancel(self.cancel)
                return render(completed)
            finally:
                pcm._mmap.close()

    def listen(self, device, stop, prefix="", wav_path=None, ffmpeg=None):
        """Live transcription: ffmpeg streams the microphone as 16 kHz PCM, the buffer is cut at pauses (split_point)
        and each segment is transcribed as soon as it closes. `stop` ends the recording and transcribes the tail;
        `self.cancel` aborts. The whole recording is also written to wav_path so nothing is lost."""
        command = [str(ffmpeg_path(ffmpeg)), "-hide_banner", "-loglevel", "error", "-nostdin", "-f", "dshow",
                   "-audio_buffer_size", "50", "-i", f"audio={device}", "-ac", "1", "-ar", str(RATE), "-f", "s16le", "pipe:1"]
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        recording = wave.open(str(wav_path), "wb") if wav_path else None
        if recording:
            recording.setnchannels(1)
            recording.setsampwidth(2)
            recording.setframerate(RATE)
        buffer, lock = bytearray(), threading.Lock()

        def pump():  # a reader thread keeps the pipe drained while Whisper runs, so ffmpeg never drops audio
            while True:
                data = process.stdout.read(RATE)  # 0.5 s
                if not data:
                    return
                with lock:
                    buffer.extend(data)
                if recording:
                    recording.writeframes(data)

        reader = threading.Thread(target=pump, daemon=True)
        reader.start()
        completed, seconds = [prefix.rstrip()] if prefix.strip() else [], 0.0

        def transcribe_segment(segment):
            nonlocal seconds
            seconds += len(segment) / RATE
            if np.sqrt(np.mean(segment.astype(np.float32) ** 2)) < SILENCE_RMS:
                return
            self.emit("stage", f"🎙 녹음 중 · {seconds:.0f}초 · 방금 구간 전사 중")
            audio = segment.astype(np.float32) / 32768.0
            text, truncated = self.infer(audio, lambda text, count: None)
            if truncated and len(audio) > 2 * RATE:  # a dense 20 s segment: transcribe the halves instead
                middle = len(audio) // 2
                text = " ".join(part for part in (self.infer(audio[:middle], lambda t, c: None)[0],
                                                  self.infer(audio[middle:], lambda t, c: None)[0]) if part)
            if text:
                completed.append(text)
                self.emit("text", "\n\n".join(completed))
            self.emit("stage", f"🎙 녹음 중 · {seconds:.0f}초")

        try:
            self.emit("stage", f"🎙 녹음 중 · {device}")
            while not stop.is_set():
                check_cancel(self.cancel)
                with lock:
                    pcm = np.frombuffer(bytes(buffer), dtype="<i2")
                    cut = split_point(pcm)
                    if cut:
                        del buffer[:cut * 2]
                if cut:
                    transcribe_segment(pcm[:cut])
                elif process.poll() is not None:
                    detail = process.stderr.read().decode("utf-8", errors="replace")[-1500:]
                    raise RuntimeError("마이크 입력이 끊겼습니다.\n" + detail)
                else:
                    self.cancel.wait(0.25)
            process.terminate()
            reader.join(3)
            with lock:
                tail = np.frombuffer(bytes(buffer), dtype="<i2")
                buffer.clear()
            if len(tail):
                transcribe_segment(tail)
            check_cancel(self.cancel)
            return "\n\n".join(completed)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait()
            reader.join(3)
            if recording:
                recording.close()

    def end_profiling(self):
        return [session.end_profiling() for session in self.sessions]


class WhisperGPU(WhisperNPU):
    """Same audio pipeline, but the standard Hugging Face ONNX export: encoder on the Adreno GPU through the QNN GPU
    backend, the 4-layer decoder with KV cache on the CPU (its per-token cost is small next to the 32-layer encoder)."""

    GPU_DIR = ROOT / "models" / "whisper-gpu"
    LIMIT = 200  # tokens per audio chunk, matching the NPU bundle so the chunk-splitting logic behaves identically

    def __init__(self, emit, cancel, model_dir=None, profile=False):
        if platform.machine().lower() != "arm64":
            raise RuntimeError("Windows ARM64 Python으로 실행해야 합니다. setup.cmd를 실행해 주세요.")
        import onnxruntime as ort
        from tokenizers import Tokenizer
        from transformers import WhisperFeatureExtractor

        self.emit, self.cancel = emit, cancel
        self.model_dir = Path(model_dir) if model_dir else ROOT / "models"
        gpu_dir = self.model_dir / "whisper-gpu"
        encoder_file = gpu_dir / "encoder_static_fp16.onnx"
        decoder_file = gpu_dir / "decoder_model_merged_fp16.onnx"
        if not encoder_file.is_file() or not decoder_file.is_file():
            raise RuntimeError("GPU용 Whisper 모델이 없습니다. setup.cmd를 실행해 주세요.")
        for name in ("tokenizer.json", "preprocessor_config.json", "generation_config.json"):
            if not (self.model_dir / name).is_file():
                raise RuntimeError(f"모델 파일이 없습니다: {name}\n처음 한 번 setup.cmd를 실행해 주세요.")
        # QNN 1.22's GPU backend cannot finalize this encoder. Keep that runtime for the compiled NPU bundle,
        # and run GPU jobs in the separate ORT + QNN plugin environment installed by setup.cmd.
        try:
            import onnxruntime_qnn as qnn
        except ImportError as error:
            raise RuntimeError("GPU 전사용 최신 QNN 환경이 필요합니다. setup.cmd를 실행한 뒤 앱에서 GPU를 선택해 주세요.") from error
        ort.disable_telemetry_events()
        self.dll_directory = os.add_dll_directory(str(Path(qnn.get_library_path()).parent))
        if "QNNExecutionProvider" not in ort.get_available_providers():
            ort.register_execution_provider_library("QNNExecutionProvider", qnn.get_library_path())
        devices = [device for device in ort.get_ep_devices() if device.ep_name == "QNNExecutionProvider"
                   and device.device.type == ort.OrtHardwareDeviceType.GPU]
        if not devices:
            raise RuntimeError("Adreno GPU를 찾지 못했습니다. GPU 드라이버를 확인해 주세요.")
        check_cancel(cancel)
        emit("stage", "GPU encoder 모델을 컴파일·로딩하는 중… (처음은 수 분)")
        options = ort.SessionOptions()
        options.add_session_config_entry("session.disable_cpu_ep_fallback", "1")
        options.enable_profiling = profile
        if profile:
            folder = ROOT / "diagnostics"
            folder.mkdir(exist_ok=True)
            options.profile_file_prefix = str(folder / "gpu-encoder")
        options.add_provider_for_devices(devices, {"backend_path": qnn.get_qnn_gpu_path()})
        try:
            self.encoder = ort.InferenceSession(str(encoder_file), sess_options=options)
        except Exception as error:
            raise RuntimeError(f"Whisper GPU 인코더 로딩 실패. setup.cmd로 GPU 환경을 갱신하거나 NPU를 선택해 주세요.\n{error}") from error
        self.encoder.disable_fallback()
        if "QNNExecutionProvider" not in self.encoder.get_providers():
            raise RuntimeError("GPU 세션 생성에 실패했습니다. Adreno 드라이버를 확인해 주세요.")
        self.encoder_dtype = np.float16 if self.encoder.get_inputs()[0].type == "tensor(float16)" else np.float32
        check_cancel(cancel)
        emit("stage", "decoder 모델을 불러오는 중…")
        decoder_options = ort.SessionOptions()
        decoder_options.enable_profiling = profile
        if profile:
            decoder_options.profile_file_prefix = str(folder / "gpu-decoder")
        self.decoder = ort.InferenceSession(str(decoder_file), sess_options=decoder_options, providers=["CPUExecutionProvider"])
        self.sessions = [self.encoder, self.decoder]
        self.decoder_inputs = [item.name for item in self.decoder.get_inputs()]
        self.decoder_outputs = [item.name for item in self.decoder.get_outputs()]
        self.limit = self.LIMIT
        self.tokenizer = Tokenizer.from_file(str(self.model_dir / "tokenizer.json"))
        self.extractor = WhisperFeatureExtractor.from_pretrained(str(self.model_dir), local_files_only=True)
        self.generation = json.loads((self.model_dir / "generation_config.json").read_text("utf-8"))
        self.prompt = [self.tokenizer.token_to_id(t) for t in
                       ("<|startoftranscript|>", "<|ko|>", "<|transcribe|>", "<|notimestamps|>")]
        self.eos = self.tokenizer.token_to_id("<|endoftext|>")
        if None in self.prompt or self.eos is None:
            raise RuntimeError("한국어 Whisper 토크나이저 구성이 올바르지 않습니다.")
        self.suppress = self.generation.get("suppress_tokens", [])
        emit("ready", "Adreno GPU (encoder) · CPU (decoder) · QNN GPU 백엔드")

    def infer(self, audio, preview):
        check_cancel(self.cancel)
        features = self.extractor(audio, sampling_rate=RATE, return_tensors="np")["input_features"]
        hidden = self.encoder.run(None, {"input_features": features.astype(self.encoder_dtype)})[0].astype(np.float32)
        feed = {"input_ids": np.array([self.prompt], dtype=np.int64), "encoder_hidden_states": hidden,
                "use_cache_branch": np.array([False])}
        for name in self.decoder_inputs:
            if name.startswith("past_key_values"):
                feed[name] = np.zeros((1, 20, 0, 64), dtype=np.float32)
        generated = []
        for position in range(self.limit):
            check_cancel(self.cancel)
            output = self.decoder.run(None, feed)
            present = dict(zip(self.decoder_outputs[1:], output[1:]))
            for name in self.decoder_inputs:
                if name.startswith("past_key_values") and (position == 0 or ".decoder." in name):
                    feed[name] = present[name.replace("past_key_values", "present")]
            feed["use_cache_branch"] = np.array([True])
            logits = output[0][0, -1].astype(np.float32)
            logits[self.eos + 1:] = -np.inf
            logits[self.suppress] = -np.inf
            if not generated:
                logits[self.generation.get("begin_suppress_tokens", [])] = -np.inf
            token = int(np.argmax(logits))
            if token == self.eos:
                return self.tokenizer.decode(generated, skip_special_tokens=True).strip(), False
            generated.append(token)
            feed["input_ids"] = np.array([[token]], dtype=np.int64)
            if len(generated) % 4 == 0:
                preview(self.tokenizer.decode(generated, skip_special_tokens=True).strip(), len(generated))
        return self.tokenizer.decode(generated, skip_special_tokens=True).strip(), True


def load_whisper(device, emit, cancel, **options):
    """'npu' = pre-compiled Hexagon bundle (default); 'gpu' = standard ONNX export on the Adreno GPU via QNN."""
    if device == "gpu":
        return WhisperGPU(emit, cancel, **options)
    if device == "npu":
        return WhisperNPU(emit, cancel, **options)
    raise ValueError("device must be 'npu' or 'gpu'")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Offline Korean transcription on Snapdragon NPU")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--profile", action="store_true")
    parser.add_argument("--device", choices=("npu", "gpu"), default="npu")
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output already exists; choose a new filename.")
    def report(kind, value):
        if kind not in ("text", "preview"):
            print(kind, value, flush=True)
    worker = load_whisper(args.device, report, threading.Event(), profile=args.profile)
    try:
        result = worker.transcribe(args.audio)
        with args.output.open("x", encoding="utf-8-sig") as target:
            target.write(result)
        print("Saved:", args.output)
    finally:
        if args.profile:
            print("Profiles:", worker.end_profiling())
