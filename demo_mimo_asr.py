"""
🎤 Demo: MiMo-V2.5-ASR via Xiaomi MiMo API Platform
=====================================================
Thay thế faster-whisper bằng mimo-v2.5-asr qua HTTP API.

Setup:
  1. Lấy API key tại: https://platform.xiaomimimo.com/ → Console → API Keys
  2. Điền MIMO_API_KEY vào file .env
  3. Chạy: python3 demo_mimo_asr.py [audio_file.wav]

Yêu cầu file audio:
  - Định dạng: WAV hoặc MP3
  - Kích thước: tối đa 10MB (sau khi base64 encode)
"""

import os
import sys
import json
import base64
import urllib.request
import urllib.error
from pathlib import Path

# ───── Đọc .env file nếu có ─────
def _load_env():
    env_file = Path(__file__).parent / ".env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, val = line.partition("=")
                if key.strip() and val.strip() and key.strip() not in os.environ:
                    os.environ[key.strip()] = val.strip()

_load_env()


# ───── Cấu hình API (đọc từ .env) ─────
MIMO_API_KEY  = os.getenv("MIMO_API_KEY", "")
MIMO_BASE_URL = os.getenv("MIMO_BASE_URL", "https://api.xiaomimimo.com/v1")
MIMO_MODEL    = os.getenv("MIMO_MODEL", "mimo-v2.5-asr")


def encode_audio(file_path: str) -> tuple[str, str]:
    """
    Đọc file audio và encode sang base64 Data URL.
    Trả về (data_url, mime_type).
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File không tồn tại: {file_path}")

    suffix = path.suffix.lower()
    mime_map = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
    }
    mime_type = mime_map.get(suffix)
    if not mime_type:
        raise ValueError(f"Định dạng không hỗ trợ: {suffix}. Chỉ dùng .wav hoặc .mp3")

    raw_bytes = path.read_bytes()
    size_mb   = len(raw_bytes) / (1024 * 1024)
    print(f"📁 File: {path.name} ({size_mb:.2f} MB)")

    if size_mb > 7.5:  # base64 tăng ~33% → giới hạn an toàn
        raise ValueError(f"File quá lớn ({size_mb:.1f} MB). Tối đa ~7.5 MB để sau encode ≤ 10 MB")

    b64 = base64.b64encode(raw_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{b64}"
    return data_url, mime_type


def transcribe(audio_path: str, language: str = "en") -> dict:
    """
    Gọi MiMo-v2.5-ASR API để nhận dạng giọng nói.

    Args:
        audio_path: Đường dẫn file .wav hoặc .mp3
        language:   Ngôn ngữ nguồn (en / zh / yue / vi ...)

    Returns:
        dict với keys: text, model, usage
    """
    if not MIMO_API_KEY:
        raise EnvironmentError(
            "❌ Thiếu MIMO_API_KEY!\n"
            "   Lấy key tại: https://platform.xiaomimimo.com/\n"
            "   Rồi chạy: export MIMO_API_KEY='your_key_here'"
        )

    # Encode audio → base64 Data URL
    data_url, mime_type = encode_audio(audio_path)

    # Tạo request payload theo chuẩn OpenAI multimodal
    payload = {
        "model": MIMO_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": data_url,
                            "format": mime_type,
                        },
                    }
                ],
            }
        ],
    }

    # HTTP Request
    url     = f"{MIMO_BASE_URL}/chat/completions"
    headers = {
        "Authorization": f"Bearer {MIMO_API_KEY}",
        "Content-Type":  "application/json",
    }
    body = json.dumps(payload).encode("utf-8")

    print(f"🌐 Gọi API: {url}")
    print(f"🤖 Model  : {MIMO_MODEL}")
    print("⏳ Đang nhận dạng...")

    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        raise RuntimeError(f"❌ HTTP {e.code}: {error_body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"❌ Lỗi kết nối: {e.reason}")

    # Parse kết quả
    text  = result["choices"][0]["message"]["content"]
    usage = result.get("usage", {})

    return {
        "text":  text,
        "model": result.get("model", MIMO_MODEL),
        "usage": usage,
    }


def generate_test_wav(output_path: str = "test_audio.wav") -> str:
    """
    Tạo file WAV test với âm thanh sine wave (nếu không có file sẵn).
    Dùng để kiểm tra kết nối API mà không cần mic.
    """
    import wave
    import struct
    import math

    sample_rate = 16000
    duration    = 2  # giây
    frequency   = 440  # Hz (nốt La)

    samples = []
    for i in range(int(sample_rate * duration)):
        val = int(32767 * math.sin(2 * math.pi * frequency * i / sample_rate))
        samples.append(struct.pack("<h", val))

    with wave.open(output_path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(samples))

    print(f"✅ Đã tạo file test: {output_path}")
    return output_path


def print_banner():
    print("""
╔══════════════════════════════════════════════════╗
║  🎤  MiMo-V2.5-ASR  Demo                        ║
║  Xiaomi MiMo API Platform                        ║
║  Endpoint: api.xiaomimimo.com/v1                 ║
╚══════════════════════════════════════════════════╝
""")


# ───── Tích hợp vào DichTuDong ─────
class MiMoSTTEngine:
    """
    Drop-in replacement cho STTEngine trong stt_engine.py.
    Dùng mimo-v2.5-asr thay vì faster-whisper.

    Cách dùng trong stt_engine.py:
        # Thay:   self.stt = STTEngine()
        # Thành:  self.stt = MiMoSTTEngine()
    """

    def __init__(self, language: str = "en"):
        self.language = language
        if not MIMO_API_KEY:
            raise EnvironmentError("MIMO_API_KEY chưa được set!")
        print(f"✅ MiMoSTTEngine khởi tạo (model: {MIMO_MODEL})")

    def transcribe_file(self, audio_path: str) -> list[dict]:
        """Nhận dạng từ file audio, trả về list segment."""
        result = transcribe(audio_path, self.language)
        text   = result["text"].strip()
        if not text:
            return []
        return [{"text": text, "start": 0.0, "end": 0.0}]


# ───── Entry Point ─────
if __name__ == "__main__":
    print_banner()

    # Kiểm tra API key
    if not MIMO_API_KEY:
        print("⚠️  MIMO_API_KEY chưa được set!")
        print("   1. Đăng ký tại: https://platform.xiaomimimo.com/")
        print("   2. Tạo API Key trong Console → API Keys")
        print("   3. Chạy: export MIMO_API_KEY='sk-xxxxx'")
        print("   4. Thử lại: python demo_mimo_asr.py [audio.wav]")
        print()
        print("💡 Để test nhanh (không cần key), dùng --gen-test:")
        print("   python demo_mimo_asr.py --gen-test")
        sys.exit(1)

    # Xác định file audio đầu vào
    if len(sys.argv) < 2:
        print("Usage: python demo_mimo_asr.py <audio_file.wav|mp3>")
        print("       python demo_mimo_asr.py --gen-test   # tạo file sine test")
        sys.exit(1)

    if sys.argv[1] == "--gen-test":
        audio_path = generate_test_wav("test_sine.wav")
        print("⚠️  File test là âm sine, kết quả transcribe sẽ trống/random")
    else:
        audio_path = sys.argv[1]

    try:
        result = transcribe(audio_path)
        print()
        print("═" * 50)
        print(f"📝 Kết quả nhận dạng:")
        print(f"   {result['text']}")
        print("═" * 50)
        usage = result.get("usage", {})
        if usage:
            print(f"📊 Tokens dùng: {usage.get('total_tokens', 'N/A')}")
        print(f"🤖 Model: {result['model']}")

    except (FileNotFoundError, ValueError, RuntimeError, EnvironmentError) as e:
        print(f"\n{e}")
        sys.exit(1)
