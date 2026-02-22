from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.base import get_db
from app.db.models import Book, Borrow, Review, User
from app.tasks.tasks import process_review_sentiment_task

router = APIRouter(prefix="/books", tags=["Reviews"])


class ReviewCreate(BaseModel):
    user_id: int
    rating: int | None = None
    text: str


@router.post("/{book_id}/reviews")
async def submit_review(
    book_id: int,
    payload: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="User mismatch for review action")
    book = (await db.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    user = (await db.execute(select(User).where(User.id == payload.user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    has_borrowed = (
        await db.execute(
            select(Borrow.id)
            .where(
                Borrow.book_id == book_id,
                Borrow.user_id == payload.user_id,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if not has_borrowed:
        raise HTTPException(status_code=403, detail="User has not borrowed this book")

    review = Review(
        book_id=book_id,
        user_id=payload.user_id,
        rating=payload.rating,
        text=payload.text,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    process_review_sentiment_task.delay(book_id, payload.user_id, payload.text)
    return {"msg": f"Review received for book {book_id}", "review_id": review.id}
