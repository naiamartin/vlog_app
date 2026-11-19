from sqlalchemy import Boolean, Column, ForeignKey, Integer, String, Table
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, unique=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    # Pictures from the bucket user_pictures in supabase
    # pre-processed before upload with image_processing.py
    picture = Column(String, index=True)
    email = Column(String, index=True)
    password_hash = Column("hashed_password", String, nullable=False)


class Blog(Base):
    __tablename__ = "blogs"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, index=True)
    text = Column(String, index=True)
    picture = Column(String, nullable=True)


# One user has many blogs
user_blogs = Table(
    "user_blogs",
    Base.metadata,
    Column('user_id', Integer, ForeignKey('users.id')),
    Column('blog_id', Integer, ForeignKey('blogs.id'))
)
