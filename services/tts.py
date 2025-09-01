import httpx
from typing import Tuple

async def generate_speech(text: str, voice: str, api_key: str) -> Tuple[bool, str]:
    """Async Text-to-speech using Murf AI"""
    if not api_key:
        return False, "/static/fallback.mp3"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.murf.ai/v1/speech/generate",
                headers={
                    "api-key": api_key,
                    "Content-Type": "application/json"
                },
                json={
                    "text": text[:3000],
                    "voice_id": voice,
                    "style": "Conversational",
                    "format": "mp3"
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                audio_url = data.get("audioFile")
                if audio_url:
                    return True, audio_url
                    
    except Exception as e:
        print(f"TTS error: {e}")
    
    return False, "/static/fallback.mp3"
