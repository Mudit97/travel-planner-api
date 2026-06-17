from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session, select

from app.database import get_session
from app.models.trip import Trip, TripCreate, TripRead, TripUpdate
from app.models.activity import Activity, ActivityRead
from app.models.user import User

router = APIRouter()


@router.post("/", response_model=TripRead, status_code=201)
def add_trip(trip_in: TripCreate, session: Session = Depends(get_session)):
    user = session.get(User, trip_in.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    trip = Trip.model_validate(trip_in)
    session.add(trip)
    session.commit()
    session.refresh(trip)
    return trip


@router.get("/{trip_id}", response_model=TripRead)
def get_trip(trip_id: int, session: Session = Depends(get_session)):
    trip = session.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.get("/{trip_id}/itinerary", response_model=list[ActivityRead])
def get_itinerary(trip_id: int, session: Session = Depends(get_session)):
    """Fetch all activities for a trip, ordered by scheduled time."""
    trip = session.get(Trip, trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    activities = session.exec(
        select(Activity)
        .where(Activity.trip_id == trip_id)
        .order_by(Activity.scheduled_at)
    ).all()
    return activities


@router.get("/", response_model=list[TripRead])
def list_trips(user_id: Optional[int] = None, session: Session = Depends(get_session)):
    query = select(Trip)
    if user_id:
        query = query.where(Trip.user_id == user_id)
    return session.exec(query).all()

## Update a trip based on trip Id, validates input dates and returns 400 if invalid dates
@router.patch("/{trip_id}", response_model = TripRead, 
summary="Update a trip", description = "Update an existing trip by its ID.")
def update_trip(trip_id: int, trip: TripUpdate, session: Session = Depends(get_session)):
    query = select(Trip).where(Trip.id == trip_id)
    existingTrip = session.exec(query).first()
    if existingTrip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    effective_start = trip.start_date or existingTrip.start_date
    effective_end = trip.end_date or existingTrip.end_date
    if effective_start > effective_end:
        raise HTTPException(status_code=400, detail="Invalid date range")
    if trip.title is not None:
        existingTrip.title = trip.title
    if trip.destination is not None:
        existingTrip.destination = trip.destination
    if trip.start_date is not None:
        existingTrip.start_date = trip.start_date
    if trip.end_date is not None:
        existingTrip.end_date = trip.end_date
    session.add(existingTrip)
    session.commit()
    session.refresh(existingTrip)
    return existingTrip
