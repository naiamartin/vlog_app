import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend import database, models
from backend.routers import posts, profile, register

logging.basicConfig(
    filename=Path(__file__).resolve().parent.parent / "server.log",
    encoding="utf-8",
    level=logging.DEBUG,
)

# Create database tables if they do not exist yet.
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI()

# Keep the existing HTML pages and static CSS available.
templates = Jinja2Templates(
    directory=Path(__file__).resolve().parent.parent / "frontend" / "pages"
)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend" / "static"),
    name="static",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"message": "Hello, Microservice!"}


# Connect the endpoints defined in each router.
app.include_router(register.router)
app.include_router(profile.router)
app.include_router(posts.router)
