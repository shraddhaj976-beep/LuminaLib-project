from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.config import settings
from app.db.base import get_db
from app.db.models import Book, Review, User
from app.services.llm import get_llm
from app.services.prompts import render_aggregate_prompt

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
    result = await db.execute(select(Review.text).where(Review.book_id == book_id))
    texts = [r[0] for r in result.all() if r[0]]
    if not texts:
        return {"book_id": book_id, "summary": ""}
    llm = get_llm()
    prompt = render_aggregate_prompt(settings.aggregate_prompt, texts)
    summary = await llm.aggregate_reviews(texts, prompt=prompt)
    return {"book_id": book_id, "summary": summary}


@router.get("/recommendations")
async def get_recommendations(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    from app.api.recommendations import recommend_for_user

    ids = await recommend_for_user(current_user.id, db, top_n=10)
    if not ids:
        return {"recommendations": []}
    books = (await db.execute(select(Book).where(Book.id.in_(ids)))).scalars().all()
    by_id = {b.id: b for b in books}
    recommendations = [
        {
            "id": book_id,
            "title": by_id.get(book_id).title if by_id.get(book_id) else None,
            "author": by_id.get(book_id).author if by_id.get(book_id) else None,
        }
        for book_id in ids
    ]
    return {"recommendations": recommendations}
