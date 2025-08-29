from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional, List
import os
import requests
import time

app = FastAPI()

# ---- Day 11: unified errors + helpers ----
class UpstreamError(Exception):
    def __init__(self, provider: str, detail: str, status_code: int = 502):
        self.provider = provider
        self.detail = detail
        self.status_code = status_code

@app.exception_handler(UpstreamError)
async def upstream_error_handler(request: Request, exc: UpstreamError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "ok": False,
            "provider": exc.provider,
            "error": exc.detail,
            "fallback_text": "I'm having trouble connecting right now"
        },
    )

@app.exception_handler(Exception)
async def catch_all_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "provider": "internal",
            "error": "Unexpected server error",
            "fallback_text": "I'm having trouble connecting right now"
        }
    )

def require_env(k: str) -> str:
    v = os.getenv(k)
    if not v:
        raise UpstreamError("config", f"Missing env var: {k}", 500)
    return v

def debug_fail(request: Request, tag: str):
    # script.js will send this via header later (?fail=tts|stt|llm|agent)
    if request.headers.get("x-debug-fail") == tag:
        raise UpstreamError(tag, "Forced failure for testing", 503)


# Load environment variables
load_dotenv()
MURF_API_KEY = os.getenv("MURF_API_KEY")
ASSEMBLY_API_KEY = os.getenv("ASSEMBLY_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

# Paths
# Paths (robust for cloud deploys)
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
TEMPLATE_DIR = BASE_DIR / "templates"
UPLOAD_DIR = BASE_DIR / os.getenv("UPLOAD_DIR", "uploads")  # optional override

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)  # ensure exists before mount

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

# ---- Chat history (in-memory) ----
from typing import Dict

CHAT_STORE: Dict[str, list[dict]] = {}   # {session_id: [{"role":"user|assistant","content": str}, ...]}
MAX_TURNS = 20                           # keep the last 20 user+assistant pairs

def get_history(session_id: str) -> list[dict]:
    return CHAT_STORE.setdefault(session_id, [])

def add_msg(session_id: str, role: str, content: str):
    hist = get_history(session_id)
    hist.append({"role": role, "content": content})
    if len(hist) > 2 * MAX_TURNS:
        CHAT_STORE[session_id] = hist[-2 * MAX_TURNS:]

def build_prompt_from_history(history: list[dict]) -> str:
    """
    Simple single-string prompt for Gemini using previous turns.
    """
    lines = [
        "You are a helpful, concise voice assistant. Reply naturally and briefly.",
        "",
        "Conversation so far:"
    ]
    for m in history:
        role = "User" if m["role"] == "user" else "Assistant"
        lines.append(f"{role}: {m['content']}")
    lines.append("Assistant:")
    return "\n".join(lines)


# ---------- Helpers ----------
def call_gemini_text(prompt: str) -> str:
    if not GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY not set")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={GEMINI_API_KEY}"
    )
    payload = {"contents": [{"parts": [{"text": prompt}]}]}

    r = requests.post(url, json=payload, timeout=60)
    r.raise_for_status()
    data = r.json()
    text = (
        data.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [{}])[0]
            .get("text")
    )
    if not text:
        raise RuntimeError(f"Empty LLM response: {data}")
    return text

def murf_generate(text: str, voice_id: str = "en-US-natalie") -> Optional[str]:
    murf_headers = {"api-key": MURF_API_KEY, "Content-Type": "application/json"}
    payload = {"text": text, "voice_id": voice_id, "format": "mp3"}

    g = requests.post(
        "https://api.murf.ai/v1/speech/generate",
        headers=murf_headers,
        json=payload,
        timeout=60
    )
    if g.status_code != 200:
        raise RuntimeError(f"Murf generate failed: {g.text[:300]}")
    j = g.json()
    audio_url = j.get("audioFile")
    if isinstance(audio_url, dict):
        audio_url = audio_url.get("url")

    if audio_url:
        return audio_url

    job_id = j.get("id")
    if not job_id:
        return None
    for _ in range(30):
        jr = requests.get(f"https://api.murf.ai/v1/speech/{job_id}", headers=murf_headers, timeout=20)
        jj = jr.json()
        audio_url = jj.get("audioFile")
        if isinstance(audio_url, dict):
            audio_url = audio_url.get("url")
        if audio_url:
            return audio_url
        time.sleep(1)
    return None

def murf_generate_chunked(text: str, voice_id: str = "en-US-natalie", chunk_limit: int = 3000) -> List[str]:
    chunks = []
    s = text.strip()
    while s:
        if len(s) <= chunk_limit:
            chunks.append(s)
            break
        cut = s.rfind(" ", 0, chunk_limit)
        cut = cut if cut != -1 else chunk_limit
        chunks.append(s[:cut].strip())
        s = s[cut:].strip()

    urls = []
    for c in chunks:
        url = murf_generate(c, voice_id=voice_id)
        if not url:
            raise RuntimeError("Murf audio not ready")
        urls.append(url)
    return urls

# ---------- Routes ----------
@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

class TextInput(BaseModel):
    text: str

# Day 2/5: Murf TTS (text -> audio)
@app.post("/generate-audio")
def generate_audio(input: TextInput, request: Request):
    # allow simulated failure later via header
    debug_fail(request, "tts")

    api_key = require_env("MURF_API_KEY")
    headers = {"api-key": api_key, "Content-Type": "application/json"}
    payload = {"text": input.text, "voice_id": "en-US-natalie", "format": "mp3"}

    try:
        resp = requests.post(
            "https://api.murf.ai/v1/speech/generate",
            headers=headers,
            json=payload,
            timeout=60
        )
        if resp.status_code != 200:
            return JSONResponse(status_code=502, content={
                "error": "Generate failed",
                "details": resp.text[:500],
                "fallback_text": "I'm having trouble connecting right now"
            })

        data = resp.json()
        audio_url = data.get("audioFile")
        if isinstance(audio_url, dict):
            audio_url = audio_url.get("url")
        if not audio_url:
            return JSONResponse(status_code=502, content={
                "error": "No audioFile returned",
                "response": data,
                "fallback_text": "I'm having trouble connecting right now"
            })

        return {"audio_url": audio_url}

    except Exception as e:
        return JSONResponse(status_code=500, content={
            "error": str(e),
            "fallback_text": "I'm having trouble connecting right now"
        })

# Debug upload
@app.post("/upload-audio")
async def upload_audio(file: UploadFile = File(...)):
    try:
        file_path = UPLOAD_DIR / file.filename
        with open(file_path, "wb") as buffer:
            buffer.write(await file.read())
        
        return {
            "filename": file.filename,
            "content_type": file.content_type,
            "size_kb": round((file_path.stat().st_size) / 1024, 2),
        }

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# Day 6: Transcribe file
@app.post("/transcribe/file")
async def transcribe_file(file: UploadFile = File(...), request: Request = None):
    # allow simulated failure via ?fail=stt  (script.js adds x-debug-fail)
    debug_fail(request, "stt")

    api_key = require_env("ASSEMBLY_API_KEY")
    aai_headers = {"authorization": api_key}

    try:
        audio_bytes = await file.read()
        upload_res = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers=aai_headers,
            data=audio_bytes,
            timeout=60
        )
        upload_res.raise_for_status()
        upload_url = upload_res.json()["upload_url"]

        transcript_res = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            headers={**aai_headers, "content-type": "application/json"},
            json={"audio_url": upload_url},
            timeout=30
        )
        transcript_res.raise_for_status()
        transcript_id = transcript_res.json()["id"]

        # poll
        for _ in range(60):
            polling_res = requests.get(
                f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                headers=aai_headers,
                timeout=20
            )
            pdata = polling_res.json()
            status = pdata.get("status")
            if status == "completed":
                return {"transcript": pdata.get("text", "")}
            if status == "error":
                return JSONResponse(status_code=502, content={
                    "error": pdata.get("error", "Transcription error"),
                    "fallback_text": "I'm having trouble connecting right now"
                })
            time.sleep(1)

        return JSONResponse(status_code=504, content={
            "error": "Transcription timed out",
            "fallback_text": "I'm having trouble connecting right now"
        })

    except requests.HTTPError as e:
        return JSONResponse(status_code=502, content={
            "error": f"Upstream error: {e.response.text[:500]}",
            "fallback_text": "I'm having trouble connecting right now"
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "error": str(e),
            "fallback_text": "I'm having trouble connecting right now"
        })

# Day 7: Echo (Transcribe -> Murf)
@app.post("/tts/echo")
async def tts_echo(file: UploadFile = File(...), request: Request = None):
    # simulate failures via ?fail=stt or ?fail=tts (script.js adds x-debug-fail)
    tag = request.headers.get("x-debug-fail")
    if tag in {"stt", "tts"}:
        raise UpstreamError(tag, "Forced failure for testing", 503)

    stt_key = require_env("ASSEMBLY_API_KEY")
    tts_key = require_env("MURF_API_KEY")
    aai_headers = {"authorization": stt_key}

    try:
        audio_bytes = await file.read()
        if not audio_bytes:
            return JSONResponse(status_code=400, content={
                "error": "Empty file",
                "fallback_text": "I'm having trouble connecting right now"
            })

        # --- STT upload ---
        up_res = requests.post(
            "https://api.assemblyai.com/v2/upload",
            headers=aai_headers,
            data=audio_bytes,
            timeout=60
        )
        up_res.raise_for_status()
        upload_url = up_res.json()["upload_url"]

        # --- STT request ---
        t_res = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            headers={**aai_headers, "content-type": "application/json"},
            json={"audio_url": upload_url},
            timeout=30
        )
        t_res.raise_for_status()
        tid = t_res.json()["id"]

        # --- STT polling ---
        text = ""
        for _ in range(60):
            poll = requests.get(
                f"https://api.assemblyai.com/v2/transcript/{tid}",
                headers=aai_headers,
                timeout=20
            )
            pdata = poll.json()
            status = pdata.get("status")
            if status == "completed":
                text = (pdata.get("text") or "").strip()
                break
            if status == "error":
                return JSONResponse(status_code=502, content={
                    "error": pdata.get("error", "Transcription error"),
                    "fallback_text": "I'm having trouble connecting right now"
                })
            time.sleep(1)

        if not text:
            return JSONResponse(status_code=504, content={
                "error": "Transcription timed out or empty",
                "fallback_text": "I'm having trouble connecting right now"
            })

        # --- TTS (Murf) ---
        murf_headers = {"api-key": tts_key, "Content-Type": "application/json"}
        g = requests.post(
            "https://api.murf.ai/v1/speech/generate",
            headers=murf_headers,
            json={"text": text, "voice_id": "en-US-natalie", "format": "mp3"},
            timeout=60
        )
        g.raise_for_status()
        j = g.json()

        audio_url = j.get("audioFile")
        if isinstance(audio_url, dict):
            audio_url = audio_url.get("url")

        if not audio_url:
            job_id = j.get("id")
            if not job_id:
                return JSONResponse(status_code=502, content={
                    "error": "Murf did not return audio url",
                    "fallback_text": "I'm having trouble connecting right now"
                })
            for _ in range(30):
                jr = requests.get(f"https://api.murf.ai/v1/speech/{job_id}", headers=murf_headers, timeout=20)
                jj = jr.json()
                audio_url = jj.get("audioFile")
                if isinstance(audio_url, dict):
                    audio_url = audio_url.get("url")
                if audio_url:
                    break
                time.sleep(1)

        if not audio_url:
            return JSONResponse(status_code=502, content={
                "error": "Murf audio not ready",
                "fallback_text": "I'm having trouble connecting right now"
            })

        return {"audio_url": audio_url, "text": text}

    except requests.HTTPError as e:
        return JSONResponse(status_code=502, content={
            "error": f"Upstream error: {e.response.text[:500]}",
            "fallback_text": "I'm having trouble connecting right now"
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "error": str(e),
            "fallback_text": "I'm having trouble connecting right now"
        })

# Day 9: Unified LLM Bot (AUDIO or TEXT -> LLM -> Murf)
@app.post("/llm/query")
async def llm_query(request: Request, file: UploadFile = File(None)):
    try:
        content_type = request.headers.get("content-type", "")

        # multipart: audio file
        if "multipart/form-data" in content_type and file is not None:
            audio_bytes = await file.read()
            if not audio_bytes:
                return JSONResponse(status_code=400, content={"error": "Empty file"})

            aai_headers = {"authorization": ASSEMBLY_API_KEY}
            up = requests.post("https://api.assemblyai.com/v2/upload", headers=aai_headers, data=audio_bytes, timeout=60)
            up.raise_for_status()
            upload_url = up.json()["upload_url"]

            tr = requests.post(
                "https://api.assemblyai.com/v2/transcript",
                headers={**aai_headers, "content-type": "application/json"},
                json={"audio_url": upload_url},
                timeout=30
            )
            tr.raise_for_status()
            tid = tr.json()["id"]

            transcript = ""
            for _ in range(60):
                poll = requests.get(f"https://api.assemblyai.com/v2/transcript/{tid}", headers=aai_headers, timeout=20)
                pdata = poll.json()
                status = pdata.get("status")
                if status == "completed":
                    transcript = (pdata.get("text") or "").strip()
                    break
                if status == "error":
                    return JSONResponse(status_code=502, content={"error": pdata.get("error", "Transcription error")})
                time.sleep(1)

            if not transcript:
                return JSONResponse(status_code=504, content={"error": "Transcription timed out or empty"})

            llm_text = call_gemini_text(transcript)
            urls = murf_generate_chunked(llm_text, voice_id="en-US-natalie", chunk_limit=3000)
            return {"audio_url": urls[0], "audio_urls": urls, "text": transcript, "llm_text": llm_text}

        # JSON: text
        elif "application/json" in content_type:
            body = await request.json()
            user_text = (body or {}).get("text", "").strip()
            if not user_text:
                return JSONResponse(status_code=400, content={"error": "Missing 'text' in body"})

            llm_text = call_gemini_text(user_text)
            urls = murf_generate_chunked(llm_text, voice_id="en-US-natalie", chunk_limit=3000)
            return {"audio_url": urls[0], "audio_urls": urls, "llm_text": llm_text}

        else:
            return JSONResponse(
                status_code=400,
                content={"error": "Unsupported Content-Type. Send audio as multipart/form-data with 'file' or JSON with {'text': ...}."}
            )

    except requests.HTTPError as e:
        return JSONResponse(status_code=502, content={"error": f"Upstream error: {e.response.text[:500]}"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
# Day 10: Session chat (AUDIO -> STT -> history -> LLM -> history -> TTS)
@app.post("/agent/chat/{session_id}")
async def agent_chat(session_id: str, file: UploadFile = File(...), request: Request = None):
    # simulate failures via ?fail=agent|stt|llm|tts (script.js adds x-debug-fail)
    tag = request.headers.get("x-debug-fail")
    if tag in {"agent", "stt", "llm", "tts"}:
        raise UpstreamError(tag, "Forced failure for testing", 503)

    # ensure required envs exist (gives clean 500 with fallback_text if missing)
    require_env("ASSEMBLY_API_KEY")
    require_env("GEMINI_API_KEY")
    require_env("MURF_API_KEY")

    try:
        # --- STT ---
        audio_bytes = await file.read()
        if not audio_bytes:
            return JSONResponse(status_code=400, content={
                "error": "Empty file",
                "fallback_text": "I'm having trouble connecting right now"
            })

        aai_headers = {"authorization": ASSEMBLY_API_KEY}
        up = requests.post("https://api.assemblyai.com/v2/upload", headers=aai_headers, data=audio_bytes, timeout=60)
        up.raise_for_status()
        upload_url = up.json()["upload_url"]

        tr = requests.post(
            "https://api.assemblyai.com/v2/transcript",
            headers={**aai_headers, "content-type": "application/json"},
            json={"audio_url": upload_url},
            timeout=30
        )
        tr.raise_for_status()
        tid = tr.json()["id"]

        transcript = ""
        for _ in range(60):
            poll = requests.get(f"https://api.assemblyai.com/v2/transcript/{tid}", headers=aai_headers, timeout=20)
            pdata = poll.json()
            status = pdata.get("status")
            if status == "completed":
                transcript = (pdata.get("text") or "").strip()
                break
            if status == "error":
                return JSONResponse(status_code=502, content={
                    "error": pdata.get("error", "Transcription error"),
                    "fallback_text": "I'm having trouble connecting right now"
                })
            time.sleep(1)

        if not transcript:
            return JSONResponse(status_code=504, content={
                "error": "Transcription timed out or empty",
                "fallback_text": "I'm having trouble connecting right now"
            })

        # --- history: add user turn ---
        add_msg(session_id, "user", transcript)

        # --- LLM with history ---
        prompt = build_prompt_from_history(get_history(session_id))
        llm_text = call_gemini_text(prompt)  # may raise → caught below

        # --- history: add assistant turn ---
        add_msg(session_id, "assistant", llm_text)

        # --- TTS (chunk-safe) ---
        urls = murf_generate_chunked(llm_text, voice_id="en-US-natalie", chunk_limit=3000)

        return {
            "session_id": session_id,
            "text": transcript,           # user said
            "llm_text": llm_text,         # assistant reply
            "audio_url": urls[0],
            "audio_urls": urls,
            "turns": len(get_history(session_id)),
            "history": get_history(session_id),
        }

    except requests.HTTPError as e:
        return JSONResponse(status_code=502, content={
            "error": f"Upstream error: {e.response.text[:500]}",
            "fallback_text": "I'm having trouble connecting right now"
        })
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "error": str(e),
            "fallback_text": "I'm having trouble connecting right now"
        })

