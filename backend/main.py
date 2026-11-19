import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from fastapi.middleware.cors import CORSMiddleware
from pydantic import EmailStr
from pwdlib import PasswordHash
from supabase import create_client

from backend import database, models
from backend.schemas import blog, user
from backend.utils.image_processing import MAX_SIZE, process_image


logging.basicConfig(
    filename=Path(__file__).resolve().parent.parent / "server.log",
    encoding="utf-8",
    level=logging.DEBUG,
)

# Create all tables in the database
models.Base.metadata.create_all(bind=database.engine)

# Create the FastAPI application
app = FastAPI()
templates = Jinja2Templates(
    directory=Path(__file__).resolve().parent.parent / "frontend" / "pages"
)
app.mount(
    "/static",
    StaticFiles(directory=Path(__file__).resolve().parent.parent / "frontend" / "static"),
    name="static",
)
password_hash = PasswordHash.recommended()

# Add CORS middleware to allow React frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React's default port
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


# Dependency to get database session
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# REGISTER
@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="profile/register.html",
        context={"message": None},
    )


@app.post("/register", response_class=HTMLResponse)
def register(
    request: Request,
    email: EmailStr = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    picture: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    existing_user = (
        db.query(models.User)
        .filter((models.User.username == username) | (models.User.email == email))
        .first()
    )
    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="profile/register.html",
            context={"message": "That username or email is already registered."},
            status_code=409,
        )

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    if not supabase_url or not supabase_key:
        raise HTTPException(
            status_code=500,
            detail="Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env.",
        )

    image_bytes = picture.file.read(MAX_SIZE + 1)
    if len(image_bytes) > MAX_SIZE:
        return templates.TemplateResponse(
            request=request,
            name="profile/register.html",
            context={"message": "Choose an image smaller than 7 MB."},
            status_code=400,
        )

    try:
        processed_image = process_image(image_bytes)
    except (OSError, ValueError):
        return templates.TemplateResponse(
            request=request,
            name="profile/register.html",
            context={"message": "Choose a valid PNG, JPEG, or WebP image."},
            status_code=400,
        )

    bucket = os.getenv("SUPABASE_PICTURE_BUCKET", "user_pictures")
    image_path = f"{uuid4().hex}.png"
    supabase = create_client(supabase_url, supabase_key)
    try:
        supabase.storage.from_(bucket).upload(
            image_path,
            processed_image,
            file_options={"content-type": "image/png", "upsert": "false"},
        )
        image_url = supabase.storage.from_(bucket).get_public_url(image_path)
    except Exception:
        logging.exception("Supabase profile photo upload failed")
        return templates.TemplateResponse(
            request=request,
            name="profile/register.html",
            context={"message": "The photo could not be uploaded. Please try again."},
            status_code=502,
        )

    db_user = models.User(
        email=email,
        username=username,
        picture=image_url,
        password_hash=password_hash.hash(password),
        is_admin=False,
    )
    db.add(db_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        try:
            supabase.storage.from_(bucket).remove([image_path])
        except Exception:
            logging.exception("Could not remove profile photo after registration failed")
        return templates.TemplateResponse(
            request=request,
            name="profile/register.html",
            context={"message": "That username is already registered."},
            status_code=409,
        )
    except Exception:
        db.rollback()
        try:
            supabase.storage.from_(bucket).remove([image_path])
        except Exception:
            logging.exception("Could not remove profile photo after registration failed")
        raise

    return templates.TemplateResponse(
        request=request,
        name="profile/register.html",
        context={"message": "Account created. You can now log in."},
        status_code=201,
    )


# LOGIN


@app.get("/")
def read_root():
    return {"message": "Hello, Microservice!"}


# CREATE - Add a new user
@app.post("/users/", response_model=user.User)
def create_user(user: user.UserCreate, db: Session = Depends(get_db)):
    user_data = user.model_dump(exclude={"password"})
    db_user = models.User(
        **user_data,
        password_hash=password_hash.hash(user.password),
    )
    db.add(db_user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Username is already registered")
    db.refresh(db_user)
    return db_user


# READ - Get all users
@app.get("/users/", response_model=list[user.User])
def read_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    users = db.query(models.User).offset(skip).limit(limit).all()
    return users


# READ - Get a single user by ID
@app.get("/users/{user_id}", response_model=user.User)
def read_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


# UPDATE - Update an existing user
@app.put("/users/{user_id}", response_model=user.User)
def update_user(
    user_id: int,
    user: user.UserUpdate,
    db: Session = Depends(get_db),
):

    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if user.is_admin is not None:
        raise HTTPException(status_code=403, detail="Admin status cannot be changed here")

    updates = user.model_dump(
        exclude_unset=True,
        exclude={"password", "is_admin"},
    )
    for field, value in updates.items():
        setattr(db_user, field, value)
    if user.password is not None:
        db_user.password_hash = password_hash.hash(user.password)

    db.commit()
    db.refresh(db_user)
    return db_user


# DELETE - Remove a user
@app.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()
    return {"message": "User deleted successfully"}


@app.get("/blogs/", response_model=list[blog.Blog])
def read_blogs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    blogs = db.query(models.Blog).offset(skip).limit(limit).all()
    return blogs


@app.post("/blogs/", response_model=blog.Blog)
def create_blog(blog: blog.BlogCreate, db: Session = Depends(get_db)):
    db_blog = models.Blog(**blog.model_dump())
    db.add(db_blog)
    db.commit()
    db.refresh(db_blog)
    return db_blog


@app.get("/blogs/{blog_id}", response_model=blog.Blog)
def read_blog(blog_id: int, db: Session = Depends(get_db)):
    blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()
    if blog is None:
        raise HTTPException(status_code=404, detail="Blog not found")
    return blog


@app.put(
    "/blogs/{blog_id}",
    response_model=blog.Blog,
)
def update_blog(
    blog_id: int,
    blog: blog.BlogUpdate,
    db: Session = Depends(get_db),
):
    db_blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()
    if db_blog is None:
        raise HTTPException(status_code=404, detail="Blog not found")

    for field, value in blog.model_dump(exclude_unset=True).items():
        setattr(db_blog, field, value)

    db.commit()
    db.refresh(db_blog)
    return db_blog


@app.delete("/blogs/{blog_id}")
def delete_blog(blog_id: int, db: Session = Depends(get_db)):
    blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()
    if blog is None:
        raise HTTPException(status_code=404, detail="Blog not found")

    db.delete(blog)
    db.commit()
    return {"message": "Blog deleted successfully"}
