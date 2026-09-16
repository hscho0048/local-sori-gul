"""One-time public model download; never imports or uploads user audio."""
import hashlib
import argparse
import os
from pathlib import Path
import sysconfig
import urllib.request
import zipfile

CODE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get("SORIGUL_HOME") or CODE)

# The interpreter's own architecture: an x64 build running under emulation on an ARM64 PC reports machine() == "ARM64".
ARM64 = sysconfig.get_platform() == "win-arm64"

MODEL_REV = "7fbb62e962d1bda945b81fbc3b048e5bb5773cf0"
TOKENIZER_REV = "41f01f3fe87f28c78e2fbf8b568835947dd65ed9"
BASE = f"https://huggingface.co/FluidInference/whisper-large-v3-turbo-qnn/resolve/{MODEL_REV}/snapdragon-x-elite"
FILES = {
    "encoder/model.onnx": "459ef81b6bd2b17384880eee32f25973a0997612cdcda6244da0b95b3f0e5d36",
    "decoder/model.onnx": "27f668a1f12349c4b4ee644598a98762e6de3b4fc4c488a1e56e5c6d52cf21b3",
    "encoder/model.bin": "91d2d7a5cfd9774624535a18a59929f9cf653a23ee2dc8c1f4aa4dbc7460c366",
    "decoder/model.bin": "65df570c3e5fa5107e8d7e7c9ae66bea35823cf76974dacfaa5966ff7c3ad199",
}


# Speaker diarization embeddings (WeSpeaker ResNet34-LM, VoxCeleb). Runs on the NPU next to Whisper; see diarize.py.
SPEAKER_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/wespeaker_en_voxceleb_resnet34_LM.onnx"
SPEAKER_SHA = "e9848563da86f263117134dfd7ad63c92355b37de492b55e325400c9d9c39012"

GPU_REV = "360ebcde2559d60bb474678be3c1de9ef347d01a"
GPU_BASE = f"https://huggingface.co/onnx-community/whisper-large-v3-turbo/resolve/{GPU_REV}/onnx"
GPU_FILES = {
    "encoder_model_fp16.onnx": "fdadc70836e6b028fd5e580417c312208dad073d2d01e509e2d127c1373399d8",
    "decoder_model_merged_fp16.onnx": "fdf10afca73a0c7bf87286cfb96cf7028a9edbc9bb02512509a526f95b126c9d",
}


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


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
    return (list(FILES) if ARM64 else []) + names


def download(url, target, sha=None, emit=log):
    target.parent.mkdir(parents=True, exist_ok=True)
    name = target.relative_to(ROOT).as_posix()
    if target.exists() and sha:
        emit("stage", f"{name} 확인 중…")  # hashing a GB-sized model takes a few seconds
    if target.exists() and (not sha or digest(target) == sha):
        emit("ready", name)
        return
    partial = target.with_suffix(target.suffix + ".part")
    emit("file", name)
    offset = partial.stat().st_size if partial.exists() else 0
    headers = {"User-Agent": "audio2text-local/1.0"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as source:
        if source.status != 206:
            offset = 0
        size = int(source.headers.get("Content-Length", 0)) + offset
        received = offset
        last = -1
        with partial.open("ab" if offset else "wb") as out:
            while chunk := source.read(4 * 1024 * 1024):
                out.write(chunk)
                received += len(chunk)
                progress = received * 100 // size if size else 0
                if progress != last:
                    emit("progress", (progress, received // 1048576, size // 1048576))
                    last = progress
        if size and received != size:
            raise RuntimeError(f"Incomplete download: {target.name}")
    if sha and digest(partial) != sha:
        partial.unlink()
        raise RuntimeError(f"Checksum mismatch: {target.name}; run setup again.")
    partial.replace(target)
    emit("ready", name)


def setup_whisper_gpu(emit=log):
    import onnx
    folder = ROOT / "models" / "whisper-gpu"
    target = folder / "encoder_static_fp16.onnx"
    decoder = "decoder_model_merged_fp16.onnx"
    download(f"{GPU_BASE}/{decoder}", folder / decoder, GPU_FILES[decoder], emit=emit)
    if target.is_file():
        model = onnx.load(str(target), load_external_data=False)
        shape = [d.dim_value for d in model.graph.input[0].type.tensor_type.shape.dim]
        if shape == [1, 128, 3000]:
            emit("ready", "whisper-gpu/encoder_static_fp16.onnx")
            return
    source = folder / "encoder_model_fp16.onnx"
    download(f"{GPU_BASE}/{source.name}", source, GPU_FILES[source.name], emit=emit)
    emit("stage", "GPU 인코더를 고정 형태로 변환하는 중…")
    model = onnx.load(str(source))
    for value, shape in [(model.graph.input[0], (1, 128, 3000)), (model.graph.output[0], (1, 1500, 1280))]:
        for dim, size in zip(value.type.tensor_type.shape.dim, shape):
            dim.dim_value = size
    partial = target.with_suffix(".onnx.part")
    onnx.save(model, str(partial))
    partial.replace(target)
    emit("ready", "whisper-gpu/encoder_static_fp16.onnx")


def main(emit=log, whisper_gpu=False):
    """Every model this machine needs, then (with whisper_gpu) the static-shape encoder. Files already present with
    the right checksum are skipped, so an interrupted first run resumes."""
    if ARM64:
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
        wheel = ROOT / "tools" / "ffmpeg.whl"
        download("https://files.pythonhosted.org/packages/2c/c6/fa760e12a2483469e2bf5058c5faff664acf66cadb4df2ad6205b016a73d/imageio_ffmpeg-0.6.0-py3-none-win_amd64.whl", wheel,
                 "02fa47c83703c37df6bfe4896aab339013f62bf02c5ebf2dce6da56af04ffc0a", emit=emit)
        with zipfile.ZipFile(wheel) as archive:
            exe = next(n for n in archive.namelist() if n.endswith(".exe"))
            (ROOT / "tools" / "ffmpeg.exe").write_bytes(archive.read(exe))
            for name in archive.namelist():
                if "license" in name.lower() and not name.endswith("/"):
                    (ROOT / "tools" / Path(name).name).write_bytes(archive.read(name))
    if whisper_gpu:
        setup_whisper_gpu(emit)
    emit("stage", "Setup complete. Inference needs no network.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--whisper-gpu", action="store_true")
    if parser.parse_args().whisper_gpu:
        setup_whisper_gpu()
    else:
        main()
