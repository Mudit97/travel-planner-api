from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import users, trips, activities
from app.database import create_db_and_tables

app = FastAPI(
    title="Travel Planner API",
    description="Plan trips and activities — Week 1 FastAPI project",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(users.router, prefix="/users", tags=["users"])
app.include_router(trips.router, prefix="/trips", tags=["trips"])
app.include_router(activities.router, prefix="/activities", tags=["activities"])
