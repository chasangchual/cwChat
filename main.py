from fastapi import FastAPI

from starlette.staticfiles import StaticFiles

my_app = FastAPI()

my_app.mount("/static", StaticFiles(directory="static"), name="static")
