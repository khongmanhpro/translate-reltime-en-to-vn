"""🚀 DichTuDong - Real-time Meeting Translator Server.

FastAPI backend with WebSocket for real-time audio streaming,
faster-whisper STT, DeepL translation, edge-tts, and SQLite storage.
"""

import sys
import os
import json
import base64
import asyncio
import io
import wave
import struct
import hmac
import secrets
from urllib.parse import parse_qs
from pathlib import Path
from datetime import datetime
from typing import Optional

import numpy as np
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from loguru import logger

from config import (
    HOST, PORT, LOG_LEVEL, LOG_PATH, AUDIO_RATE,
    TTS_ENABLED, DEEPL_API_KEY, STT_ENGINE, STT_MODEL_SIZE,
)
from translator import TextTranslator
from stt_engine import AudioProcessor
from database import TranscriptDB

# ───── Setup logging ─────
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logger.remove()
logger.add(sys.stderr, level=LOG_LEVEL)
logger.add(str(LOG_PATH), rotation="10 MB", retention="7 days", level="DEBUG")

# ───── Initialize components ─────
app = FastAPI(title="DichTuDong", version="1.0.0")
translator = TextTranslator()
db = TranscriptDB()
current_session_id: int = db.start_session("Auto Session")

# ───── Simple access control ─────
AUTH_USER = os.getenv("APP_USERNAME", "admin")
AUTH_PASSWORD = os.getenv("APP_PASSWORD", "1332001")
AUTH_COOKIE = "dichtudong_session"
AUTH_SESSIONS: set[str] = set()


def is_valid_session(token: Optional[str]) -> bool:
    return bool(token and token in AUTH_SESSIONS)


def is_authenticated_request(request: Request) -> bool:
    return is_valid_session(request.cookies.get(AUTH_COOKIE))


def is_authenticated_scope(scope: dict) -> bool:
    cookie_header = ""
    for key, value in scope.get("headers", []):
        if key == b"cookie":
            cookie_header = value.decode("latin1")
            break

    cookies = {}
    for part in cookie_header.split(";"):
        if "=" not in part:
            continue
        name, value = part.strip().split("=", 1)
        cookies[name] = value
    return is_valid_session(cookies.get(AUTH_COOKIE))


def render_login(error: str = "") -> str:
    error_html = f'<div class="error">{error}</div>' if error else ""
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - DichTuDong</title>
    <style>
        * {{ box-sizing: border-box; }}
        body {{
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            font-family: Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            color: #f5f8ff;
            background:
                linear-gradient(135deg, rgba(56, 232, 255, 0.13), transparent 36%),
                linear-gradient(225deg, rgba(124, 58, 237, 0.16), transparent 38%),
                #07090d;
        }}
        .login {{
            width: min(420px, calc(100vw - 32px));
            padding: 28px;
            border: 1px solid #34465f;
            border-radius: 10px;
            background: rgba(16, 22, 32, 0.88);
            box-shadow: 0 24px 80px rgba(0, 0, 0, 0.42);
            backdrop-filter: blur(18px);
        }}
        .mark {{
            width: 40px;
            height: 40px;
            display: grid;
            place-items: center;
            margin-bottom: 18px;
            border-radius: 8px;
            background: linear-gradient(135deg, #38e8ff, #7c3aed);
            color: #031015;
            font-weight: 800;
            font-size: 13px;
        }}
        h1 {{
            margin: 0 0 8px;
            font-size: 24px;
            line-height: 1.2;
        }}
        p {{
            margin: 0 0 24px;
            color: #b6c3d4;
            font-size: 14px;
            line-height: 1.6;
        }}
        label {{
            display: block;
            margin-bottom: 8px;
            color: #b6c3d4;
            font-size: 13px;
            font-weight: 600;
        }}
        input {{
            width: 100%;
            height: 44px;
            margin-bottom: 16px;
            padding: 0 12px;
            border: 1px solid #223044;
            border-radius: 8px;
            outline: none;
            background: #0d1118;
            color: #f5f8ff;
            font: inherit;
        }}
        input:focus {{
            border-color: #38e8ff;
            box-shadow: 0 0 0 3px rgba(56, 232, 255, 0.13);
        }}
        button {{
            width: 100%;
            height: 44px;
            border: 0;
            border-radius: 8px;
            cursor: pointer;
            background: linear-gradient(135deg, #38e8ff, #2dd4bf);
            color: #031015;
            font: inherit;
            font-weight: 800;
        }}
        .error {{
            margin-bottom: 16px;
            padding: 10px 12px;
            border: 1px solid rgba(224, 82, 67, 0.35);
            border-radius: 8px;
            background: rgba(224, 82, 67, 0.12);
            color: #ffb4aa;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <form class="login" method="post" action="/login">
        <div class="mark">DT</div>
        <h1>DichTuDong Login</h1>
        <p>Nhap tai khoan de truy cap giao dien dich truc tiep.</p>
        {error_html}
        <label for="username">Username</label>
        <input id="username" name="username" autocomplete="username" autofocus>
        <label for="password">Password</label>
        <input id="password" name="password" type="password" autocomplete="current-password">
        <button type="submit">Dang nhap</button>
    </form>
</body>
</html>"""


class AuthenticatedStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope: dict):
        if not is_authenticated_scope(scope):
            return JSONResponse({"error": "Unauthorized"}, status_code=401)
        return await super().get_response(path, scope)

# TTS (lazy init)
tts_engine = None
if TTS_ENABLED:
    try:
        from tts_engine import TTSEngine
        tts_engine = TTSEngine()
    except Exception:
        logger.warning("⚠️ TTS init failed, continuing without TTS")

# ───── STT callback ─────
connected_clients: set[WebSocket] = set()


async def broadcast(payload: dict):
    """Send JSON payload to all connected WebSocket clients."""
    data = json.dumps(payload, ensure_ascii=False)
    dead = set()
    for ws in connected_clients:
        try:
            await ws.send_text(data)
        except Exception:
            dead.add(ws)
    connected_clients.difference_update(dead)


def on_stt_text(text: str):
    """Called by AudioProcessor when speech is detected."""
    translated = translator.translate(text) or ""

    # Store in DB
    db.add_entry(current_session_id, text, translated)

    # Broadcast to clients
    payload = {
        "type": "subtitle",
        "original": text,
        "translated": translated,
        "timestamp": datetime.now().isoformat(),
        "session_id": current_session_id,
    }

    # TTS (if enabled)
    if tts_engine and translated:
        try:
            audio_bytes = tts_engine.generate(translated)
            if audio_bytes:
                payload["tts_audio"] = base64.b64encode(audio_bytes).decode("ascii")
        except Exception as e:
            logger.warning(f"TTS failed: {e}")

    loop = None
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        pass

    if loop and loop.is_running():
        asyncio.ensure_future(broadcast(payload))
    else:
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(broadcast(payload))
            loop.close()
        except Exception:
            pass


# Initialize AudioProcessor
audio_processor = AudioProcessor(on_text=on_stt_text)

# ───── Serve static files ─────
static_dir = Path(__file__).parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", AuthenticatedStaticFiles(directory=str(static_dir)), name="static")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated_request(request):
        return RedirectResponse("/", status_code=303)
    return render_login()


@app.post("/login")
async def login(request: Request):
    body = (await request.body()).decode("utf-8")
    form = parse_qs(body)
    username = form.get("username", [""])[0]
    password = form.get("password", [""])[0]

    valid_user = hmac.compare_digest(username, AUTH_USER)
    valid_password = hmac.compare_digest(password, AUTH_PASSWORD)
    if not (valid_user and valid_password):
        return HTMLResponse(render_login("Sai tai khoan hoac mat khau."), status_code=401)

    token = secrets.token_urlsafe(32)
    AUTH_SESSIONS.add(token)
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        AUTH_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        max_age=60 * 60 * 24 * 7,
    )
    return response


@app.get("/logout")
async def logout(request: Request):
    token = request.cookies.get(AUTH_COOKIE)
    if token:
        AUTH_SESSIONS.discard(token)
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(AUTH_COOKIE)
    return response


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main subtitle UI."""
    if not is_authenticated_request(request):
        return RedirectResponse("/login", status_code=303)

    index_file = static_dir / "index.html"
    if index_file.exists():
        return index_file.read_text(encoding="utf-8")
    return "<h1>DichTuDong - Real-time Meeting Translator</h1><p>static/index.html not found</p>"


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """WebSocket endpoint for real-time audio streaming and subtitle delivery."""
    if not is_authenticated_scope(ws.scope):
        await ws.close(code=1008)
        return

    await ws.accept()
    connected_clients.add(ws)
    logger.info(f"🔌 Client connected ({len(connected_clients)} total)")

    try:
        while True:
            msg = await ws.receive()

            if msg.get("type") == "websocket.disconnect":
                break

            # Handle JSON commands
            if "text" in msg:
                try:
                    data = json.loads(msg["text"])
                    cmd = data.get("action")

                    if cmd == "start_listening":
                        audio_processor.start()
                        await ws.send_text(json.dumps({"type": "status", "listening": True}))

                    elif cmd == "stop_listening":
                        audio_processor.stop()
                        await ws.send_text(json.dumps({"type": "status", "listening": False}))

                    elif cmd == "get_sessions":
                        sessions = db.get_sessions()
                        await ws.send_text(json.dumps({"type": "sessions", "data": sessions}))

                    elif cmd == "get_transcripts":
                        sid = data.get("session_id", current_session_id)
                        entries = db.get_transcripts(sid)
                        await ws.send_text(json.dumps({"type": "transcripts", "data": entries}))

                    elif cmd == "export_srt":
                        sid = data.get("session_id", current_session_id)
                        srt = db.export_srt(sid)
                        await ws.send_text(json.dumps({"type": "export", "format": "srt", "data": srt}))

                    elif cmd == "export_txt":
                        sid = data.get("session_id", current_session_id)
                        txt = db.export_txt(sid)
                        await ws.send_text(json.dumps({"type": "export", "format": "txt", "data": txt}))

                except json.JSONDecodeError:
                    pass

            # Handle binary audio data (PCM 16-bit, mono, 16kHz)
            elif "bytes" in msg:
                raw = msg["bytes"]
                if len(raw) > 0:
                    audio = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                    audio_processor.feed_audio(audio)

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"❌ WebSocket error: {e}")
    finally:
        connected_clients.discard(ws)
        logger.info(f"🔌 Client disconnected ({len(connected_clients)} total)")


@app.get("/api/sessions")
async def api_sessions(request: Request):
    if not is_authenticated_request(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return db.get_sessions()


@app.get("/api/config")
async def api_config(request: Request):
    if not is_authenticated_request(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return {
        "stt_engine": STT_ENGINE,
        "stt_model": STT_MODEL_SIZE if STT_ENGINE == "whisper" else "mimo-v2.5-asr",
        "translator": "deepl" if DEEPL_API_KEY else "google-api",
        "tts": TTS_ENABLED,
        "audio_rate": AUDIO_RATE,
    }


@app.get("/api/sessions/{session_id}/transcripts")
async def api_transcripts(session_id: int, request: Request):
    if not is_authenticated_request(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return db.get_transcripts(session_id)


@app.get("/api/export/{session_id}/{format}")
async def api_export(session_id: int, format: str, request: Request):
    if not is_authenticated_request(request):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    if format == "srt":
        content = db.export_srt(session_id)
        media = "text/plain"
        fname = f"transcript_{session_id}.srt"
    elif format == "txt":
        content = db.export_txt(session_id)
        media = "text/plain"
        fname = f"transcript_{session_id}.txt"
    else:
        return JSONResponse({"error": "Unsupported format"}, status_code=400)

    return JSONResponse({"filename": fname, "content": content})


@app.on_event("shutdown")
async def shutdown():
    db.end_session(current_session_id)
    db.close()
    logger.info("🛑 Server shutting down")


# ───── Entry point ─────
if __name__ == "__main__":
    import uvicorn
    logger.info(f"🚀 DichTuDong starting on {HOST}:{PORT}")
    logger.info(f"   STT Model: {STT_MODEL_SIZE}")
    logger.info(f"   Translation: {'DeepL' if DEEPL_API_KEY else 'Argos (offline)'}")
    logger.info(f"   TTS: {'Enabled' if TTS_ENABLED else 'Disabled'}")
    uvicorn.run(app, host=HOST, port=PORT, log_level=LOG_LEVEL.lower())
