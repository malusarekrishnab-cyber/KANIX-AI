import re
from pathlib import Path

file_path = Path(r"c:\Users\malus\ALL VS CODE PROJECT\KANIX -AI\Mark-XXXIX-OR\actions\file_processor.py")
content = file_path.read_text(encoding="utf-8")

# 1. Imports
content = re.sub(r'import google\.generativeai as genai\n+', 'from core.llm_provider import LLMProvider\nfrom core.stt import speech_to_text\n\n', content)

# 2. Remove API key & _gemini_client
content = re.sub(r'def _get_api_key.*?\n\s+return json\.load.*?gemini_api_key.*?\n', '', content, flags=re.DOTALL)
content = re.sub(r'def _gemini_client\(\).*?return genai\.GenerativeModel\("gemini-2\.5-flash"\)\n', '', content, flags=re.DOTALL)

# 3. _process_image
content = content.replace("model  = _gemini_client()", "model = LLMProvider()")
content = content.replace("model    = _gemini_client()", "model = LLMProvider()")
content = content.replace("model   = _gemini_client()", "model = LLMProvider()")
content = content.replace("response = model.generate_content([prompt, img])\n            result   = response.text.strip()", "result = model.chat_vision(prompt=prompt, image_path=str(path))")

# 4. _process_pdf
content = content.replace("response = model.generate_content(prompt_map.get(action, f\"Analyze:\\n\\n{text}\"))\n            result   = response.text.strip()", "result = model.chat(prompt_map.get(action, f\"Analyze:\\n\\n{text}\")).get('content', '')")

# 5. _process_text_doc
content = content.replace("response = model.generate_content(prompt_map[action])\n        result   = response.text.strip()", "result = model.chat(prompt_map[action]).get('content', '')")

# 6. _process_data (line 348)
content = content.replace("response = model.generate_content(prompt)\n            return response.text.strip()", "return model.chat(prompt).get('content', '')")

# 7. _process_data (line 402)
content = content.replace("""        response = model.generate_content(
            f"Task: {action}\\nDataset ({len(df)} rows, cols: {list(df.columns)}):\\n{preview}"
        )
        return response.text.strip()""", """        return model.chat(f"Task: {action}\\nDataset ({len(df)} rows, cols: {list(df.columns)}):\\n{preview}").get('content', '')""")

# 8. _process_json (line 433)
content = content.replace("response = model.generate_content(prompt)\n            return response.text.strip()", "return model.chat(prompt).get('content', '')")

# 9. _process_code (line 497)
content = content.replace("response = model.generate_content(prompt)\n        result   = response.text.strip()", "result = model.chat(prompt).get('content', '')")

# 10. _process_audio (line 537)
audio_old = """            model   = _gemini_client()
            content = path.read_bytes()
            mime    = {
                "mp3": "audio/mp3", "wav": "audio/wav",
                "ogg": "audio/ogg", "m4a": "audio/mp4",
                "aac": "audio/aac", "flac": "audio/flac",
            }.get(path.suffix.lstrip(".").lower(), "audio/mpeg")
            response = model.generate_content([
                "Transcribe all speech in this audio file accurately.",
                {"mime_type": mime, "data": content}
            ])
            result = response.text.strip()"""
audio_new = """            import wave, io, subprocess, tempfile
            # Convert audio to wav in memory using ffmpeg
            wav_path = Path(tempfile.mktemp(suffix=".wav"))
            subprocess.run(["ffmpeg", "-i", str(path), "-ar", "16000", "-ac", "1", "-f", "s16le", str(wav_path)], capture_output=True, timeout=60)
            pcm_data = wav_path.read_bytes()
            wav_path.unlink(missing_ok=True)
            result = speech_to_text(pcm_data, sample_rate=16000, channels=1)"""
content = content.replace(audio_old, audio_new)

# 11. _process_pptx (line 769)
content = content.replace("response = model.generate_content(prompt)\n            return response.text.strip()", "return model.chat(prompt).get('content', '')")

# 12. Fallback (line 802)
content = content.replace("response = model.generate_content(prompt)\n            return response.text.strip()", "return model.chat(prompt).get('content', '')")

file_path.write_text(content, encoding="utf-8")
print("Refactoring complete.")
