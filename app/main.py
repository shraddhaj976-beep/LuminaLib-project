from fastapi import FastAPI

from app.api import auth, books, intel, reviews
from app.db.base import init_db

app = FastAPI(title="LuminaLib API")

app.include_router(auth.router)
app.include_router(books.router)
app.include_router(reviews.router)
app.include_router(intel.router)


@app.on_event("startup")
async def on_startup():
    await init_db()


@app.get("/")
async def root():
    return {"message": "LuminaLib is running 🚀"}
