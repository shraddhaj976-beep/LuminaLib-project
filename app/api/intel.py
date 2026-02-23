from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.db.base import get_db
from app.db.models import Book, User, UserPreference

router = APIRouter(tags=["Intel"])


@router.get("/books/{book_id}/analysis")
async def get_analysis(
    book_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    book = (await db.execute(select(Book).where(Book.id == book_id))).scalar_one_or_none()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")
    return {"book_id": book_id, "summary": book.review_summary or ""}


@router.get("/recommendations")
async def get_recommendations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.api.recommendations import recommend_for_user

    ids = await recommend_for_user(current_user.id, db, top_n=10)
    if not ids:
        return {"recommendations": []}
    prefs_q = await db.execute(
        select(UserPreference).where(UserPreference.user_id == current_user.id)
    )
    prefs = prefs_q.scalars().all()
    pref_tags = {p.tag for p in prefs}
    books = (await db.execute(select(Book).where(Book.id.in_(ids)))).scalars().all()
    by_id = {b.id: b for b in books}
    recommendations = [
        {
            "id": book_id,
            "title": by_id.get(book_id).title if by_id.get(book_id) else None,
            "author": by_id.get(book_id).author if by_id.get(book_id) else None,
            "matched_tags": (
                [t for t in (by_id.get(book_id).tags or []) if t in pref_tags]
                if by_id.get(book_id)
                else []
            ),
        }
        for book_id in ids
    ]
    return {"recommendations": recommendations}
