"""🚀 DichTuDong - Local entry point.

Run this for local development/testing.
For production/VPS: use Docker (docker-compose up).

Usage:
    python main.py                  # Start server + local audio capture
    python main.py --server-only    # Start server only (for Docker/remote client)
    python main.py --client-only    # Start client only (connect to remote server)
    python main.py --list-devices   # List audio input devices
"""

import sys
import argparse
from loguru import logger
from config import HOST, PORT, STT_MODEL_SIZE, DEEPL_API_KEY


def main():
    parser = argparse.ArgumentParser(description="DichTuDong - Real-time Meeting Translator")
    parser.add_argument("--server-only", action="store_true", help="Start server only")
    parser.add_argument("--client-only", action="store_true", help="Start client only")
    parser.add_argument("--list-devices", action="store_true", help="List audio devices")
    parser.add_argument("--host", default=HOST, help=f"Server host (default: {HOST})")
    parser.add_argument("--port", type=int, default=PORT, help=f"Server port (default: {PORT})")
    args = parser.parse_args()

    if args.list_devices:
        from client import list_devices
        list_devices()
        return

    # Print banner
    print("""
╔══════════════════════════════════════════════╗
║   🎙️  DichTuDong - Real-time Translator      ║
║   EN → VI | Subtitles + Voice               ║
╚══════════════════════════════════════════════╝
""")
    print(f"  STT Model   : {STT_MODEL_SIZE}")
    print(f"  Translation : {'DeepL' if DEEPL_API_KEY else 'Argos (offline)'}")
    print(f"  Server      : {args.host}:{args.port}")
    print()

    if args.client_only:
        # Client only - connect to remote server
        from client import stream_audio
        import asyncio
        try:
            asyncio.run(stream_audio())
        except KeyboardInterrupt:
            print("\n👋 Bye!")
        return

    if args.server_only:
        # Server only
        import uvicorn
        from server import app
        uvicorn.run(app, host=args.host, port=args.port, log_level="info")
        return

    # Default: start server + local client in threads
    import threading
    import time

    # Start server in background thread
    def run_server():
        import uvicorn
        from server import app
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")

    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    logger.info(f"🚀 Server starting on {args.host}:{args.port}...")
    time.sleep(3)  # Wait for server to be ready

    # Start local client
    from client import stream_audio
    import asyncio
    try:
        asyncio.run(stream_audio())
    except KeyboardInterrupt:
        print("\n👋 Bye!")


if __name__ == "__main__":
    main()
