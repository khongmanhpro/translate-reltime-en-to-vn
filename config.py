"""🎛️ Configuration for DichTuDong - Real-time Meeting Translator."""

import os
from pathlib import Path

# ───── STT Engine Selection ─────
STT_ENGINE: str = os.getenv("STT_ENGINE", "whisper")  # "whisper" | "mimo"

# ───── STT: Whisper (local) ─────
STT_MODEL_SIZE: str = os.getenv("STT_MODEL_SIZE", "medium")  # tiny/base/small/medium/large-v3
STT_DEVICE: str = os.getenv("STT_DEVICE", "auto")  # auto/cuda/cpu
STT_COMPUTE_TYPE: str = os.getenv("STT_COMPUTE_TYPE", "auto")  # auto/float16/int8/float32
STT_LANGUAGE: str = os.getenv("STT_LANGUAGE", "en")  # Source language

# ───── STT: MiMo ASR API ─────
MIMO_API_KEY: str = os.getenv("MIMO_API_KEY", "")
MIMO_BASE_URL: str = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
MIMO_MODEL: str = os.getenv("MIMO_MODEL", "mimo-v2.5-asr")

# ───── Translation ─────
DEEPL_API_KEY: str = os.getenv("DEEPL_API_KEY", "")  # Free key or pro key
DEEPL_API_URL: str = os.getenv("DEEPL_API_URL", "https://api-free.deepl.com/v2/translate")
TARGET_LANG: str = os.getenv("TARGET_LANG", "VI")  # DeepL target language code
# Fallback: argos-translate (offline)
USE_ARGOS_FALLBACK: bool = os.getenv("USE_ARGOS_FALLBACK", "true").lower() == "true"

# ───── TTS (edge-tts) ─────
TTS_ENABLED: bool = os.getenv("TTS_ENABLED", "false").lower() == "true"
TTS_VOICE: str = os.getenv("TTS_VOICE", "vi-VN-HoaiMyNeural")  # vi-VN-NamMinhNeural

# ───── Audio ─────
AUDIO_RATE: int = int(os.getenv("AUDIO_RATE", "16000"))
CHUNK_SIZE: int = int(os.getenv("CHUNK_SIZE", "4000"))
MIN_AUDIO_SEC: float = float(os.getenv("MIN_AUDIO_SEC", "2.0"))
MAX_BUFFER_SECONDS: int = int(os.getenv("MAX_BUFFER_SECONDS", "8"))
MIN_VOLUME: float = float(os.getenv("MIN_VOLUME", "0.005"))

# ───── Database ─────
DB_PATH: Path = Path(os.getenv("DB_PATH", "data/transcripts.db"))

# ───── Server ─────
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8765"))

# ───── Logging ─────
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
LOG_PATH: Path = Path(os.getenv("LOG_PATH", "data/logs/app.log"))
