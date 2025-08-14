# 🎙 Conversational Voice Agent

🗣️ **Talk to your AI — get human-like responses back in real time.**  
Powered by **AssemblyAI** (Speech-to-Text) + **Google Gemini** (LLM) + **Murf AI** (Text-to-Speech).  
Built as part of **#30DaysofVoiceAgents** by [Murf AI](https://murf.ai).

---

## 📸 UI Screenshots
*(Add screenshots here — one for the main chat interface, one for the architecture diagram)*

---

## ✨ What’s Inside

- 🎙 **Hands-free voice chat** — Record directly in your browser and hear AI responses instantly.
- 🧠 **Multi-turn memory** — Session-based conversation history (tracked with `session_id`).
- 🛡 **Resilient by design** — Graceful fallbacks if STT, LLM, or TTS fails (no awkward silence).
- ⚡ **FastAPI backend** — Clean, async endpoints for TTS, STT, LLM, and agent chat.
- 🎨 **Simple, responsive UI** — Built with HTML/CSS/JS (and easily replaceable with Tailwind).
- 🔁 **Auto-continue mode** — Automatically restarts recording after AI finishes speaking.

---

## 🧩 High-Level Architecture

```plaintext
User Speaks → AssemblyAI (STT) → Google Gemini (LLM) → Murf AI (TTS) → User Hears Reply
```

**Flow:**
1. **Frontend** captures microphone input (MediaRecorder API).
2. **Backend** sends audio to AssemblyAI for transcription.
3. Transcribed text is passed to Google Gemini for intelligent response generation.
4. Gemini’s text output is sent to Murf AI for lifelike voice synthesis.
5. Final audio is streamed back to the browser and auto-played.

---

## 🗂 Project Structure

```
.
├─ main.py                # FastAPI app (STT/LLM/TTS endpoints + agent chat)
├─ templates/
│  └─ index.html           # Frontend interface
├─ static/
│  ├─ script.js            # Frontend logic (recording, fetch, playback)
│  ├─ fallback.mp3         # Fallback audio when APIs fail
├─ uploads/                # Temporary audio files
├─ .env                    # API keys (not committed)
├─ requirements.txt        # Python dependencies
└─ README.md               # Documentation
```

---

## 🔑 Environment Variables

Create a `.env` file in the root directory:

```
MURF_API_KEY=your_murf_api_key_here
ASSEMBLYAI_API_KEY=your_assemblyai_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-1.5-flash
```

**Tip:** Never commit `.env` — add it to `.gitignore`.

---

## ⚙️ Setup & Run

### 1️⃣ Clone & Create Virtual Environment
```bash
git clone https://github.com/yourusername/ai-voice-agent.git
cd ai-voice-agent

python -m venv venv
# macOS/Linux
source venv/bin/activate
# Windows
venv\Scripts\activate
```

### 2️⃣ Install Dependencies
```bash
pip install -r requirements.txt
```

### 3️⃣ Start the Server
```bash
uvicorn main:app --reload
```

### 4️⃣ Open in Browser
Go to: [http://127.0.0.1:8000](http://127.0.0.1:8000)

---

## 🔌 API Endpoints (Quick Reference)

### **POST /generate-audio**
- **Body:** `{"text": "Hello world"}`
- **Response:** `{"ok": true, "audio_url": "https://..."}`  
  Falls back to `/static/fallback.mp3` if TTS fails.

### **POST /transcribe/file**
- **FormData:** `file` (audio/webm)
- **Response:** `{"ok": true, "transcript": "..."}`

### **POST /llm/query**
- **Body:** `{"text": "Your question here"}`
- **Response:** `{"ok": true, "llm_text": "..."}`

### **POST /agent/chat/{session_id}**
- **FormData:** `file` (audio/webm)
- **Response:** `{"ok": true, "transcript": "...", "llm_text": "...", "audio_url": "..."}`  
  Stores conversation history in memory for that `session_id`.

---

## 🧱 Error Handling & Fallbacks

- Every external API call (STT, LLM, TTS) is wrapped in **`try/except`** blocks.
- If a stage fails:
  1. Backend returns JSON with `ok: false`, `stage`, and `error`.
  2. Frontend auto-plays `fallback.mp3` so the conversation never "goes silent".
- Simulate outages by removing an API key from `.env` and restarting.

**Example Error JSON:**
```json
{
  "ok": false,
  "stage": "llm",
  "error": "RuntimeError: Gemini HTTP 403: ...details..."
}
```

---

## 🧭 Browser Notes

- Uses **MediaRecorder** with `audio/webm;codecs=opus` — works best in Chromium-based browsers.
- Safari users may need to allow microphone permissions and check codec support.
- Autoplay is triggered after a **user gesture** to comply with browser policies.

---

## 🧰 Requirements (Partial List)

- `fastapi`
- `uvicorn`
- `python-dotenv`
- `requests`
- `assemblyai`
- `jinja2`

*(See `requirements.txt` for full list)*

---

## 🛣 Roadmap

- Replace in-memory history with a persistent store (SQLite/Redis/Firestore)
- Add **multi-voice and style control** for Murf AI
- Implement **streamed STT & streamed TTS**
- Add **live waveform visualizer** for recordings
- Create **admin dashboard** for viewing conversation logs

---

## 🙏 Credits

- **[Murf AI](https://murf.ai)** — Text-to-Speech
- **[AssemblyAI](https://assemblyai.com)** — Speech-to-Text
- **[Google Gemini](https://ai.google.dev/)** — LLM Responses
- **[FastAPI](https://fastapi.tiangolo.com/)** — Backend framework

---

## 📜 License

MIT — see `LICENSE` file.
