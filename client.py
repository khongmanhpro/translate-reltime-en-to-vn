"""🎙️ Local audio capture client.

Captures system audio via sounddevice and streams to the server via WebSocket.
Use this when running the translator on a local machine with a meeting.

Requires:
  - macOS: BlackHole 2ch virtual audio device
  - Windows: VB-Cable or WASAPI loopback
  - Linux: PulseAudio monitor
"""

import sys
import json
import asyncio
import numpy as np
from loguru import logger

try:
    import sounddevice as sd
    import websockets
except ImportError as e:
    print(f"Missing dependency: {e}")
    print("Install: pip install sounddevice websockets")
    sys.exit(1)

from config import AUDIO_RATE, CHUNK_SIZE

# ───── Config ─────
SERVER_URL = "ws://localhost:8765/ws"
DEVICE_NAME = None  # None = default, or "BlackHole 2ch", "VB-Cable", etc.


def find_device(name: str = None) -> int:
    """Find audio input device by name."""
    if name is None:
        return sd.default.device[0]  # Default input

    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if name.lower() in dev["name"].lower() and dev["max_input_channels"] > 0:
            logger.info(f"🎤 Found device: {dev['name']} (index {i})")
            return i

    logger.warning(f"⚠️ Device '{name}' not found, using default")
    return sd.default.device[0]


async def stream_audio():
    """Capture audio and send to server via WebSocket."""
    device_id = find_device(DEVICE_NAME)
    device_info = sd.query_devices(device_id)
    input_rate = int(device_info["default_samplerate"])
    logger.info(f"🎤 Using: {device_info['name']} @ {input_rate}Hz")

    # Connect to server
    logger.info(f"🔌 Connecting to {SERVER_URL}...")
    async with websockets.connect(SERVER_URL, max_size=2**20) as ws:
        logger.info("✅ Connected to server")

        # Start listening
        await ws.send(json.dumps({"action": "start_listening"}))
        response = json.loads(await ws.recv())
        logger.info(f"📡 Server status: {response}")

        # Audio callback
        queue = asyncio.Queue()

        def audio_callback(indata, frames, time, status):
            if status:
                logger.warning(f"⚠️ Audio status: {status}")
            queue.put_nowait(indata.copy())

        # Start audio stream
        with sd.InputStream(
            device=device_id,
            channels=1,
            samplerate=input_rate,
            blocksize=CHUNK_SIZE,
            dtype="float32",
            callback=audio_callback,
        ):
            logger.info("🎤 Streaming audio... Press Ctrl+C to stop")

            try:
                while True:
                    audio = await queue.get()

                    # Resample to 16kHz if needed
                    if input_rate != AUDIO_RATE:
                        import resampy
                        audio = resampy.resample(audio[:, 0], input_rate, AUDIO_RATE)
                        audio = audio.reshape(-1, 1)

                    # Convert to int16 PCM
                    pcm = (audio[:, 0] * 32767).astype(np.int16)
                    await ws.send(pcm.tobytes())

                    # Receive subtitles
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=0.01)
                        data = json.loads(msg)
                        if data.get("type") == "subtitle":
                            print(f"\n🗣️  {data['original']}")
                            print(f"   → {data['translated']}")
                    except asyncio.TimeoutError:
                        pass

            except KeyboardInterrupt:
                logger.info("🛑 Stopping...")
                await ws.send(json.dumps({"action": "stop_listening"}))


def list_devices():
    """List available audio input devices."""
    print("\n🎤 Available audio input devices:\n")
    devices = sd.query_devices()
    for i, dev in enumerate(devices):
        if dev["max_input_channels"] > 0:
            marker = " ← DEFAULT" if i == sd.default.device[0] else ""
            print(f"  [{i}] {dev['name']} (ch: {dev['max_input_channels']}, rate: {dev['default_samplerate']:.0f}Hz){marker}")
    print()


if __name__ == "__main__":
    if "--list-devices" in sys.argv:
        list_devices()
    else:
        try:
            asyncio.run(stream_audio())
        except KeyboardInterrupt:
            print("\n👋 Bye!")
