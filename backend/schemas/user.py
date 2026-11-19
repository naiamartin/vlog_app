from pydantic import BaseModel, ConfigDict, EmailStr


# Base schema with common attributes
class UserBase(BaseModel):
    email: EmailStr
    username: str
    picture: str | None = None
    is_admin: bool = False


# Schema for creating a new user
class UserCreate(BaseModel):
    email: EmailStr
    username: str
    picture: str | None = None
    password: str
    model_config = ConfigDict(extra="forbid")


# Schema for updating a user
class UserUpdate(UserBase):
    email: EmailStr | None = None
    username: str | None = None
    picture: str | None = None
    is_admin: bool | None = None
    password: str | None = None


# Schema for reading/returning a user(includes id)
class User(UserBase):
    id: int
    model_config = ConfigDict(from_attributes=True)
