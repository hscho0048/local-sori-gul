"""System sound (WASAPI loopback of the default output device), optionally mixed with a microphone, as 16 kHz mono
s16le on stdout until killed. Stdlib ctypes COM; the engine reads it exactly like its ffmpeg microphone stream.

    python loopback.py              system sound only
    python loopback.py --mic NAME   system sound + the capture device with that name (else the default one)
"""
import argparse
import ctypes
from ctypes import HRESULT, POINTER, byref, c_int64, c_uint16, c_uint32, c_uint64, c_void_p
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
    # vt + 3 reserved WORDs + 16-byte union = 24 bytes on 64-bit
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
        try:
            return ctypes.wstring_at(value.value) if value.value else ""
        finally:
            ctypes.oledll.ole32.PropVariantClear(byref(value))
    finally:
        release(store)


def endpoint(enumerator, flow, name=None):
    """The active endpoint whose friendly name matches `name` (DirectShow uses the same names), else the default."""
    if name:
        collection, count = c_void_p(), c_uint32()
        call(enumerator, 3, (c_uint32, flow), (c_uint32, DEVICE_STATE_ACTIVE), (POINTER(c_void_p), byref(collection)))
        try:
            call(collection, 3, (POINTER(c_uint32), byref(count)))
            for index in range(count.value):
                device = c_void_p()
                call(collection, 4, (c_uint32, index), (POINTER(c_void_p), byref(device)))
                label = friendly_name(device)
                if label and (label.startswith(name) or name.startswith(label)):
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
        release(device)
        pcm = WAVEFORMATEX(1, 1, RATE, RATE * 2, 2, 16, 0)
        flags = AUTOCONVERTPCM | SRC_DEFAULT_QUALITY | (LOOPBACK if loopback else 0)
        call(self.client, 3, (c_uint32, 0), (c_uint32, flags), (c_int64, 2_000_000), (c_int64, 0),
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
                 (POINTER(c_uint32), byref(flags)), (POINTER(c_uint64), None), (POINTER(c_uint64), None))  # GetBuffer
            if flags.value & SILENT or not data.value:
                chunks.append(np.zeros(frames.value, dtype=np.int16))
            else:
                chunks.append(np.frombuffer(ctypes.string_at(data.value, frames.value * 2), dtype=np.int16))
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
    ole32 = ctypes.oledll.ole32
    ole32.CoInitializeEx(None, 0)  # S_FALSE (already initialised) is fine; failures raise
    enumerator = c_void_p()
    ole32.CoCreateInstance(byref(CLSID_MMDeviceEnumerator), None, CLSCTX_ALL, byref(IID_IMMDeviceEnumerator),
                           byref(enumerator))
    system = Capture(endpoint(enumerator, E_RENDER), loopback=True)
    mic = Capture(endpoint(enumerator, E_CAPTURE, args.mic), loopback=False) if args.mic is not None else None
    out = sys.stdout.buffer
    start, produced, produced_mic = time.monotonic(), 0, 0
    pending_system = pending_mic = np.zeros(0, dtype=np.int16)
    # ponytail: 10 ms polling instead of event handles (~1% of a core); switch to SetEventHandle if CPU use shows up.
    while True:
        time.sleep(0.01)
        expected = int((time.monotonic() - start) * RATE)
        chunk = pad(system.read(), produced, expected, RATE // 10)
        produced += len(chunk)
        if mic is None:
            block = chunk
        else:
            voice = pad(mic.read(), produced_mic, expected, RATE // 10)  # a stalled mic must not stall the mix
            produced_mic += len(voice)
            pending_system = np.concatenate([pending_system, chunk])
            pending_mic = np.concatenate([pending_mic, voice])
            block, pending_system, pending_mic = mix(pending_system, pending_mic)
        if len(block):
            try:
                out.write(block.tobytes())
                out.flush()
            except OSError:  # includes BrokenPipeError: the engine is gone
                return


if __name__ == "__main__":
    main()
