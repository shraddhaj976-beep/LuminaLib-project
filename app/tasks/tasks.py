import asyncio
from io import BytesIO

from pdfminer.high_level import extract_text
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.db import models
from app.services.llm import get_llm
from app.services.prompts import render_aggregate_prompt
from app.services.sentiment import sentiment_score
from app.services.storage import get_storage

from .celery_app import celery


@celery.task(name="app.tasks.tasks.generate_summary")
def generate_summary_task(book_id: int):
    # Celery worker is sync, but we can run async DB calls using asyncio.run
    print(f"Starting summary generation for book {book_id}")
    asyncio.run(_generate_summary(book_id))


async def _generate_summary(book_id: int):
    llm = get_llm()
    storage = get_storage()
    engine = create_async_engine(settings.database_url, future=True, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        q = await session.execute(select(models.Book).where(models.Book.id == book_id))
        book = q.scalar_one()
        content_bytes = b""
        if book.content_path:
            if book.content_path.startswith("s3://"):
                key = book.content_path.split("/", 3)[-1]
                content_bytes = await storage.download(key)
            elif book.content_path.startswith("/"):
                with open(book.content_path, "rb") as f:
                    content_bytes = f.read()
            else:
                content_bytes = await storage.download(book.content_path)

        content_text = ""
        if content_bytes.startswith(b"%PDF"):
            try:
                content_text = extract_text(BytesIO(content_bytes)) or ""
            except Exception:
                content_text = ""
        if not content_text:
            if b"\x00" in content_bytes:
                content_text = ""
            else:
                try:
                    content_text = content_bytes.decode("utf-8")
                except UnicodeDecodeError:
                    content_text = content_bytes.decode("utf-8", errors="ignore")
                printable = sum(ch.isprintable() for ch in content_text)
                if content_text and (printable / max(1, len(content_text))) < 0.6:
                    content_text = ""
                content_text = content_text.replace("\x00", "")

        summary = await llm.summarize(content_text[:20000])  # chunk limit
        tags = await llm.generate_tags(content_text[:20000])
        print(f"Generated summary for book {book_id}: {summary}")
        book.summary = summary
        book.tags = tags
        session.add(book)
        await session.commit()
    await engine.dispose()


@celery.task(name="app.tasks.tasks.aggregate_reviews")
def aggregate_reviews_task(book_id: int):
    asyncio.run(_aggregate_reviews(book_id))


async def _aggregate_reviews(book_id: int):
    llm = get_llm()
    engine = create_async_engine(settings.database_url, future=True, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        q = await session.execute(select(models.Review).where(models.Review.book_id == book_id))
        reviews = q.scalars().all()
        texts = [r.text for r in reviews]
        if not texts:
            await engine.dispose()
            return
        prompt = render_aggregate_prompt(settings.aggregate_prompt, texts)
        analysis = await llm.aggregate_reviews(texts, prompt=prompt)
        # store in dedicated review_summary field
        q2 = await session.execute(select(models.Book).where(models.Book.id == book_id))
        book = q2.scalar_one()
        book.review_summary = analysis
        session.add(book)
        await session.commit()
    await engine.dispose()


@celery.task(name="app.tasks.tasks.process_review_sentiment")
def process_review_sentiment_task(book_id: int, user_id: int, text: str):
    asyncio.run(_process_review_sentiment(book_id, user_id, text))


async def _process_review_sentiment(book_id: int, user_id: int, text: str):
    engine = create_async_engine(settings.database_url, future=True, poolclass=NullPool)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        q = await session.execute(select(models.Book).where(models.Book.id == book_id))
        book = q.scalar_one_or_none()
        if not book:
            await engine.dispose()
            return

        score = sentiment_score(text)
        if score > 0:
            delta = 1.0
        elif score < 0:
            delta = -0.5
        else:
            delta = 0.5

        print(
            f"Review sentiment for user {user_id}, book {book_id}: " f"score={score}, delta={delta}"
        )

        if book.tags:
            for tag in book.tags:
                pref = (
                    await session.execute(
                        select(models.UserPreference).where(
                            models.UserPreference.user_id == user_id,
                            models.UserPreference.tag == tag,
                        )
                    )
                ).scalar_one_or_none()
                if pref:
                    pref.weight = max(0.1, float(pref.weight) + delta)
                else:
                    session.add(
                        models.UserPreference(
                            user_id=user_id,
                            tag=tag,
                            weight=max(0.1, 1.0 + delta),
                        )
                    )

        session.add(
            models.UserInteraction(
                user_id=user_id,
                book_id=book_id,
                event_type="review",
                sentiment=float(score),
            )
        )
        await session.commit()
    await engine.dispose()
