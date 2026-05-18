import os

import httpx


async def transcribe_audio_chunk(pcm_bytes: bytes) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or not pcm_bytes:
        return ""

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": ("chunk.wav", pcm_bytes, "audio/wav")},
            data={"model": "openai/whisper-large-v3-turbo"},
        )
        response.raise_for_status()
        data = response.json()
        return data.get("text", "")
