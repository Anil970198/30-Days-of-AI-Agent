from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import os
import asyncio
from tempfile import NamedTemporaryFile
from typing import Dict, List

# Import async services
from services.stt import transcribe_audio
from services.tts import generate_speech
from services.llm import call_gemini_llm, detect_and_process_skills, get_real_weather
from models import ConfigRequest, ChatResponse, error_response
from services.search import tavily_web_search


# Load environment
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

# App setup
app = FastAPI(title="Voice Agent - FAST & ASYNC")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

# Static files and templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Configuration (same as before)
PERSONAS = {
    "neutral": {"system": "You are a helpful, concise voice assistant. Reply naturally and briefly.", "voice": "en-US-natalie"},
    "robot": {"system": "You speak like a friendly robot assistant: clear, compact, and precise.", "voice": "en-US-natalie"},
    "pirate": {"system": "Talk like a pirate, with playful 'Arrr!' and nautical flavor, but keep it concise.", "voice": "en-US-natalie"},
    "coach": {"system": "You are an encouraging coach. Be supportive, energetic, and pragmatic.", "voice": "en-US-natalie"},
}

SESSION_CFG: Dict[str, Dict[str, str]] = {}
CHAT_STORE: Dict[str, List[Dict[str, str]]] = {}
AGENT_LOCKS: Dict[str, asyncio.Lock] = {}

# Utility functions (same as before)
def get_api_key(session_id: str, key_type: str) -> str:
    session_key = SESSION_CFG.get(session_id, {}).get(key_type, "").strip()
    if session_key:
        return session_key
    return os.getenv(f"{key_type.upper()}_API_KEY", "")

def get_persona_system(session_id: str) -> str:
    persona = SESSION_CFG.get(session_id, {}).get("persona", "neutral")
    return PERSONAS.get(persona, PERSONAS["neutral"])["system"]

def get_persona_voice(session_id: str) -> str:
    persona = SESSION_CFG.get(session_id, {}).get("persona", "neutral")
    return PERSONAS.get(persona, PERSONAS["neutral"])["voice"]

def get_chat_history(session_id: str) -> List[Dict[str, str]]:
    return CHAT_STORE.setdefault(session_id, [])

def add_to_history(session_id: str, role: str, content: str):
    get_chat_history(session_id).append({"role": role, "content": content})

# Routes
@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# In your main.py, update the save_config function:

@app.post("/config/{session_id}")
async def save_config(session_id: str, config: ConfigRequest):
    try:
        SESSION_CFG[session_id] = {
            "murf": config.murf,
            "aai": config.aai,
            "gemini": config.gemini,
            "weather": config.weather,
            "search": config.search,      # 🆕 STORE SEARCH KEY
            "persona": config.persona
        }
        return {"ok": True, "message": "Configuration saved"}
    except Exception as e:
        return JSONResponse(**error_response("config", str(e)))


# Update get_api_key function to handle weather:
def get_api_key(session_id: str, key_type: str) -> str:
    session_key = SESSION_CFG.get(session_id, {}).get(key_type, "").strip()
    if session_key:
        return session_key
    
    # Fallback to environment variables
    fallback_keys = {
        "murf": os.getenv("MURF_API_KEY", ""),
        "aai": os.getenv("ASSEMBLYAI_API_KEY", ""),
        "gemini": os.getenv("GEMINI_API_KEY", ""),
        "weather": os.getenv("OPENWEATHERMAP_API_KEY", ""),
        "search": os.getenv("TAVILY_API_KEY", "")  # 🆕 ADD SEARCH FALLBACK
    }
    return fallback_keys.get(key_type, "")


@app.post("/agent/chat/{session_id}", response_model=ChatResponse)
async def agent_chat(
    session_id: str,
    file: UploadFile = File(...),
    web_search: bool = Form(False),
    concise: bool = Form(False)
):
    """FULLY ASYNC PIPELINE with Weather + Web Search"""
    
    if session_id not in AGENT_LOCKS:
        AGENT_LOCKS[session_id] = asyncio.Lock()
    
    async with AGENT_LOCKS[session_id]:
        temp_file = None
        try:
            # Step 1: Save uploaded audio file
            with NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
                tmp.write(await file.read())
                temp_file = tmp.name
            
            # Step 2: Get ALL API keys
            aai_key = get_api_key(session_id, "aai")
            gemini_key = get_api_key(session_id, "gemini")
            murf_key = get_api_key(session_id, "murf")
            weather_key = get_api_key(session_id, "weather")
            search_key = get_api_key(session_id, "search")  # 🆕 GET SEARCH KEY
            
            print(f"🔍 Web Search: {'✅ Enabled' if web_search else '❌ Disabled'}")
            print(f"🔍 Search API Key: {'✅ Found' if search_key else '❌ Missing'}")
            
            # Step 3: ASYNC Speech-to-Text
            try:
                transcript = await transcribe_audio(temp_file, aai_key)
                if not transcript:
                    raise RuntimeError("Empty transcript")
                print(f"🎤 Transcript: {transcript}")
            except Exception as e:
                return JSONResponse(**error_response("stt", str(e), 502))
            
            # Step 4: Skills detection
            skill_result = detect_and_process_skills(transcript)
            print(f"🛠️ Skill detected: {skill_result or 'None'}")
            
            # Step 5: Handle weather requests ASYNC
            if skill_result.startswith("WEATHER_REQUEST:"):
                city = skill_result.replace("WEATHER_REQUEST:", "")
                print(f"🌤️ Getting weather for: {city}")
                skill_result = await get_real_weather(city, weather_key)
                print(f"🌤️ Weather result: {skill_result}")
            
            # Step 6: Handle web search ASYNC (NEW!)
            web_context = ""
            if web_search and transcript:
                print(f"🔍 Performing web search for: {transcript}")
                web_context = await tavily_web_search(transcript, search_key)
                print(f"🔍 Search results: {web_context}")
            
            # Step 7: Build enriched conversation context
            history = get_chat_history(session_id)
            system_prompt = get_persona_system(session_id)
            
            user_input = transcript
            
            # Add skill results
            if skill_result:
                user_input = f"{transcript}\n\n{skill_result}"
            
            # Add web search context
            if web_context:
                user_input = f"{user_input}\n\n{web_context}\n\nPlease answer based on the above search results and be concise."
            
            if concise:
                user_input = f"Answer briefly: {user_input}"
            
            add_to_history(session_id, "user", user_input)
            
            # Step 8: ASYNC LLM Generation
            try:
                llm_response = await call_gemini_llm(history, system_prompt, gemini_key)
                if not llm_response:
                    llm_response = "Let's talk about something else. How can I help?"
                print(f"🤖 LLM response: {llm_response}")
            except Exception as e:
                return JSONResponse(**error_response("llm", str(e), 502))
            
            add_to_history(session_id, "assistant", llm_response)
            
            # Step 9: ASYNC Text-to-Speech
            voice = get_persona_voice(session_id)
            success, audio_url = await generate_speech(llm_response, voice, murf_key)
            print(f"🔊 TTS: {'✅ Success' if success else '❌ Failed'}")
            
            # Step 10: Return complete response
            return ChatResponse(
                ok=True,
                transcript=transcript,
                llm_text=llm_response,
                audio_url=audio_url,
                history=[{"role": msg["role"], "content": msg["content"]} for msg in history],
                fallback=not success
            )
            
        except Exception as e:
            print(f"❌ Agent pipeline error: {e}")
            return JSONResponse(**error_response("agent", str(e)))
        
        finally:
            # Step 11: Cleanup temp file
            if temp_file:
                try:
                    os.remove(temp_file)
                except:
                    pass



if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
