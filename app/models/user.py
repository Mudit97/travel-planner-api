from typing import Optional, List
from sqlmodel import SQLModel, Field, Relationship


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    email: str = Field(unique=True, index=True)

    trips: List["Trip"] = Relationship(back_populates="user")


# --- Request/Response schemas ---

class UserCreate(SQLModel):
    name: str
    email: str


class UserRead(SQLModel):
    id: int
    name: str
    email: str
