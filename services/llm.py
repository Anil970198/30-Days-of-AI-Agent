import google.generativeai as genai
import httpx
import os
from typing import List, Dict
from fastapi.concurrency import run_in_threadpool

async def call_gemini_llm(history: List[Dict[str, str]], system_prompt: str, api_key: str) -> str:
    """Async Gemini LLM call using threadpool for blocking SDK"""
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing")
    
    def _sync_gemini_call():
        # Build conversation prompt
        messages = [system_prompt, ""]
        for msg in history[-10:]:
            role = "User" if msg["role"] == "user" else "Assistant"
            messages.append(f"{role}: {msg['content']}")
        
        messages.append("Assistant:")
        prompt = "\n".join(messages)
        
        # Call Gemini (blocking)
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        
        return response.text.strip() if response.text else ""
    
    # Run blocking call in threadpool
    return await run_in_threadpool(_sync_gemini_call)

async def get_real_weather(city: str, weather_api_key: str = "") -> str:
    """Async weather data from OpenWeatherMap API using session key"""
    if not weather_api_key:
        return f"🌤️ Weather API key not configured. Please add your OpenWeatherMap API key in the ⚙️ Config dialog to get real weather for {city}."
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                'http://api.openweathermap.org/data/2.5/weather',
                params={
                    'q': city,
                    'appid': weather_api_key,
                    'units': 'metric'
                }
            )
            
            if response.status_code == 401:
                return f"🌤️ Invalid weather API key. Please check your OpenWeatherMap API key in the config."
            
            if response.status_code != 200:
                return f"🌤️ Could not get weather for {city}. Error: {response.status_code}"
            
            data = response.json()
            
            if data.get('cod') != 200:
                return f"🌤️ Weather data not found for {city}. Please check the city name."
            
            # Extract weather information
            main = data.get('main', {})
            weather_desc = data.get('weather', [{}])[0].get('description', 'No description')
            temp = main.get('temp')
            feels_like = main.get('feels_like')
            humidity = main.get('humidity')
            
            return (f"🌤️ Current weather in {city}: {weather_desc.capitalize()}, "
                    f"Temperature: {temp}°C (feels like {feels_like}°C), "
                    f"Humidity: {humidity}%")
            
    except Exception as e:
        return f"🌤️ Error getting weather for {city}: Network issue, please try again."

def detect_and_process_skills(text: str) -> str:
    """Process skills inline within conversation"""
    text_lower = text.lower().strip()
    
    # Calculator skill
    if any(word in text_lower for word in ["calculate", "calc", "what is", "*", "+", "-", "/"]):
        import re
        numbers_and_ops = re.findall(r'[\d+\-*/().\s]+', text)
        if numbers_and_ops:
            expr = numbers_and_ops[0].strip()
            try:
                allowed_chars = set("0123456789+-*/(). ")
                if all(c in allowed_chars for c in expr) and "__" not in expr:
                    result = eval(expr, {"__builtins__": {}}, {})
                    return f"🔢 Calculation: {expr} = {result}"
            except:
                return "🔢 I couldn't calculate that. Try a simple expression like 25 * 16."
    
    # Weather skill - ASYNC PROCESSING
    if "weather" in text_lower:
        city = "London"  # Default
        
        # Extract city name from speech
        if " in " in text_lower:
            parts = text_lower.split(" in ")
            if len(parts) > 1:
                city = parts[-1].strip().title()
        elif " for " in text_lower:
            parts = text_lower.split(" for ")
            if len(parts) > 1:
                city = parts[-1].strip().title()
        
        # Return marker for async processing in main function
        return f"WEATHER_REQUEST:{city}"
    
    return ""
