from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import Session

from app.database import get_session
from app.models.activity import Activity, ActivityCreate, ActivityRead
from app.models.trip import Trip

router = APIRouter()


@router.post("/", response_model=ActivityRead, status_code=201)
def add_activity(activity_in: ActivityCreate, session: Session = Depends(get_session)):
    trip = session.get(Trip, activity_in.trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    activity = Activity.model_validate(activity_in)
    session.add(activity)
    session.commit()
    session.refresh(activity)
    return activity


@router.get("/{activity_id}", response_model=ActivityRead)
def get_activity(activity_id: int, session: Session = Depends(get_session)):
    activity = session.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return activity


@router.delete("/{activity_id}", status_code=204)
def delete_activity(activity_id: int, session: Session = Depends(get_session)):
    activity = session.get(Activity, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    session.delete(activity)
    session.commit()
