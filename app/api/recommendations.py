from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Book, Borrow, UserPreference


async def recommend_for_user(user_id: int, db: AsyncSession, top_n=10):
    # load user's preferences
    q = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    prefs = q.scalars().all()
    tags = {p.tag: float(p.weight) for p in prefs}
    if not tags:
        return []

    borrowed_q = await db.execute(
        select(Borrow.book_id).where(
            Borrow.user_id == user_id,
            Borrow.status == "borrowed",
        )
    )
    borrowed_ids = {row[0] for row in borrowed_q.all()}

    # load books and compute content-based similarity (tags + summary)
    q2 = await db.execute(select(Book))
    books = q2.scalars().all()
    if not books:
        return []

    def book_text(b: Book) -> str:
        tag_text = " ".join(b.tags or [])
        summary_text = b.summary or ""
        return f"{tag_text} {summary_text}".strip()

    corpus = [book_text(b) for b in books]
    vectorizer = TfidfVectorizer(max_features=5000)
    X = vectorizer.fit_transform(corpus)

    seed_text = " ".join([f"{k} " * int(max(1, v)) for k, v in tags.items()])
    u_vec = vectorizer.transform([seed_text])
    sims = cosine_similarity(u_vec, X).flatten()

    scored = []
    for idx, b in enumerate(books):
        if b.id in borrowed_ids:
            continue
        if sims[idx] > 0:
            scored.append((b.id, float(sims[idx])))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [book_id for book_id, _ in scored[:top_n]]
