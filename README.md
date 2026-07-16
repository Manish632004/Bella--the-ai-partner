# BELLA — Personal Local AI Assistant

A privacy-first, fully local AI assistant that runs on your own hardware.

## Quick Start (Phase 1)

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.ai/) installed and running

### Setup

```bash
# 1. Pull the model (one time, ~9GB download)
ollama pull qwen2.5:14b-instruct-q4_K_M

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start the server
python run.py
```

Open `http://localhost:8000` in your browser.

## Architecture

```
BELLA/
├── bella/
│   ├── api/            # FastAPI routes
│   │   └── chat.py     # Chat endpoint (REST + SSE streaming)
│   ├── core/           # Core logic
│   │   ├── config.py   # Configuration from .env
│   │   ├── conversation.py  # Session-based conversation management
│   │   └── llm.py      # Ollama client (async, streaming)
│   ├── memory/         # Phase 4: LanceDB + SQLite memory
│   ├── permissions/    # Phase 5: Tiered permission gate
│   ├── tools/          # Phase 3: Tool definitions & execution
│   ├── voice/          # Phase 2: STT, TTS, wake word
│   ├── static/         # CSS, JS
│   ├── templates/      # Jinja2 HTML templates
│   └── app.py          # FastAPI application factory
├── tests/
├── .env                # Local configuration
├── requirements.txt
└── run.py              # Entry point
```

## Build Phases

| Phase | Description | Status |
|-------|------------|--------|
| 1 | Core local chat loop | 🟢 In Progress |
| 2 | Voice in / voice out | ⬜ Pending |
| 3 | Tool calling | ⬜ Pending |
| 4 | Memory (vector + structured) | ⬜ Pending |
| 5 | Permission-gated system tools | ⬜ Pending |
| 6 | Sync + phone client | ⬜ Pending |
| 7 | Integrations & polish | ⬜ Pending |

## Privacy

Everything runs locally. No data leaves your machine. The LLM, STT, TTS, and all storage are on-device.
