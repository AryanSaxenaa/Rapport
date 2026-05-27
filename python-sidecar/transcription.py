import asyncio
import os

import httpx

_RETRYABLE = {429, 500, 503}


async def transcribe_audio_chunk(pcm_bytes: bytes) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key or not pcm_bytes:
        return ""

    for attempt in range(1, 4):
        try:
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
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in _RETRYABLE or attempt == 3:
                return ""
        except (httpx.ConnectError, httpx.TimeoutException):
            if attempt == 3:
                return ""
        await asyncio.sleep(2 ** attempt)
    return ""
