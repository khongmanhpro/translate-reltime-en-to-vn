"""🎤 STT Module: faster-whisper (local) hoặc MiMo-v2.5-ASR (API).

Chọn engine qua biến môi trường STT_ENGINE:
  STT_ENGINE=whisper  → dùng faster-whisper chạy local (mặc định)
  STT_ENGINE=mimo     → dùng mimo-v2.5-asr qua Xiaomi MiMo API
"""

import io
import queue
import struct
import threading
import wave
import base64
import json
import urllib.request
import urllib.error
import numpy as np
from typing import Callable, Optional
from loguru import logger
from config import (
    STT_ENGINE,
    STT_MODEL_SIZE, STT_DEVICE, STT_COMPUTE_TYPE, STT_LANGUAGE,
    MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL,
    AUDIO_RATE, MIN_AUDIO_SEC, MAX_BUFFER_SECONDS, MIN_VOLUME,
)


# ─────────────────────────────────────────────
# Deduplicator (dùng chung cho cả 2 engine)
# ─────────────────────────────────────────────
class TranscriptDeduplicator:
    """Filter duplicate transcriptions."""

    def __init__(self):
        self.last_text = ""
        self.history: set[str] = set()
        self._lock = threading.Lock()

    def is_duplicate(self, text: str) -> bool:
        text = text.strip()
        if not text or len(text.split()) < 2:
            return True
        with self._lock:
            if text == self.last_text or text in self.history:
                return True
            self.last_text = text
            self.history.add(text)
            # Keep history bounded
            if len(self.history) > 500:
                self.history = set(list(self.history)[-200:])
        return False


# ─────────────────────────────────────────────
# Engine 1: Whisper (local)
# ─────────────────────────────────────────────
class WhisperSTTEngine:
    """Speech-to-text using faster-whisper (chạy local, CPU/GPU)."""

    def __init__(self):
        self.model = None
        self._load_model()

    def _resolve_device(self) -> str:
        if STT_DEVICE != "auto":
            return STT_DEVICE
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            return "cpu"

    def _resolve_compute_type(self) -> str:
        if STT_COMPUTE_TYPE != "auto":
            return STT_COMPUTE_TYPE
        return "float16" if self._resolve_device() == "cuda" else "int8"

    def _load_model(self):
        try:
            from faster_whisper import WhisperModel
            device  = self._resolve_device()
            compute = self._resolve_compute_type()
            logger.info(f"📦 Loading Whisper '{STT_MODEL_SIZE}' on {device} ({compute})...")
            self.model = WhisperModel(STT_MODEL_SIZE, device=device, compute_type=compute)
            logger.info("✅ Whisper model loaded")
        except Exception as e:
            logger.error(f"❌ Failed to load Whisper model: {e}")
            raise

    def transcribe(self, audio: np.ndarray) -> list[dict]:
        """Transcribe audio array → list of segment dicts."""
        if self.model is None:
            return []
        try:
            segments, _ = self.model.transcribe(
                audio,
                language=STT_LANGUAGE,
                beam_size=5,
                vad_filter=True,
            )
            results = []
            for seg in segments:
                text = seg.text.strip()
                if text:
                    results.append({"text": text, "start": seg.start, "end": seg.end})
            return results
        except Exception as e:
            logger.error(f"❌ Whisper transcription error: {e}")
            return []


# ─────────────────────────────────────────────
# Engine 2: MiMo-v2.5-ASR (API)
# ─────────────────────────────────────────────
class MiMoSTTEngine:
    """Speech-to-text using Xiaomi MiMo-v2.5-ASR API."""

    def __init__(self):
        if not MIMO_API_KEY:
            raise EnvironmentError(
                "❌ MIMO_API_KEY chưa được set!\n"
                "   Lấy key tại: https://platform.xiaomimimo.com/"
            )
        logger.info(f"✅ MiMo ASR engine khởi tạo (model: {MIMO_MODEL})")
        logger.info(f"   Endpoint: {MIMO_BASE_URL}")

    def _numpy_to_wav_bytes(self, audio: np.ndarray) -> bytes:
        """Chuyển numpy float32 array → WAV bytes (16kHz, mono, 16-bit)."""
        pcm = (audio * 32767).astype(np.int16)
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(AUDIO_RATE)
            wf.writeframes(pcm.tobytes())
        return buf.getvalue()

    def transcribe(self, audio: np.ndarray) -> list[dict]:
        """Gọi MiMo ASR API, trả về list segment dicts."""
        try:
            # Chuyển audio → WAV → base64 Data URL
            wav_bytes = self._numpy_to_wav_bytes(audio)
            b64       = base64.b64encode(wav_bytes).decode("ascii")
            data_url  = f"data:audio/wav;base64,{b64}"

            # Kiểm tra kích thước (giới hạn 10MB)
            size_mb = len(b64) / (1024 * 1024)
            if size_mb > 9.5:
                logger.warning(f"⚠️ Audio quá lớn ({size_mb:.1f}MB), bỏ qua chunk này")
                return []

            payload = {
                "model": MIMO_MODEL,
                "messages": [{
                    "role": "user",
                    "content": [{
                        "type": "input_audio",
                        "input_audio": {
                            "data":   data_url,
                            "format": "audio/wav",
                        },
                    }],
                }],
            }

            url     = f"{MIMO_BASE_URL}/chat/completions"
            headers = {
                "Authorization": f"Bearer {MIMO_API_KEY}",
                "Content-Type":  "application/json",
            }
            body = json.dumps(payload).encode("utf-8")
            req  = urllib.request.Request(url, data=body, headers=headers, method="POST")

            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read().decode("utf-8"))

            text = result["choices"][0]["message"]["content"].strip()
            # Lọc các tag đặc biệt model trả về khi không có speech
            if not text or text in ("<chinese>", "<english>", "<noise>", "<silence>"):
                return []

            logger.debug(f"🌐 MiMo ASR: {text[:80]}")
            return [{"text": text, "start": 0.0, "end": 0.0}]

        except urllib.error.HTTPError as e:
            logger.error(f"❌ MiMo API HTTP {e.code}: {e.read().decode()[:200]}")
            return []
        except Exception as e:
            logger.error(f"❌ MiMo ASR error: {e}")
            return []


# ─────────────────────────────────────────────
# Factory: chọn engine theo config
# ─────────────────────────────────────────────
def create_stt_engine():
    """Tạo STT engine dựa trên STT_ENGINE env var."""
    engine = STT_ENGINE.lower().strip()
    if engine == "mimo":
        logger.info("🤖 STT Engine: MiMo-v2.5-ASR (API)")
        return MiMoSTTEngine()
    else:
        logger.info("🖥️  STT Engine: Whisper (local)")
        return WhisperSTTEngine()


# Alias để tương thích ngược với code cũ
STTEngine = WhisperSTTEngine


# ─────────────────────────────────────────────
# AudioProcessor (không đổi logic, chỉ dùng factory)
# ─────────────────────────────────────────────
class AudioProcessor:
    """Process audio stream and emit transcribed text."""

    def __init__(self, on_text: Callable[[str], None]):
        self.on_text    = on_text
        self.audio_queue: queue.Queue = queue.Queue()
        self.running    = False
        self.buffer: list[np.ndarray] = []
        self.dedup      = TranscriptDeduplicator()
        self.stt        = create_stt_engine()
        self._thread: Optional[threading.Thread] = None

    def feed_audio(self, audio_chunk: np.ndarray):
        """Feed raw audio chunk (float32, mono, 16kHz)."""
        self.audio_queue.put(audio_chunk)

    def start(self):
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        logger.info("🎤 AudioProcessor started")

    def stop(self):
        self.running = False
        logger.info("🛑 AudioProcessor stopped")

    def _loop(self):
        min_samples = int(AUDIO_RATE * MIN_AUDIO_SEC)
        max_samples = int(AUDIO_RATE * MAX_BUFFER_SECONDS)

        while self.running:
            try:
                chunk = self.audio_queue.get(timeout=1)
            except queue.Empty:
                continue

            # Volume gate
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            if rms < MIN_VOLUME:
                continue

            self.buffer.append(chunk)
            full = np.concatenate(self.buffer, axis=0)

            if len(full) < min_samples:
                continue

            if len(full) > max_samples:
                logger.warning("🧹 Buffer overflow, forcing transcription")

            # Transcribe
            segments = self.stt.transcribe(full)
            for seg in segments:
                text = seg["text"]
                if not self.dedup.is_duplicate(text):
                    logger.info(f"🗣️ STT: {text}")
                    self.on_text(text)

            self.buffer = []
