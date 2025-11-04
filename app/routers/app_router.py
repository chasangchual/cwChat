from fastapi import APIRouter, Request, Cookie, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from dependency_injector.wiring import inject, Provide
from typing import Optional
import secrets
from fastapi.responses import HTMLResponse, RedirectResponse
from datetime import datetime, timezone
from app.utils.session_utils import SESSION_COOKIE_NAME, SessionUtils
from app.utils.date_utils import DateUtils
from app.models.chat_message import ChatMessage, MemoryStore
chat_app_router = APIRouter(
    prefix="/app"
)

templates = Jinja2Templates(directory="templates")

@chat_app_router.get("/", response_class=RedirectResponse)
async def root():
    return "/chat"


@chat_app_router.get("/chat", response_class=HTMLResponse)
@inject
async def chat_page(request: Request, session_id: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME)):
    sid = SessionUtils.get_or_create_session_id(session_id)
    # First time visitors still get cookie via middleware; we also pass sid to template for initial state
    parms = {
        "request": request,
        "session_id": sid,
        "nonce": secrets.token_urlsafe(16),  # CSP nonce if you add CSP
        "title": "Web ChatBot",
    }
    return templates.TemplateResponse("chat.html", parms)


@chat_app_router.websocket("/ws")
async def ws_chat(websocket: WebSocket):
    # Accept ASAP for handshake reliability
    await websocket.accept()
    try:
        # Expect a hello with session id
        hello = await websocket.receive_json()
        if not isinstance(hello, dict) or hello.get("type") != "hello":
            await websocket.close(code=1002)
            return
        session_id = hello.get("session_id") or SessionUtils.get_or_create_session_id(None)

        while True:
            event = await websocket.receive_json()
            etype = event.get("type")

            if etype == "user_message":
                text = (event.get("text") or "").strip()
                if not text:
                    await websocket.send_json({"type": "error", "error": "Message is empty."})
                    continue

                # Save user message
                MemoryStore.setdefault(session_id, []).append(
                    ChatMessage(role="user", content=text, at=DateUtils.now_iso())
                )
                await websocket.send_json({"type": "ack"})

                # Typing start
                await websocket.send_json({"type": "typing", "state": True})

                # Demo file payload (if provided)
                f = event.get("file")
                if f and isinstance(f, dict):
                    name = f.get("name")
                    size = f.get("size")
                    # Attach a synthetic assistant note acknowledging receipt
                    MemoryStore[session_id].append(
                        ChatMessage(
                            role="assistant",
                            content=f"(Received file: {name}, {size} bytes)",
                            at=DateUtils.now_iso(),
                            meta={"kind": "file-receipt"},
                        )
                    )
                    await websocket.send_json(
                        {"type": "assistant_message", "message": {"role": "assistant", "content": f"(Received {name}, {size} bytes)"}}
                    )

                # Build assistant reply
                reply = await demo_bot_reply(text)

                # Stream assistant reply
                await SessionUtils.stream_assistant(websocket, reply)

                # Save assistant message
                MemoryStore.setdefault(session_id, []).append(
                    ChatMessage(role="assistant", content=reply, at=DateUtils.now_iso())
                )

                # Typing end
                await websocket.send_json({"type": "typing", "state": False})

            elif etype == "ping":
                await websocket.send_json({"type": "pong"})

            else:
                await websocket.send_json({"type": "error", "error": f"Unknown event: {etype}"})

    except WebSocketDisconnect:
        # Client disconnected; nothing to do
        return
    except Exception as exc:
        # Defensive error surface to client
        try:
            await websocket.send_json({"type": "error", "error": f"Server error: {exc}"})
        except Exception:
            pass
        finally:
            await websocket.close(code=1011)

async def demo_bot_reply(user_text: str) -> str:
    """
    Replace with your LLM call. Kept simple for clarity.
    """
    # A tiny, deterministic toy response with "tools"
    prefix = "You said:"
    if user_text.strip().lower() in {"hi", "hello", "hey"}:
        return "Hey! How can I help you today?"
    if user_text.strip().lower().startswith("/time"):
        return f"Current UTC time is {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}."
    return f"{prefix} “{user_text.strip()}”. Here’s a helpful response placeholder."