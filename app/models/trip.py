from typing import Optional, List
from datetime import date
from sqlmodel import SQLModel, Field, Relationship


class Trip(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    title: str
    destination: str
    start_date: date
    end_date: date
    user_id: int = Field(foreign_key="user.id")
    budget: Optional[float] = Field(default=None)
    user: Optional["User"] = Relationship(back_populates="trips")
    activities: List["Activity"] = Relationship(back_populates="trip")


# --- Request/Response schemas ---

class TripCreate(SQLModel):
    title: str
    destination: str
    start_date: date
    end_date: date
    user_id: int


class TripRead(SQLModel):
    id: int
    title: str
    destination: str
    start_date: date
    end_date: date
    user_id: int

class TripUpdate(SQLModel):
    title: Optional[str] = None
    destination: Optional[str] = None
    end_date: Optional[date] = None
    start_date: Optional[date] = None