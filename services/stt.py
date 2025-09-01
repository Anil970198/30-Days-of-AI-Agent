import assemblyai as aai
from typing import Optional
from fastapi.concurrency import run_in_threadpool

async def transcribe_audio(file_path: str, api_key: Optional[str] = None) -> str:
    """Async Speech-to-text using AssemblyAI"""
    if not api_key:
        raise RuntimeError("ASSEMBLYAI_API_KEY missing")
    
    def _sync_transcribe():
        aai.settings.api_key = api_key
        transcriber = aai.Transcriber()
        result = transcriber.transcribe(file_path)
        return result.text or ""
    
    # Run blocking transcription in threadpool
    return await run_in_threadpool(_sync_transcribe)
