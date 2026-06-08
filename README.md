# 🎙️ DichTuDong - Real-time Meeting Translator

**EN → Vietnamese** real-time speech translation for online meetings (Teams, Zoom, Google Meet).

## ✨ Features

- **Real-time STT** — faster-whisper (Whisper model, CPU/GPU)
- **Translation** — DeepL API (500K free chars/month) + Argos Translate (offline fallback)
- **TTS** — edge-tts Vietnamese voice (optional)
- **Web UI** — Subtitle overlay, history, export (SRT/TXT)
- **Transcript storage** — SQLite database
- **Docker ready** — CPU & GPU support, one-command deploy

## 🏗️ Architecture

```
┌──────────────┐    WebSocket    ┌──────────────────┐
│  Web Client   │◄──────────────►│  FastAPI Server   │
│  (Browser)    │                │                    │
└──────────────┘                │  faster-whisper    │
                                │  DeepL/Argos       │
┌──────────────┐    WebSocket    │  edge-tts          │
│  Audio Client │───────────────►│  SQLite            │
│  (Local mic)  │                └──────────────────┘
└──────────────┘
```

## 🚀 Quick Start

### Option 1: Docker (recommended for VPS)

```bash
# Clone
git clone <repo-url> dichtudong
cd dichtudong

# Configure
cp .env.example .env
# Edit .env → set DEEPL_API_KEY

# Run (CPU mode)
docker-compose up -d

# Access: http://localhost:8765
```

### Option 2: Docker with GPU

```bash
# Edit docker-compose.yml: uncomment app-gpu service, comment app service
docker-compose up -d --build
```

### Option 3: Local development

```bash
# Install dependencies
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env

# Run (server + local audio capture)
python main.py

# Or server only
python main.py --server-only

# Or client only (connect to remote server)
python main.py --client-only

# List audio devices
python main.py --list-devices
```

## 🎤 Audio Setup

### macOS — BlackHole
```bash
brew install blackhole-2ch
# System Preferences → Sound → Output → BlackHole 2ch
# Then in client.py: DEVICE_NAME = "BlackHole 2ch"
```

### Windows — VB-Cable
Download: https://vb-audio.com/Cable/
Set as default playback device, then capture from CABLE Output.

### Linux — PulseAudio
```bash
# Use PulseAudio monitor
pactl list short sources | grep monitor
# Set DEVICE_NAME to your monitor source
```

## ⚙️ Configuration

| Variable | Default | Description |
|---|---|---|
| `STT_MODEL_SIZE` | `medium` | Whisper model (tiny/base/small/medium/large-v3) |
| `STT_DEVICE` | `auto` | CPU or CUDA |
| `STT_LANGUAGE` | `en` | Source language |
| `DEEPL_API_KEY` | (empty) | DeepL API key (free at deepl.com/pro-api) |
| `TARGET_LANG` | `VI` | Translation target |
| `TTS_ENABLED` | `false` | Enable Vietnamese voice |
| `TTS_VOICE` | `vi-VN-HoaiMyNeural` | TTS voice |
| `PORT` | `8765` | Server port |

## 📁 Project Structure

```
dichtudong/
├── server.py          # FastAPI server (main backend)
├── stt_engine.py      # Speech-to-text (faster-whisper)
├── translator.py      # Translation (DeepL + Argos)
├── tts_engine.py      # Text-to-speech (edge-tts)
├── database.py        # SQLite transcript storage
├── client.py          # Local audio capture client
├── config.py          # Configuration
├── main.py            # Local dev entry point
├── static/
│   └── index.html     # Web subtitle UI
├── Dockerfile         # CPU Docker image
├── Dockerfile.gpu     # GPU Docker image
├── docker-compose.yml # Docker orchestration
├── requirements.txt   # Python dependencies
└── .env.example       # Environment template
```

## 🔌 API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/` | GET | Web subtitle UI |
| `/ws` | WebSocket | Real-time audio/subtitle stream |
| `/api/sessions` | GET | List transcript sessions |
| `/api/sessions/{id}/transcripts` | GET | Get session transcripts |
| `/api/export/{id}/srt` | GET | Export as SRT |
| `/api/export/{id}/txt` | GET | Export as TXT |

## 📊 Model Size Guide

| Model | Size | Speed (CPU) | Quality | RAM |
|---|---|---|---|---|
| tiny | 39M | ⚡⚡⚡⚡ | ⭐⭐ | ~1GB |
| base | 74M | ⚡⚡⚡ | ⭐⭐⭐ | ~1GB |
| small | 244M | ⚡⚡ | ⭐⭐⭐⭐ | ~2GB |
| medium | 769M | ⚡ | ⭐⭐⭐⭐ | ~4GB |
| large-v3 | 1.5G | 🐌 | ⭐⭐⭐⭐⭐ | ~6GB |

## 📄 License

Based on [Voice2Sub](https://github.com/light12222/Voice2Sub-Whisper-Live-Translator) (MIT License).
