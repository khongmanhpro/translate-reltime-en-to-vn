"""🔊 TTS Module: edge-tts for Vietnamese text-to-speech."""

import asyncio
import tempfile
import io
from typing import Optional
from loguru import logger
from config import TTS_VOICE


class TTSEngine:
    """Generate Vietnamese speech from text using edge-tts."""

    def __init__(self, voice: str = TTS_VOICE):
        self.voice = voice
        self._available = False
        try:
            import edge_tts  # noqa: F401
            self._available = True
            logger.info(f"🔊 TTS ready (voice: {voice})")
        except ImportError:
            logger.warning("⚠️ edge-tts not installed, TTS disabled")

    async def _generate(self, text: str) -> Optional[bytes]:
        """Generate MP3 audio bytes from text."""
        if not self._available:
            return None
        try:
            import edge_tts
            communicate = edge_tts.Communicate(text, self.voice)
            buf = io.BytesIO()
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    buf.write(chunk["data"])
            return buf.getvalue() if buf.tell() > 0 else None
        except Exception as e:
            logger.error(f"❌ TTS error: {e}")
            return None

    def generate(self, text: str) -> Optional[bytes]:
        """Synchronous wrapper for generate MP3 audio."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Already in async context, use a new thread
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, self._generate(text)).result(timeout=10)
            return loop.run_until_complete(self._generate(text))
        except RuntimeError:
            return asyncio.run(self._generate(text))
