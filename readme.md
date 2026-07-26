# 🤖 KANIX AI

KANIX AI is a local AI assistant inspired by JARVIS.

It combines local AI models with modern automation to provide an intelligent desktop assistant.

---

## ✨ Features

- 🧠 Local LLM using Qwen 3 (Ollama)
- 👁️ Vision AI using Qwen2.5-VL
- 🎤 Speech-to-Text using Groq Whisper
- 🔊 Natural Text-to-Speech using Kokoro
- 💾 Memory System
- 🌐 Web Search
- 📂 File Management
- 🖥️ Computer Automation
- 🌦️ Weather Reports
- 🎬 YouTube Controls
- 📱 Messaging Automation
- 🧑‍💻 Coding Assistant
- 🤖 Multi-Agent Architecture

---

## 🛠 Tech Stack

- Python
- PyQt6
- Ollama
- Qwen3 8B
- Qwen2.5-VL
- Groq API
- Kokoro TTS
- Supabase
- Playwright

---

## Project Structure

```text
KANIX-AI/
│
├── actions/
├── agent/
├── core/
├── memory/
├── ui.py
├── main.py
├── requirements.txt
└── README.md
```

---

## Installation

```bash
git clone https://github.com/malusarekrishnab-cyber/KANIX-AI.git

cd KANIX-AI

python -m venv .venv

source .venv/bin/activate
# Windows
.\.venv\Scripts\activate

pip install -r requirements.txt
```

---

## Run

```bash
python main.py
```

---

## Current AI Models

| Component | Model |
|----------|--------|
| LLM | Qwen3 8B |
| Vision | Qwen2.5-VL |
| Speech-to-Text | Whisper Large V3 Turbo |
| Text-to-Speech | Kokoro |
| Memory | Local Database |

---

## License

MIT License

---

## Author

**Krushna Malusare**

GitHub:
https://github.com/malusarekrishnab-cyber