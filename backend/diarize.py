"""Speaker diarization on the Hexagon NPU: WeSpeaker ResNet34 speaker embeddings (ONNX through ONNX Runtime's QNN
execution provider) over windows of voiced frames, then clustering in NumPy. Runs inside .venv, next to Whisper.

Pipeline: energy VAD splits the recording into speech regions (pauses of 0.6 s or more) → each region's Kaldi-style
80-bin log-mel fbank frames (NumPy) are filtered to voiced frames only, because windows that contain pauses gave
embeddings that could not separate speakers → sliding windows of FRAMES voiced frames (about 2 s of speech, half
overlap) feed the fixed-shape graph → a window that drifts away from its running turn starts a new turn (a speaker
change without a pause) → average-linkage agglomerative clustering of turns by cosine similarity, stopping at
MERGE_THRESHOLD (the number of speakers is not asked) → speakers numbered by first appearance. Whisper then cuts its
chunks at these speaker changes so each chunk has one voice.
"""
import os
from pathlib import Path

import numpy as np

ROOT = Path(os.environ.get("SORIGUL_HOME") or Path(__file__).resolve().parent.parent)  # the app sets SORIGUL_HOME; dev: repo root
MODEL_DIR = ROOT / "models" / "speaker"
MODEL_FILE = "wespeaker_en_voxceleb_resnet34_LM.onnx"
RATE = 16000
FRAME, SHIFT, N_FFT, N_MELS = 400, 160, 512, 80          # Kaldi 25 ms / 10 ms at 16 kHz
FRAMES = 198                                             # voiced frames per embedding (~2 s of speech); graph is compiled for this
HOP_FRAMES = FRAMES // 2
MIN_FRAMES = 60                                          # a region with fewer voiced frames (0.6 s) gets no turn of its own
MIN_FRAGMENT = 20                                        # ...but from 0.2 s of speech it is still assigned to a neighbouring turn
BLOCK = RATE // 5                                        # 200 ms energy blocks for the VAD
PAUSE_BLOCKS = 3                                         # 0.6 s of quiet ends a speech region
MAX_REGION = 60 * RATE                                   # bounds fbank memory for pause-free speech
TURN_SIMILARITY = 0.50    # a window this close to the running turn mean belongs to it
MERGE_THRESHOLD = 0.50    # average cosine above which two clusters are one speaker (ResNet34-LM scale)
# ponytail: thresholds calibrated on this PC's TTS clips (same-speaker windows ~0.68, different ~0.26); expose them if
# real meetings over- or under-split.
MIN_TURN = 1.0            # seconds; shorter spans are absorbed by the previous speaker
MAX_SPEAKERS = 8


# ---- features -------------------------------------------------------------------------------------------------------
def mel_banks():
    """Kaldi-style triangular filters on the mel scale, 20 Hz .. Nyquist, over the N_FFT/2 + 1 rfft bins."""
    mel = lambda f: 1127.0 * np.log1p(f / 700.0)
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / RATE)
    points = np.linspace(mel(20.0), mel(RATE / 2), N_MELS + 2)
    m = mel(freqs)
    left, center, right = points[:-2, None], points[1:-1, None], points[2:, None]
    return np.maximum(0.0, np.minimum((m - left) / (center - left), (right - m) / (right - center))).astype(np.float32)


BANKS = mel_banks()
HAMMING = (0.54 - 0.46 * np.cos(2 * np.pi * np.arange(FRAME) / (FRAME - 1))).astype(np.float32)


def fbank(samples):
    """([frames, 80] log-mel energies, [frames] RMS) of int16-scale samples: DC removal, 0.97 pre-emphasis, Hamming,
    power spectrum, log with Kaldi's epsilon. Mean subtraction (WeSpeaker's CMN) is applied later per embedding."""
    x = np.asarray(samples, dtype=np.float32)
    count = (len(x) - FRAME) // SHIFT + 1
    if count < 1:
        raise ValueError("window too short")
    frames = np.lib.stride_tricks.as_strided(x, shape=(count, FRAME), strides=(x.strides[0] * SHIFT, x.strides[0])).copy()
    rms = np.sqrt(np.mean(frames ** 2, axis=1))
    frames -= frames.mean(axis=1, keepdims=True)
    frames[:, 1:] -= 0.97 * frames[:, :-1]
    frames[:, 0] *= 0.03
    frames *= HAMMING
    power = np.abs(np.fft.rfft(frames, n=N_FFT, axis=1)) ** 2
    return np.log(np.maximum(power @ BANKS.T, 1.1920929e-07)).astype(np.float32), rms


# ---- model ----------------------------------------------------------------------------------------------------------
def static_model(source, target):
    import onnx
    model = onnx.load(str(source))
    for tensor in list(model.graph.input) + list(model.graph.output):
        for index, dim in enumerate(tensor.type.tensor_type.shape.dim):
            if dim.dim_param or dim.dim_value == 0:
                dim.dim_param = ""
                dim.dim_value = 1 if index == 0 else FRAMES if index == 1 else dim.dim_value
    part = Path(target).with_suffix(".onnx.part")  # a killed setup never leaves a truncated model behind
    onnx.save(model, str(part))
    part.replace(target)


class SpeakerEmbedder:
    def __init__(self, device="npu", model_dir=MODEL_DIR, emit=lambda kind, value: None):
        import onnxruntime as ort
        source = Path(model_dir) / MODEL_FILE
        if not source.is_file():
            raise RuntimeError("화자 분리 모델이 없습니다. setup.cmd를 실행해 주세요.")
        target = Path(model_dir) / f"speaker_static_{FRAMES}.onnx"
        if not target.is_file():
            emit("stage", "화자 분리 모델 고정 형태로 변환 중… (처음 한 번)")
            static_model(source, target)
        ort.disable_telemetry_events()
        options = ort.SessionOptions()
        options.log_severity_level = 3
        if device == "cpu":
            emit("stage", "화자 분리 모델을 CPU에 올리는 중…")
            self.session = ort.InferenceSession(str(target), sess_options=options, providers=["CPUExecutionProvider"])
        else:
            capi = Path(ort.__file__).parent / "capi"
            self.dll_directory = os.add_dll_directory(str(capi))
            backend = {"npu": "QnnHtp.dll", "gpu": "QnnGpu.dll"}[device]
            provider = {"backend_path": str(capi / backend), "htp_performance_mode": "burst", "enable_htp_fp16_precision": "1"}
            emit("stage", f"화자 분리 모델을 {'NPU' if device == 'npu' else 'GPU'}에 올리는 중…")
            # Convolutions and pooling are QNN-supported; only shape/cast glue may fall to the CPU, which is accepted.
            self.session = ort.InferenceSession(str(target), sess_options=options,
                                                providers=[("QNNExecutionProvider", provider), "CPUExecutionProvider"])
            if "QNNExecutionProvider" not in self.session.get_providers():
                raise RuntimeError("화자 분리 세션이 QNN에서 열리지 않았습니다.")
        self.input_name = self.session.get_inputs()[0].name

    def embed(self, features):
        """L2-normalised 256-d embedding of [n, 80] voiced fbank frames; fewer than FRAMES frames are tiled."""
        if len(features) < FRAMES:
            features = np.tile(features, (FRAMES // len(features) + 1, 1))
        features = features[:FRAMES]
        features = features - features.mean(axis=0, keepdims=True)
        vector = self.session.run(None, {self.input_name: features[None].astype(np.float32)})[0][0].astype(np.float32)
        return vector / max(float(np.linalg.norm(vector)), 1e-12)


# ---- segmentation ---------------------------------------------------------------------------------------------------
def quiet_threshold(pcm):
    """Energy below which a 200 ms block is silence: the same rule Whisper chunking uses (absolute floor or 8% of the
    recording's median block energy)."""
    usable = len(pcm) - len(pcm) % BLOCK
    if usable < BLOCK:
        return 32.0 ** 2
    energy = np.mean(np.asarray(pcm[:usable], dtype=np.float32).reshape(-1, BLOCK) ** 2, axis=1)
    return max(32.0 ** 2, float(np.median(energy)) * 0.08)


def speech_regions(pcm, threshold):
    """[(start_sample, end_sample)] of speech separated by at least PAUSE_BLOCKS quiet blocks, each at most MAX_REGION."""
    usable = len(pcm) - len(pcm) % BLOCK
    if usable < BLOCK:
        return [(0, len(pcm))] if len(pcm) else []
    energy = np.mean(np.asarray(pcm[:usable], dtype=np.float32).reshape(-1, BLOCK) ** 2, axis=1)
    voiced = energy >= threshold
    regions, start, quiet = [], None, 0
    for index, on in enumerate(voiced):
        if on:
            if start is None:
                start = index
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet >= PAUSE_BLOCKS:
                regions.append((start * BLOCK, (index - quiet + 1) * BLOCK))
                start, quiet = None, 0
    if start is not None:
        regions.append((start * BLOCK, len(pcm)))
    # Soft onsets ("네", "Sure") sit below the speech threshold but well above silence: extend each region's start
    # backwards over merely audible blocks (1% of median energy), never into the previous region.
    audible = energy >= threshold / 8
    for index in range(len(regions)):
        block, floor = regions[index][0] // BLOCK, (regions[index - 1][1] // BLOCK) if index else 0
        while block > floor and audible[block - 1]:
            block -= 1
        regions[index] = (block * BLOCK, regions[index][1])
    bounded = []
    for start, end in regions:
        while end - start > MAX_REGION:
            bounded.append((start, start + MAX_REGION))
            start += MAX_REGION
        bounded.append((start, end))
    return bounded


def cluster(vectors, threshold=MERGE_THRESHOLD, max_clusters=MAX_SPEAKERS):
    """Average-linkage agglomerative clustering on cosine similarity. With unit vectors the average pairwise similarity
    between two clusters equals the dot product of their vector sums divided by their sizes, so no pairwise matrix of
    members is kept. Returns a label per vector."""
    vectors = np.asarray(vectors, dtype=np.float32)
    labels = np.arange(len(vectors))
    sums, counts = vectors.copy(), np.ones(len(vectors))
    while len(sums) > 1:
        similarity = (sums @ sums.T) / np.outer(counts, counts)
        np.fill_diagonal(similarity, -np.inf)
        a, b = np.unravel_index(int(np.argmax(similarity)), similarity.shape)
        if similarity[a, b] < threshold and len(sums) <= max_clusters:
            break
        a, b = min(a, b), max(a, b)
        sums[a] += sums[b]
        counts[a] += counts[b]
        sums, counts = np.delete(sums, b, axis=0), np.delete(counts, b)
        labels[labels == b] = a
        labels[labels > b] -= 1
    return labels


def region_turns(pcm, start, end, threshold, embedder):
    """[(start_sample, end_sample, mean_vector)] for one speech region: windows over its voiced frames, split into a
    new turn when a window no longer resembles the running turn."""
    features, rms = fbank(pcm[start:end])
    voiced = np.flatnonzero(rms >= np.sqrt(threshold))
    if len(voiced) < MIN_FRAMES:
        # Too short to cluster on its own ("네", "Sure"): a tiled embedding still tells which neighbour it resembles.
        return [], (embedder.embed(features[voiced]) if len(voiced) >= MIN_FRAGMENT else None)
    turns, previous = [], None
    for offset in range(0, len(voiced), HOP_FRAMES):
        indices = voiced[offset:offset + FRAMES]
        if offset and len(indices) < HOP_FRAMES:
            break  # the previous window already covered this tail
        vector = embedder.embed(features[indices])
        last = start + int(indices[-1]) * SHIFT + FRAME
        if turns:
            total = turns[-1][2]
            if float(vector @ (total / max(float(np.linalg.norm(total)), 1e-12))) >= TURN_SIMILARITY:
                turns[-1] = (turns[-1][0], last, total + vector)
                previous = indices
                continue
            # A speaker change inside the region: cut at the longest silence between the two windows' starts,
            # or halfway between them when nobody paused (windows overlap by half, so the change lies in between).
            span = voiced[(voiced >= previous[0]) & (voiced <= indices[0])]
            gaps = np.diff(span)
            if len(gaps) and gaps.max() >= 10:
                cut = int(span[int(np.argmax(gaps))]) + 1
            else:
                cut = (int(previous[0]) + int(indices[0])) // 2
            first = start + cut * SHIFT
            turns[-1] = (turns[-1][0], first, total)
        else:
            first = start  # the region's onset (soft first syllables under the frame gate) belongs to its first turn
        turns.append((first, last, vector.copy()))
        previous = indices
    return [(a, b, total / max(float(np.linalg.norm(total)), 1e-12)) for a, b, total in turns], None


def diarize(pcm, embedder, emit=lambda kind, value: None, cancel=None):
    """[(start_sample, end_sample, speaker_index)] covering the whole recording, speakers numbered by first appearance.
    Pauses and regions too short to embed are attached to the preceding speaker."""
    total = len(pcm)
    threshold = quiet_threshold(pcm)
    turns, fragments = [], []
    regions = speech_regions(pcm, threshold)
    for number, (start, end) in enumerate(regions):
        if cancel is not None and cancel.is_set():
            raise RuntimeError("취소됨")
        found, fragment = region_turns(pcm, start, end, threshold, embedder)
        turns += found
        if not found and fragment is not None:
            fragments.append((start, end, fragment))
        if number % 20 == 0:
            emit("stage", f"화자 분석 중 · {start / RATE:.0f}/{total / RATE:.0f}초")
    if not turns:
        return [(0, total, 0)]
    labels = cluster(np.asarray([vector for _, _, vector in turns]))
    spans = [[start, end, int(label)] for (start, end, _), label in zip(turns, labels)]
    # A short utterance joins whichever neighbouring turn it sounds like (its label), not merely the earlier one.
    for start, end, vector in fragments:
        index = sum(1 for turn in turns if turn[0] < start)
        neighbours = [k for k in (index - 1, index) if 0 <= k < len(turns)]
        best = max(neighbours, key=lambda k: float(vector @ turns[k][2]))
        spans.append([start, end, int(labels[best])])
    spans.sort(key=lambda span: span[0])
    spans[0][0] = 0
    for index in range(1, len(spans)):
        spans[index - 1][1] = spans[index][0]  # a span runs until the next one starts (pauses go to the earlier voice)
    spans[-1][1] = total
    merged = []
    for start, end, label in spans:
        if merged and (end - start < MIN_TURN * RATE or merged[-1][2] == label):
            merged[-1][1] = end
        else:
            merged.append([start, end, label])
    order = {}
    for span in merged:
        span[2] = order.setdefault(span[2], len(order))
    return [tuple(span) for span in merged]
