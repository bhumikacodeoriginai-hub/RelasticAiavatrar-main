"""
D-ID talking-avatar integration (Talks API).

Turns a piece of text into a short MP4 of a REAL human face speaking it, with
accurate lip-sync. This is optional and fully isolated: if D-ID is not
configured or fails, the endpoint returns success=false and the frontend simply
falls back to the existing 3D avatar. No other app logic depends on this.

Flow:
    POST {base}/talks   -> { id }
    GET  {base}/talks/{id} (poll) -> { status: "done", result_url: "<mp4>" }

Auth: D-ID expects `Authorization: Basic <api_key>` where <api_key> is the key
exactly as shown in the D-ID console (it already encodes username:password).
"""

import asyncio
import base64
from typing import Optional

import httpx
import structlog
from fastapi import APIRouter
from pydantic import BaseModel

from config import settings

logger = structlog.get_logger()

router = APIRouter(prefix="/api/did", tags=["did-avatar"])


class SpeakRequest(BaseModel):
    text: str


def _auth_header() -> str:
    """Build the Authorization header value for D-ID.

    D-ID keys are usually of the form `email:token`. If the configured key
    already looks base64-encoded (no colon), we send it as-is; otherwise we
    base64-encode it. Either way we prefix with 'Basic '.
    """
    key = (settings.did_api_key or "").strip()
    if not key:
        return ""
    if ":" in key:
        encoded = base64.b64encode(key.encode("utf-8")).decode("utf-8")
        return f"Basic {encoded}"
    # Already looks encoded / opaque token.
    return f"Basic {key}"


async def create_talking_video(text: str) -> Optional[str]:
    """Create a D-ID talk from text and return the resulting MP4 URL.

    Returns None on any failure (disabled, network, rejection, timeout) so the
    caller can gracefully fall back.
    """
    if not settings.did_enabled:
        return None
    if not text or not text.strip():
        return None

    auth = _auth_header()
    if not auth:
        return None

    script = {
        "type": "text",
        "input": text.strip(),
    }
    # Optional voice provider (Microsoft voices are supported by D-ID).
    if settings.did_voice_id:
        script["provider"] = {"type": "microsoft", "voice_id": settings.did_voice_id}

    payload = {"script": script}
    # Only include source_url if configured; otherwise D-ID uses a default
    # presenter (avoids failing when a custom image is not reachable/valid).
    if settings.did_source_url and settings.did_source_url.strip():
        payload["source_url"] = settings.did_source_url.strip()

    headers = {
        "Authorization": auth,
        "Content-Type": "application/json",
        "accept": "application/json",
    }

    base = settings.did_api_base.rstrip("/")

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # 1) Create the talk
            resp = await client.post(f"{base}/talks", json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.warning(
                    "D-ID create talk failed",
                    status=resp.status_code,
                    body=resp.text[:300],
                )
                return None
            talk_id = resp.json().get("id")
            if not talk_id:
                logger.warning("D-ID: no talk id returned")
                return None

            # 2) Poll for completion (Talks render in a few seconds).
            for _ in range(30):  # up to ~30 * 1s = 30s
                await asyncio.sleep(1.0)
                poll = await client.get(f"{base}/talks/{talk_id}", headers=headers)
                if poll.status_code >= 400:
                    logger.warning("D-ID poll failed", status=poll.status_code)
                    return None
                data = poll.json()
                status = data.get("status")
                if status == "done":
                    url = data.get("result_url")
                    logger.info("D-ID talk ready", talk_id=talk_id)
                    return url
                if status in ("error", "rejected"):
                    logger.warning("D-ID talk failed", status=status, detail=str(data)[:300])
                    return None
            logger.warning("D-ID talk timed out", talk_id=talk_id)
            return None
    except Exception as e:
        logger.warning("D-ID request error", error=str(e))
        return None


@router.get("/status")
async def did_status():
    """Report whether D-ID is enabled (so the frontend can decide to use it)."""
    return {
        "enabled": settings.did_enabled,
        "has_source": bool(settings.did_source_url and settings.did_source_url.strip()),
    }


@router.post("/speak")
async def did_speak(req: SpeakRequest):
    """Return a real-human talking-video URL for the given text.

    Always returns 200 with success flag so the frontend can fall back cleanly.
    """
    if not settings.did_enabled:
        return {"success": False, "reason": "disabled"}
    url = await create_talking_video(req.text)
    if url:
        return {"success": True, "video_url": url}
    return {"success": False, "reason": "generation_failed"}
