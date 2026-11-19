from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend import models
from backend.database import get_db
from backend.schemas import blog as blog_schema

router = APIRouter()


@router.get("/blogs/", response_model=list[blog_schema.Blog])
def read_blogs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(models.Blog).offset(skip).limit(limit).all()


@router.post("/blogs/", response_model=blog_schema.Blog)
def create_blog(blog: blog_schema.BlogCreate, db: Session = Depends(get_db)):
    db_blog = models.Blog(**blog.model_dump())
    db.add(db_blog)
    db.commit()
    db.refresh(db_blog)
    return db_blog


@router.get("/blogs/{blog_id}", response_model=blog_schema.Blog)
def read_blog(blog_id: int, db: Session = Depends(get_db)):
    db_blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()
    if db_blog is None:
        raise HTTPException(status_code=404, detail="Blog not found")
    return db_blog


@router.put("/blogs/{blog_id}", response_model=blog_schema.Blog)
def update_blog(
    blog_id: int,
    blog: blog_schema.BlogUpdate,
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


@router.delete("/blogs/{blog_id}")
def delete_blog(blog_id: int, db: Session = Depends(get_db)):
    db_blog = db.query(models.Blog).filter(models.Blog.id == blog_id).first()
    if db_blog is None:
        raise HTTPException(status_code=404, detail="Blog not found")

    db.delete(db_blog)
    db.commit()
    return {"message": "Blog deleted successfully"}
