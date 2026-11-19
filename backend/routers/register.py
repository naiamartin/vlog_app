import logging
import os
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import EmailStr
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from supabase import create_client

from backend import models
from backend.database import get_db
from backend.security import password_hash
from backend.services.image_processing import MAX_SIZE, process_image

router = APIRouter()
templates = Jinja2Templates(
    directory=Path(__file__).resolve().parents[2] / "frontend" / "pages"
)


@router.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="profile/register.html",
        context={"message": None},
    )


@router.post("/register", response_class=HTMLResponse)
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
            context={"message": "That username or email is already registered."},
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
