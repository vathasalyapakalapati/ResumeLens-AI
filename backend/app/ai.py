"""Thin clients for the free AI APIs: chat with a JSON reply (Groq or Gemini) and speech-to-text
(Groq Whisper). Callers decide what to do when these raise; nothing here retries or falls back.
"""

import json

import httpx

from .config import get_settings

TIMEOUT = 90.0


def chat_available() -> bool:
    s = get_settings()
    return (s.llm_provider == "groq" and bool(s.groq_api_key)) or (
        s.llm_provider == "gemini" and bool(s.google_api_key)
    )


def transcription_available() -> bool:
    return bool(get_settings().groq_api_key)


def engine_name() -> str:
    s = get_settings()
    return f"groq:{s.groq_model}" if s.llm_provider == "groq" else f"gemini:{s.gemini_model}"


def chat_json(system: str, user: str, temperature: float = 0.0) -> dict:
    """Send one system + user message and parse the model's JSON object reply."""
    s = get_settings()
    if s.llm_provider == "groq":
        res = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {s.groq_api_key}"},
            json={
                "model": s.groq_model,
                "temperature": temperature,
                "response_format": {"type": "json_object"},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            },
            timeout=TIMEOUT,
        )
        res.raise_for_status()
        raw = res.json()["choices"][0]["message"]["content"]
    else:
        res = httpx.post(
            f"https://generativelanguage.googleapis.com/v1beta/models/{s.gemini_model}:generateContent",
            headers={"x-goog-api-key": s.google_api_key},
            json={
                "systemInstruction": {"parts": [{"text": system}]},
                "contents": [{"role": "user", "parts": [{"text": user}]}],
                "generationConfig": {"temperature": temperature, "responseMimeType": "application/json"},
            },
            timeout=TIMEOUT,
        )
        res.raise_for_status()
        raw = res.json()["candidates"][0]["content"]["parts"][0]["text"]
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("model did not return a JSON object")
    return data


def transcribe(audio: bytes, filename: str, content_type: str) -> str:
    """Speech to text with Groq's hosted Whisper."""
    s = get_settings()
    res = httpx.post(
        "https://api.groq.com/openai/v1/audio/transcriptions",
        headers={"Authorization": f"Bearer {s.groq_api_key}"},
        files={"file": (filename, audio, content_type)},
        data={"model": s.groq_stt_model, "language": "en", "response_format": "json", "temperature": "0"},
        timeout=TIMEOUT,
    )
    res.raise_for_status()
    return str(res.json().get("text") or "").strip()
