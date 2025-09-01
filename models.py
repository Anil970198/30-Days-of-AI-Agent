from pydantic import BaseModel
from typing import Optional, List, Dict

class ConfigRequest(BaseModel):
    murf: str = ""
    aai: str = ""
    gemini: str = ""
    weather: str = ""
    search: str = ""          # 🆕 ADD SEARCH KEY
    persona: str = "neutral"

class ChatResponse(BaseModel):
    ok: bool
    transcript: str
    llm_text: str
    audio_url: str
    history: List[Dict[str, str]]
    fallback: Optional[bool] = False

def error_response(stage: str, error: str, status_code: int = 500):
    return {"status_code": status_code, "content": {"ok": False, "stage": stage, "error": error}}
