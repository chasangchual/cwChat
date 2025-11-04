import asyncio
from typing import Optional
import uuid
from fastapi import Response, WebSocket

SESSION_COOKIE_NAME = "chat_session_id"
SESSION_COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days
SESSION_ID_LENGTH = 64

class SessionUtils:
    @classmethod
    def get_or_create_session_id(cls, session_id: Optional[str]) -> str:
        if session_id and len(session_id) <= SESSION_ID_LENGTH:
            return session_id
        return uuid.uuid4().hex

    @classmethod
    def set_session_cookie(cls, resp: Response, session_id: str) -> None:
        # Why: Sticky history per browser without auth
        resp.set_cookie(
            key=SESSION_COOKIE_NAME,
            value=session_id,
            max_age=SESSION_COOKIE_MAX_AGE,
            httponly=True,
            secure=False,  # set True behind TLS
            samesite="lax",  # Helps mitigate CSRF attacks
            path="/",
        )

    @classmethod
    async def stream_assistant(cls, ws: WebSocket, full_text: str):
        """
        Chunk text to simulate streaming; your LLM stream goes here.
        Why: Better UX + typing indicator parity.
        """
        chunks = []
        words = full_text.split()
        buf = []
        for w in words:
            buf.append(w)
            if len(buf) >= 4:
                chunks.append(" ".join(buf) + " ")
                buf = []
        if buf:
            chunks.append(" ".join(buf))
        for c in chunks:
            await ws.send_json({"type": "token", "data": c})
            await asyncio.sleep(0.05)
        await ws.send_json({"type": "done"})