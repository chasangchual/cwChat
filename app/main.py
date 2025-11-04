from fastapi import FastAPI, Request

from starlette.staticfiles import StaticFiles
from app.routers import app_router
from app.utils.session_utils import SessionUtils, SESSION_COOKIE_NAME
cw_chat_app = FastAPI()

cw_chat_app.mount("/static", StaticFiles(directory="static"), name="static")

@cw_chat_app.middleware("http")
async def inject_session_cookie(request: Request, call_next):
    # Why: Ensure every visitor gets a stable session id
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    new_session = False
    if not session_id:
        session_id = SessionUtils.get_or_create_session_id(None)
        new_session = True

    response = await call_next(request)
    if new_session:
        SessionUtils.set_session_cookie(response, session_id)
    return response

cw_chat_app.include_router(app_router.chat_app_router)
