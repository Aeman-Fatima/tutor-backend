import json
import time
import anthropic
from google import genai
from google.genai import types
from google.genai import errors
from core.filter import _SYSTEM

# Configuration flag
# LLM = 'gemini' 
LLM = 'anthropic' 

def api_response(system_prompt, model="claude-sonnet-4-6", tokens=1024, prompt_label=None, content_text=None, user_message=None, json_mode=True) -> str:
    full_prompt = f"{prompt_label}{content_text}" if prompt_label and content_text else user_message
    
    if LLM == 'anthropic':
        client_anthropic = anthropic.Anthropic()

        if isinstance(system_prompt, list):
            anthropic_system = system_prompt
        else:
            anthropic_system = [{"type": "text", "text": str(system_prompt), "cache_control": {"type": "ephemeral"}}]

        response = client_anthropic.messages.create(
            model=model,
            max_tokens=tokens,
            system=anthropic_system,
            messages=[{"role": "user", "content": full_prompt}],
        )
        # Returns clean text only
        return response.content[0].text.strip()

    elif LLM == 'gemini':
        client_gemini = genai.Client()
        
        if isinstance(system_prompt, list) and len(system_prompt) > 0 and isinstance(system_prompt, dict):
            clean_system = system_prompt.get("text", "")
        elif isinstance(system_prompt, dict):
            clean_system = system_prompt.get("text", "")
        else:
            clean_system = str(system_prompt)
            
        config = types.GenerateContentConfig(
            max_output_tokens=tokens,         
            system_instruction=clean_system, 
            temperature=0.1 
        )
        
        if json_mode:
            config.response_mime_type = "application/json"
        
        gemini_model = "gemini-2.5-flash-lite"
        
        max_retries = 3
        pause_time = 10  
        
        for attempt in range(max_retries):
            try:
                response = client_gemini.models.generate_content(
                    model=gemini_model,
                    contents=full_prompt,  
                    config=config
                )
                
                raw_text = response.text.strip()
                
                if json_mode:
                    try:
                        data = json.loads(raw_text)
                        # If Gemini used "response" but your main code expects "rewritten_response"
                        if "response" in data and "rewritten_response" not in raw_text:
                            data["rewritten_response"] = data.pop("response")
                            raw_text = json.dumps(data)
                        # Conversely, if your main code expects "response" but Gemini used "rewritten_response"
                        elif "rewritten_response" in data and "response" not in raw_text:
                            data["response"] = data.pop("rewritten_response")
                            raw_text = json.dumps(data)
                    except json.JSONDecodeError:
                        pass 
                
                return raw_text
                
            except errors.ClientError as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    print(f"Free tier limit hit. Retrying in {pause_time}s...")
                    time.sleep(pause_time)
                    continue
                raise e  
                
        raise Exception("Gemini quota limits exhausted after multiple retries.")

    
def image_response(image_data: str, media_type: str, _SYSTEM: str) -> str:
    if LLM == 'anthropic':
        client_anthropic = anthropic.Anthropic()
        response = client_anthropic.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_data}},
                        {"type": "text", "text": "Transcribe the student's math solution shown in this image."}
                    ],
                }
            ],
        )
        return response.content[0].text.strip()

    elif LLM == 'gemini':
        client_gemini = genai.Client()
        
        if isinstance(_SYSTEM, list) and len(_SYSTEM) > 0 and isinstance(_SYSTEM[0], dict):
            clean_system = _SYSTEM[0].get("text", "")
        elif isinstance(_SYSTEM, dict):
            clean_system = _SYSTEM.get("text", "")
        else:
            clean_system = str(_SYSTEM)

        config = types.GenerateContentConfig(
            max_output_tokens=512,
            system_instruction=clean_system
        )
        
        image_part = types.Part.from_bytes(data=image_data, mime_type=media_type)
        gemini_model = "gemini-2.5-flash-lite"
        
        max_retries = 3
        pause_time = 10
        
        for attempt in range(max_retries):
            try:
                response = client_gemini.models.generate_content(
                    model=gemini_model,
                    contents=[image_part, "Transcribe the student's math solution shown in this image."],
                    config=config
                )
                return response.text.strip()
                
            except errors.ClientError as e:
                if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e):
                    print(f"Free tier limit hit on image. Retrying in {pause_time}s...")
                    time.sleep(pause_time)
                    continue
                raise e
                
        raise Exception("Gemini image quota limits exhausted after multiple retries.")
    
    else:
        raise ValueError(f"Unsupported LLM: {LLM}")
