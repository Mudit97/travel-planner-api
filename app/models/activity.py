from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship


class Activity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    trip_id: int = Field(foreign_key="trip.id")

    trip: Optional["Trip"] = Relationship(back_populates="activities")


# --- Request/Response schemas ---

class ActivityCreate(SQLModel):
    name: str
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    trip_id: int


class ActivityRead(SQLModel):
    id: int
    name: str
    description: Optional[str]
    scheduled_at: Optional[datetime]
    trip_id: int
